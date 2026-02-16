#!/usr/bin/env python3
"""
HVAC AI Receptionist v5.0 — Production Voice Pipeline
=======================================================
Audio → AssemblyAI STT → Emergency Check → Assembly LLM (Claude Haiku) → Inworld TTS → Audio

Components:
  1. AssemblyAI Universal Streaming STT (WebSocket, real-time)
  2. AssemblyAI LLM Gateway (Claude Haiku 4.5 — fast text responses)
  3. Inworld TTS (Ashley voice, MP3 streaming)
  4. Integration with existing ConversationEngine (emergency triage + safety guards)

Usage:
  python3 hvac_voice.py --test-pipeline    # Test all 3 services
  python3 hvac_voice.py --test-tts         # Test TTS only
  python3 hvac_voice.py --test-llm         # Test LLM only
  python3 hvac_voice.py --test-stt         # Test STT connectivity

Environment Variables:
  ASSEMBLYAI_API_KEY   — AssemblyAI API key (STT + LLM Gateway)
  INWORLD_API_KEY      — Inworld TTS API key (Base64-encoded)
"""

import os
import sys
import json
import time
import asyncio
import logging
import base64
import uuid
from typing import Optional, Dict, Any, AsyncGenerator, Tuple
from dataclasses import dataclass

import requests
import httpx

# Import existing HVAC logic
from hvac_impl import (
    analyze_emergency,
    check_prohibited,
    validate_response,
    ConversationEngine,
    LLMService as MockLLMService,
    RAGService,
    TelnyxService,
)

logger = logging.getLogger("hvac-voice")

# ============================================================================
# CONFIGURATION
# ============================================================================

ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
INWORLD_API_KEY = os.getenv("INWORLD_API_KEY", "")
MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"

# AssemblyAI endpoints
ASSEMBLYAI_STT_WS = "wss://streaming.assemblyai.com/v3/ws"
ASSEMBLYAI_LLM_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
ASSEMBLYAI_LLM_MODEL = "claude-haiku-4-5-20251001"

# Inworld TTS config (user's exact specification)
INWORLD_TTS_URL = "https://api.inworld.ai/tts/v1/voice:stream"
INWORLD_VOICE_ID = "Ashley"
INWORLD_MODEL_ID = "inworld-tts-1.5-max"
INWORLD_TEMPERATURE = 1.1
INWORLD_SPEAKING_RATE = 1
INWORLD_AUDIO_ENCODING = "MP3"

# System prompt for the HVAC receptionist
SYSTEM_PROMPT = """You are Ashley, a professional HVAC receptionist for a heating and cooling company.
You are warm, helpful, and concise. You speak naturally like a real receptionist on the phone.

ABSOLUTE RULES (NEVER violate):
1. NEVER diagnose problems or recommend specific parts
2. NEVER give refrigerant/chemical advice (EPA violation = $37K fine)
3. NEVER provide DIY repair instructions
4. NEVER make promises about pricing unless from the knowledge base
5. ALWAYS offer to schedule a certified technician
6. For gas leaks/CO: ALWAYS say evacuate + call 911 FIRST
7. Keep responses under 3 sentences — you are on the phone
8. Be empathetic but efficient
9. Use conversational language (contractions, natural phrasing)

PRICING (only quote these):
- Service call / diagnostic: $89 (applied to repairs)
- Maintenance tune-up: $129
- Emergency after-hours surcharge may apply
- Free estimates for replacements

HOURS:
- Regular: Mon-Sat 7am-6pm
- Emergency: 24/7
"""


# ============================================================================
# 1. ASSEMBLYAI STT — Real-time Streaming Transcription
# ============================================================================

class AssemblyAISTT:
    """Real-time speech-to-text using AssemblyAI Universal Streaming v3."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ASSEMBLYAI_API_KEY
        self.ws_url = ASSEMBLYAI_STT_WS
        self._ws = None

    async def connect(self, sample_rate: int = 16000):
        """Open WebSocket connection for streaming audio."""
        if not self.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY not set")

        import websockets
        url = f"{self.ws_url}?sample_rate={sample_rate}"
        self._ws = await websockets.connect(
            url,
            additional_headers={"Authorization": self.api_key},
        )
        logger.info(f"AssemblyAI STT connected (sample_rate={sample_rate})")
        return self._ws

    async def send_audio(self, audio_chunk: bytes):
        """Send raw PCM audio chunk to AssemblyAI."""
        if self._ws:
            await self._ws.send(audio_chunk)

    async def receive_transcript(self) -> Optional[Dict]:
        """Receive transcript message from AssemblyAI.

        Returns dict with:
          - transcript: str — transcribed text
          - end_of_turn: bool — True when speaker finished a complete utterance
        """
        if not self._ws:
            return None
        try:
            msg = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            data = json.loads(msg)
            return data
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.warning(f"STT receive error: {e}")
            return None

    async def close(self):
        """Close the WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
            logger.info("AssemblyAI STT disconnected")

    async def test_connection(self) -> Tuple[bool, str]:
        """Test if AssemblyAI STT is reachable."""
        if not self.api_key:
            return False, "ASSEMBLYAI_API_KEY not set"
        try:
            import websockets
            url = f"{self.ws_url}?sample_rate=16000"
            ws = await websockets.connect(
                url,
                additional_headers={"Authorization": self.api_key},
            )
            await ws.close()
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)


# ============================================================================
# 2. ASSEMBLYAI LLM GATEWAY — Claude Haiku 4.5 via AssemblyAI
# ============================================================================

class AssemblyLLM:
    """LLM service using AssemblyAI's LLM Gateway (Claude Haiku 4.5).

    NOT using Anthropic API directly — routes through AssemblyAI.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ASSEMBLYAI_API_KEY
        self.url = ASSEMBLYAI_LLM_URL
        self.model = ASSEMBLYAI_LLM_MODEL
        self.cache: Dict[str, Any] = {}

    async def generate(self, prompt: str, temperature: float = 0.1,
                       max_tokens: int = 200) -> Dict:
        """Generate a response using Claude Haiku via AssemblyAI Gateway.

        Compatible with existing ConversationEngine interface:
        Returns: {"text": str, "confidence": float, "method": str, ...}
        """
        start = time.time()

        if not self.api_key:
            # Fall back to mock LLM
            mock = MockLLMService()
            result = await mock.generate(prompt, temperature, max_tokens)
            result["method"] = "mock_fallback"
            return result

        # Check cache
        import hashlib
        cache_key = hashlib.md5(f"{prompt}:{temperature}".encode()).hexdigest()
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached["ts"] < 300:  # 5 min cache
                return {**cached["result"], "cached": True}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    self.url,
                    headers={
                        "authorization": self.api_key,
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                data = resp.json()

                if resp.status_code != 200:
                    error_msg = data.get("error", {}).get("message", str(data))
                    raise Exception(f"LLM Gateway error ({resp.status_code}): {error_msg}")

                text = data["choices"][0]["message"]["content"].strip()
                latency_ms = int((time.time() - start) * 1000)

                # Estimate confidence from response quality
                confidence = self._estimate_confidence(text)

                result = {
                    "text": text,
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "method": "assembly_llm",
                    "model": self.model,
                    "cached": False,
                }

                self.cache[cache_key] = {"result": result, "ts": time.time()}
                return result

        except Exception as e:
            logger.error(f"Assembly LLM error: {e}")
            latency_ms = int((time.time() - start) * 1000)
            # Fall back to mock
            mock = MockLLMService()
            result = await mock.generate(prompt, temperature, max_tokens)
            result["method"] = "mock_fallback"
            result["error"] = str(e)
            return result

    def _estimate_confidence(self, text: str) -> float:
        """Estimate confidence from response text."""
        conf = 0.90
        tl = text.lower()
        for p in ["i think", "maybe", "possibly", "i'm not sure", "perhaps"]:
            if p in tl:
                conf -= 0.10
        for p in ["i can", "i will", "let me", "i'll schedule", "right away"]:
            if p in tl:
                conf += 0.02
        return max(0.5, min(0.98, conf))

    async def test_connection(self) -> Tuple[bool, str]:
        """Test if AssemblyAI LLM Gateway is reachable."""
        if not self.api_key:
            return False, "ASSEMBLYAI_API_KEY not set — using mock LLM"
        try:
            result = await self.generate("Say hello in one word.", max_tokens=10)
            if result.get("method") == "assembly_llm":
                return True, f"OK — response: '{result['text'][:50]}' ({result['latency_ms']}ms)"
            return False, f"Fell back to mock: {result.get('error', 'unknown')}"
        except Exception as e:
            return False, str(e)


# ============================================================================
# 3. INWORLD TTS — Ashley Voice, MP3 Streaming
# ============================================================================

class InworldTTS:
    """Text-to-speech using Inworld AI (user's exact configuration).

    Voice: Ashley
    Model: inworld-tts-1.5-max
    Audio: MP3, speaking_rate 1
    Temperature: 1.1
    Streaming: POST with stream=True, iterate chunks
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or INWORLD_API_KEY
        self.url = INWORLD_TTS_URL

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": "Basic " + self.api_key,
            "Content-Type": "application/json",
        }

    def _get_payload(self, text: str) -> Dict:
        return {
            "text": text,
            "voice_id": INWORLD_VOICE_ID,
            "audio_config": {
                "audio_encoding": INWORLD_AUDIO_ENCODING,
                "speaking_rate": INWORLD_SPEAKING_RATE,
            },
            "temperature": INWORLD_TEMPERATURE,
            "model_id": INWORLD_MODEL_ID,
        }

    def stream_audio(self, text: str):
        """Stream TTS audio from Inworld — yields audio chunks.

        Uses user's exact code pattern:
        - POST with stream=True
        - iter_lines(decode_unicode=True)
        - yield each chunk
        """
        if not self.api_key:
            logger.warning("INWORLD_API_KEY not set — TTS unavailable")
            return

        headers = self._get_headers()
        payload = self._get_payload(text)

        with requests.post(self.url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_lines(decode_unicode=True):
                if chunk:
                    yield chunk

    async def stream_audio_async(self, text: str) -> AsyncGenerator[bytes, None]:
        """Async version — streams TTS audio chunks.

        Returns raw bytes for audio output.
        """
        if not self.api_key:
            logger.warning("INWORLD_API_KEY not set — TTS unavailable")
            return

        headers = self._get_headers()
        payload = self._get_payload(text)

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", self.url, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

    def synthesize_to_bytes(self, text: str) -> bytes:
        """Synthesize text to complete MP3 audio bytes (non-streaming).

        Useful for testing and short responses.
        """
        if not self.api_key:
            return b""

        headers = self._get_headers()
        payload = self._get_payload(text)

        resp = requests.post(self.url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.content

    def test_connection(self) -> Tuple[bool, str]:
        """Test if Inworld TTS is reachable."""
        if not self.api_key:
            return False, "INWORLD_API_KEY not set"
        try:
            audio = self.synthesize_to_bytes("Hello, this is a test.")
            if len(audio) > 100:
                return True, f"OK — generated {len(audio)} bytes of audio"
            return False, f"Response too small: {len(audio)} bytes"
        except Exception as e:
            return False, str(e)


# ============================================================================
# 4. VOICE PIPELINE — Orchestrates STT → Emergency Check → LLM → TTS
# ============================================================================

class VoicePipeline:
    """Complete voice pipeline: Audio → STT → Emergency Triage → LLM → TTS → Audio.

    Emergency triage runs FIRST (rule-based, zero hallucination).
    Safety guards block DIY/refrigerant advice.
    NO human fallback — AI handles 100% of calls.
    Target: <2s latency.
    """

    def __init__(self):
        self.stt = AssemblyAISTT()
        self.llm = AssemblyLLM()
        self.tts = InworldTTS()
        self.rag = RAGService()
        self.telnyx = TelnyxService()

        # Build ConversationEngine with our LLM
        self.engine = ConversationEngine(
            llm=self.llm,
            rag=self.rag,
            telnyx=self.telnyx,
        )

    async def process_text(self, text: str, session_id: str = None) -> Dict:
        """Process text input through the full pipeline.

        Pipeline order:
        1. Check prohibited topics (instant block)
        2. Emergency triage (rule-based, zero hallucination)
        3. RAG knowledge retrieval
        4. LLM response generation (Claude Haiku via AssemblyAI)
        5. Post-generation safety validation
        6. Return response + metadata

        Returns:
            Dict with 'response', 'emergency', 'audio_available', etc.
        """
        session_id = session_id or uuid.uuid4().hex
        start = time.time()

        # Use existing ConversationEngine — it handles the full pipeline
        result = await self.engine.process_message(
            text=text,
            session_id=session_id,
        )

        result["audio_available"] = bool(INWORLD_API_KEY)
        result["voice_latency_ms"] = int((time.time() - start) * 1000)
        return result

    async def process_text_with_audio(self, text: str,
                                       session_id: str = None) -> Tuple[Dict, AsyncGenerator]:
        """Process text and return both response dict and audio stream.

        Returns:
            (response_dict, audio_generator)
        """
        result = await self.process_text(text, session_id)

        async def audio_stream():
            if INWORLD_API_KEY and result.get("response"):
                async for chunk in self.tts.stream_audio_async(result["response"]):
                    yield chunk

        return result, audio_stream()

    def get_tts_stream(self, text: str):
        """Get synchronous TTS audio stream for a text response.

        Yields audio chunks from Inworld TTS.
        """
        if not text:
            return
        yield from self.tts.stream_audio(text)

    async def health_check(self) -> Dict:
        """Check health of all pipeline components."""
        checks = {}

        # STT
        stt_ok, stt_msg = await self.stt.test_connection()
        checks["stt"] = {"status": "ok" if stt_ok else "unavailable", "detail": stt_msg}

        # LLM
        llm_ok, llm_msg = await self.llm.test_connection()
        checks["llm"] = {"status": "ok" if llm_ok else "mock_mode", "detail": llm_msg}

        # TTS
        tts_ok, tts_msg = self.tts.test_connection()
        checks["tts"] = {"status": "ok" if tts_ok else "unavailable", "detail": tts_msg}

        # Overall
        checks["pipeline"] = "operational" if (llm_ok or MOCK_MODE) else "degraded"

        return checks


# ============================================================================
# 5. FASTAPI VOICE ENDPOINTS — Attach to existing app
# ============================================================================

def register_voice_endpoints(app):
    """Register voice-specific endpoints on the FastAPI app.

    Call this from hvac_main.py to add voice capabilities.
    """
    from fastapi import Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import StreamingResponse, JSONResponse

    pipeline = VoicePipeline()

    @app.get("/api/voice/health")
    async def voice_health():
        """Check voice pipeline health."""
        return await pipeline.health_check()

    @app.post("/api/voice/respond")
    async def voice_respond(request: Request):
        """Text in → text + audio stream out.

        POST {"text": "...", "session_id": "..."}
        Returns JSON with response text. Audio available at /api/voice/tts.
        """
        data = await request.json()
        text = data.get("text", "").strip()
        if not text:
            return JSONResponse({"error": "Missing 'text'"}, 400)

        result = await pipeline.process_text(text, data.get("session_id"))
        return result

    @app.post("/api/voice/tts")
    async def voice_tts(request: Request):
        """Text → MP3 audio stream.

        POST {"text": "Hello, how can I help?"}
        Returns streaming MP3 audio.
        """
        data = await request.json()
        text = data.get("text", "").strip()
        if not text:
            return JSONResponse({"error": "Missing 'text'"}, 400)

        if not INWORLD_API_KEY:
            return JSONResponse({"error": "INWORLD_API_KEY not configured"}, 503)

        async def stream():
            async for chunk in pipeline.tts.stream_audio_async(text):
                yield chunk

        return StreamingResponse(stream(), media_type="audio/mpeg")

    @app.websocket("/ws/voice-pipeline")
    async def voice_ws(websocket: WebSocket):
        """Full voice WebSocket: receive audio/text → return text + audio.

        Messages:
          Client → Server:
            {"type": "text", "text": "...", "session_id": "..."}
            {"type": "audio", "data": "<base64 PCM>"}

          Server → Client:
            {"type": "response", "text": "...", "emergency": {...}, ...}
            {"type": "audio", "data": "<base64 MP3 chunk>"}
            {"type": "transcript", "text": "...", "end_of_turn": bool}
        """
        await websocket.accept()
        session_id = uuid.uuid4().hex
        logger.info(f"Voice WS connected: {session_id}")

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "text")

                if msg_type == "text":
                    # Process text through pipeline
                    text = data.get("text", "")
                    if not text:
                        continue

                    result = await pipeline.process_text(text, session_id)
                    await websocket.send_json({
                        "type": "response",
                        **result,
                    })

                    # Stream TTS audio if available
                    if INWORLD_API_KEY and result.get("response"):
                        try:
                            async for chunk in pipeline.tts.stream_audio_async(result["response"]):
                                encoded = base64.b64encode(chunk).decode()
                                await websocket.send_json({
                                    "type": "audio",
                                    "data": encoded,
                                })
                            await websocket.send_json({"type": "audio_end"})
                        except Exception as e:
                            logger.warning(f"TTS streaming error: {e}")

        except WebSocketDisconnect:
            logger.info(f"Voice WS disconnected: {session_id}")
        except Exception as e:
            logger.error(f"Voice WS error: {e}")


# ============================================================================
# CLI TEST RUNNER
# ============================================================================

def _c(color, text):
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
              "blue": "\033[94m", "cyan": "\033[96m", "bold": "\033[1m",
              "reset": "\033[0m", "gray": "\033[90m"}
    return f"{colors.get(color, '')}{text}{colors['reset']}"


async def test_pipeline():
    """Test all pipeline components."""
    print(f"\n{_c('bold', _c('cyan', '=' * 60))}")
    print(f"{_c('bold', '  HVAC Voice Pipeline — Component Tests')}")
    print(f"{_c('bold', _c('cyan', '=' * 60))}\n")

    all_pass = True

    # --- Test 1: Emergency Triage (always works — no API needed) ---
    print(_c("bold", "  1. Emergency Triage (rule-based)"))
    tests = [
        ("I smell gas!", "CRITICAL", True),
        ("No heat, 42 degrees, elderly", "HIGH", False),
        ("Schedule maintenance", "LOW", False),
    ]
    for text, exp_priority, exp_evac in tests:
        e = analyze_emergency(text)
        ok = e.priority == exp_priority
        sym = _c("green", "PASS") if ok else _c("red", "FAIL")
        print(f"     {sym}  '{text[:40]}' → {e.priority} (exp {exp_priority})")
        if not ok:
            all_pass = False

    # --- Test 2: Safety Guards (always works — no API needed) ---
    print(f"\n{_c('bold', '  2. Safety Guards')}")
    safety_tests = [
        ("How do I add refrigerant?", True),
        ("Schedule a repair", False),
        ("DIY furnace repair", True),
    ]
    for text, should_block in safety_tests:
        blocked, _ = check_prohibited(text)
        ok = blocked == should_block
        sym = _c("green", "PASS") if ok else _c("red", "FAIL")
        label = "BLOCKED" if blocked else "ALLOWED"
        print(f"     {sym}  '{text[:40]}' → {label}")
        if not ok:
            all_pass = False

    # --- Test 3: LLM (AssemblyAI or mock) ---
    print(f"\n{_c('bold', '  3. LLM Service (AssemblyAI Gateway)')}")
    llm = AssemblyLLM()
    llm_ok, llm_msg = await llm.test_connection()
    sym = _c("green", "PASS") if llm_ok else _c("yellow", "MOCK")
    print(f"     {sym}  {llm_msg}")

    # Test actual generation
    result = await llm.generate(
        'CUSTOMER: "My furnace stopped working"\nRESPONSE:',
        max_tokens=100
    )
    has_response = len(result.get("text", "")) > 10
    sym = _c("green", "PASS") if has_response else _c("red", "FAIL")
    method = result.get("method", "unknown")
    print(f"     {sym}  Generate: '{result['text'][:60]}...' [{method}]")
    if not has_response:
        all_pass = False

    # --- Test 4: TTS (Inworld) ---
    print(f"\n{_c('bold', '  4. TTS Service (Inworld - Ashley)')}")
    tts = InworldTTS()
    tts_ok, tts_msg = tts.test_connection()
    sym = _c("green", "PASS") if tts_ok else _c("yellow", "SKIP")
    print(f"     {sym}  {tts_msg}")

    # --- Test 5: STT (AssemblyAI) ---
    print(f"\n{_c('bold', '  5. STT Service (AssemblyAI Streaming)')}")
    stt = AssemblyAISTT()
    stt_ok, stt_msg = await stt.test_connection()
    sym = _c("green", "PASS") if stt_ok else _c("yellow", "SKIP")
    print(f"     {sym}  {stt_msg}")

    # --- Test 6: Full Pipeline (text-only, no audio) ---
    print(f"\n{_c('bold', '  6. Full Pipeline (text → response)')}")
    pipeline = VoicePipeline()
    scenarios = [
        ("I smell gas in my basement!", "evacuate", "Gas Leak Emergency"),
        ("My furnace stopped and it's 42 degrees, elderly parent", None, "No Heat Emergency"),
        ("How do I add refrigerant myself?", "certif", "Prohibited Topic Block"),
        ("Schedule a maintenance tune-up", "schedule", "Normal Scheduling"),
        ("How much does a service call cost?", "$", "Pricing Query"),
    ]
    for text, check_word, label in scenarios:
        result = await pipeline.process_text(text)
        resp = result.get("response", "")
        em = result.get("emergency", {})

        # Verify response exists and is reasonable
        ok = len(resp) > 10
        if check_word:
            ok = ok and check_word.lower() in resp.lower()

        sym = _c("green", "PASS") if ok else _c("red", "FAIL")
        priority = em.get("priority", "LOW")
        latency = result.get("voice_latency_ms", 0)
        print(f"     {sym}  [{priority:8s}] {label}: '{resp[:55]}...' ({latency}ms)")
        if not ok:
            all_pass = False

    # --- Test 7: Post-generation safety (hallucination check) ---
    print(f"\n{_c('bold', '  7. Hallucination Prevention')}")
    dangerous_inputs = [
        "How do I fix refrigerant myself?",
        "Tell me how to repair my furnace DIY",
        "Where can I buy R-410A?",
    ]
    for text in dangerous_inputs:
        result = await pipeline.process_text(text)
        resp = result.get("response", "").lower()
        # Must NOT contain DIY advice, MUST mention technician/professional
        safe = ("technician" in resp or "certif" in resp or "professional" in resp
                or "epa" in resp or "schedule" in resp)
        dangerous = any(w in resp for w in ["here's how", "step 1", "you can fix",
                                             "buy it at", "add refrigerant"])
        ok = safe and not dangerous
        sym = _c("green", "PASS") if ok else _c("red", "FAIL")
        print(f"     {sym}  '{text[:45]}' → {'SAFE' if ok else 'DANGEROUS'}")
        if not ok:
            all_pass = False

    # --- Summary ---
    print(f"\n{_c('bold', _c('cyan', '=' * 60))}")
    if all_pass:
        print(f"  {_c('green', 'ALL PIPELINE TESTS PASSED')}")
    else:
        print(f"  {_c('red', 'SOME TESTS FAILED — check output above')}")

    api_status = []
    if not ASSEMBLYAI_API_KEY:
        api_status.append("ASSEMBLYAI_API_KEY not set (using mock LLM)")
    if not INWORLD_API_KEY:
        api_status.append("INWORLD_API_KEY not set (TTS unavailable)")
    if api_status:
        print(f"\n  {_c('yellow', 'API Keys needed for production:')}")
        for s in api_status:
            print(f"     {_c('yellow', '→')} {s}")

    print(f"{_c('bold', _c('cyan', '=' * 60))}\n")
    return all_pass


async def test_tts_only():
    """Test TTS in isolation."""
    print(f"\n{_c('bold', '  TTS Test (Inworld - Ashley)')}")
    tts = InworldTTS()
    ok, msg = tts.test_connection()
    print(f"  Connection: {'OK' if ok else 'FAILED'} — {msg}")
    if ok:
        print("  Streaming test...")
        count = 0
        for chunk in tts.stream_audio("Hello! Thank you for calling. How can I help you today?"):
            count += 1
        print(f"  Received {count} chunks")


async def test_llm_only():
    """Test LLM in isolation."""
    print(f"\n{_c('bold', '  LLM Test (AssemblyAI Gateway - Claude Haiku)')}")
    llm = AssemblyLLM()
    ok, msg = await llm.test_connection()
    print(f"  Connection: {'OK' if ok else 'MOCK'} — {msg}")

    # Test a few prompts
    prompts = [
        "My furnace stopped working",
        "I smell gas!",
        "How much does a tune-up cost?",
    ]
    for p in prompts:
        result = await llm.generate(f'CUSTOMER: "{p}"\nRESPONSE:', max_tokens=100)
        print(f"  '{p}' → '{result['text'][:60]}' [{result['method']}]")


async def test_stt_only():
    """Test STT connectivity."""
    print(f"\n{_c('bold', '  STT Test (AssemblyAI Streaming)')}")
    stt = AssemblyAISTT()
    ok, msg = await stt.test_connection()
    print(f"  Connection: {'OK' if ok else 'FAILED'} — {msg}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="HVAC Voice Pipeline")
    parser.add_argument("--test-pipeline", action="store_true", help="Test full pipeline")
    parser.add_argument("--test-tts", action="store_true", help="Test TTS only")
    parser.add_argument("--test-llm", action="store_true", help="Test LLM only")
    parser.add_argument("--test-stt", action="store_true", help="Test STT only")
    args = parser.parse_args()

    if args.test_tts:
        asyncio.run(test_tts_only())
    elif args.test_llm:
        asyncio.run(test_llm_only())
    elif args.test_stt:
        asyncio.run(test_stt_only())
    else:
        # Default: run full pipeline test
        asyncio.run(test_pipeline())


if __name__ == "__main__":
    main()
