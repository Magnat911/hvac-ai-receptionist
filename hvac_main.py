#!/usr/bin/env python3
"""
HVAC AI Receptionist v5.0 - Production-Ready with Full Mock Mode
Integrated: AI Receptionist + Smart Dispatch + Inventory + Emergency Triage + EPA Compliance

MODES:
- MOCK_MODE=1: All external APIs mocked (for testing without keys/balance)
- MOCK_MODE=0: Real APIs (AssemblyAI/Claude Haiku, Telnyx)

Stack: FastAPI + PostgreSQL + OR-Tools + Telnyx + Claude Haiku 4.5 (AssemblyAI Gateway)
"""

import os
import asyncio
import logging
import json
import time
import re
import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx

# Optional imports with graceful fallback
try:
    import asyncpg
    HAS_PG = True
except ImportError:
    HAS_PG = False

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    from prometheus_client import Counter as PCounter, Histogram as PHist, generate_latest, CONTENT_TYPE_LATEST
    HAS_PROM = True
except ImportError:
    HAS_PROM = False

# ============================================================================
# CONFIGURATION
# ============================================================================

MOCK_MODE = os.getenv("MOCK_MODE", "1") == "1"
USE_PGVECTOR = os.getenv("USE_PGVECTOR", "0") == "1"
USE_SELF_CONS = os.getenv("USE_SELF_CONS", "0") == "1"
GRAPH_KEY = os.getenv("GRAPH_KEY", "")
USE_EPA = os.getenv("USE_EPA", "0") == "1"
LOG_DIR = os.getenv("LOG_DIR", "./logs")

# Thresholds
STT_CONFIDENCE_THRESHOLD = float(os.getenv("STT_CONFIDENCE_THRESHOLD", "0.90"))
LLM_CONFIDENCE_THRESHOLD = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.85"))
HUMAN_FALLBACK_THRESHOLD = float(os.getenv("HUMAN_FALLBACK_THRESHOLD", "0.80"))
TARGET_LATENCY_MS = 200

# API Keys (loaded from .env)
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")
ASSEMBLYAI_LLM_URL = "https://llm-gateway.assemblyai.com/v1/chat/completions"
ASSEMBLYAI_LLM_MODEL = "claude-haiku-4-5-20251001"
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "")
TELNYX_PHONE = os.getenv("TELNYX_PHONE", "")
HUMAN_FALLBACK_NUMBER = os.getenv("HUMAN_FALLBACK_NUMBER", "")
REDIS_URL = os.getenv("REDIS_URL", "")

# Logging
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/hvac.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("hvac-ai")
logger.info(f"HVAC AI v5.0 | MOCK={MOCK_MODE} | PGVECTOR={USE_PGVECTOR} | EPA={USE_EPA}")

# ============================================================================
# METRICS (optional Prometheus)
# ============================================================================

if HAS_PROM:
    calls_total = PCounter("hvac_calls_total", "Total calls processed", ["status"])
    emergency_total = PCounter("hvac_emergency_total", "Emergency calls", ["type"])
    llm_latency = PHist("hvac_llm_latency_seconds", "LLM response latency")
    e2e_latency = PHist("hvac_e2e_latency_seconds", "End-to-end latency")
else:
    # Stub metrics
    class _Stub:
        def labels(self, **kw): return self
        def inc(self): pass
        def observe(self, v): pass
    calls_total = _Stub()
    emergency_total = _Stub()
    llm_latency = _Stub()
    e2e_latency = _Stub()

# ============================================================================
# HVAC DOMAIN: Keywords, Prohibited Topics, Knowledge Base
# ============================================================================

HVAC_KEYTERMS = [
    "furnace", "air conditioner", "ac", "heat pump", "boiler", "thermostat",
    "compressor", "condenser", "evaporator", "ductwork", "vents", "filter",
    "no heat", "no ac", "not cooling", "not heating", "leaking", "frozen",
    "gas smell", "carbon monoxide", "co detector", "maintenance", "tune-up",
    "repair", "installation", "replacement", "emergency", "urgent",
    "degrees", "temperature", "elderly", "baby", "sick", "medical", "pregnant",
]

PROHIBITED_PATTERNS = {
    "refrigerant": "I cannot provide refrigerant advice. EPA regulations require a certified technician. Let me schedule one for you.",
    "freon": "I cannot provide refrigerant advice. EPA regulations require a certified technician. Let me schedule one for you.",
    "r-22": "I cannot provide refrigerant advice. EPA regulations require a certified technician. Let me schedule one for you.",
    "r-410a": "I cannot provide refrigerant advice. EPA regulations require a certified technician. Let me schedule one for you.",
    "how do i fix": "For safety and warranty reasons, I can only schedule a certified technician. Would you like me to do that?",
    "how to repair": "For safety and warranty reasons, I can only schedule a certified technician. Would you like me to do that?",
    "diy": "For safety and warranty reasons, I can only schedule a certified technician. Would you like me to do that?",
}

DEFAULT_KNOWLEDGE_BASE = {
    "emergency_no_heat": {
        "title": "Emergency: No Heat",
        "content": "No heat in cold weather is an emergency, especially with vulnerable occupants. We prioritize same-day service for heating emergencies.",
        "category": "emergency",
    },
    "emergency_no_ac": {
        "title": "Emergency: No AC",
        "content": "No AC in extreme heat can be dangerous. We offer priority scheduling for cooling emergencies, especially when indoor temperatures exceed 85°F.",
        "category": "emergency",
    },
    "emergency_gas": {
        "title": "Emergency: Gas Leak",
        "content": "If you smell gas, evacuate immediately and call 911. Do not use electrical switches. After safety is confirmed, we can send a technician.",
        "category": "emergency",
    },
    "scheduling": {
        "title": "Appointment Scheduling",
        "content": "We offer same-day emergency service, next-day standard service, and flexible scheduling for maintenance. Morning (8-12), afternoon (12-5), or specific time windows available.",
        "category": "general",
    },
    "maintenance": {
        "title": "HVAC Maintenance",
        "content": "Regular maintenance includes filter changes, system inspection, refrigerant check (by certified tech), and efficiency optimization. Recommended twice yearly.",
        "category": "maintenance",
    },
    "pricing": {
        "title": "Service Pricing",
        "content": "Service call / diagnostic fee: $89 (applied toward repair). Tune-up / maintenance: $129. Capacitor replacement: $149.99. Compressor replacement: $599.99. Maintenance plans from $199/year. Emergency surcharge may apply for after-hours. We provide upfront pricing before any work begins.",
        "category": "pricing",
    },
    "hours": {
        "title": "Business Hours",
        "content": "Regular hours Monday-Friday 8AM-6PM, Saturday 9AM-2PM. Emergency service available 24/7. After-hours calls are handled by our AI and dispatched to on-call technicians.",
        "category": "general",
    },
}

# ============================================================================
# EMERGENCY TRIAGE (Rule-based, no hallucination risk)
# ============================================================================

@dataclass
class EmergencyAnalysis:
    is_emergency: bool
    emergency_type: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    requires_evacuation: bool
    requires_911: bool
    dispatch_immediately: bool
    indoor_temp: Optional[int]
    vulnerable_occupants: bool
    confidence: float

def extract_temperature(text: str) -> Optional[int]:
    patterns = [r"(\d+)\s*degrees?", r"(\d+)\s*°[fF]", r"temp\w*\s+(?:is|at)\s+(\d+)", r"(\d+)\s+inside"]
    for p in patterns:
        m = re.search(p, text.lower())
        if m:
            t = int(m.group(1))
            if 30 <= t <= 130:
                return t
    return None

def detect_vulnerable(text: str) -> bool:
    tl = text.lower()
    if any(kw in tl for kw in ["elderly", "baby", "infant", "sick", "medical", "pregnant", "newborn", "disabled", "oxygen", "old mother", "old father", "senior", "child", "toddler"]):
        return True
    # Detect age mentions like "82 year old"
    import re as _re
    age_match = _re.search(r'(\d{1,3})\s*(?:year|yr)s?\s*old', tl)
    if age_match:
        age = int(age_match.group(1))
        if age >= 65 or age <= 5:
            return True
    # "6 month old baby", "3 month old"
    if _re.search(r'\d{1,2}\s*months?\s*old', tl):
        return True
    return False

def analyze_emergency(text: str) -> EmergencyAnalysis:
    tl = text.lower()
    temp = extract_temperature(text)
    vuln = detect_vulnerable(text)

    # Gas leak / CO - ALWAYS CRITICAL
    if any(k in tl for k in ["gas smell", "smell gas", "smells like gas", "gas leak", "gas odor",
                              "carbon monoxide", "co detector", "co alarm", "co2 detector"]):
        return EmergencyAnalysis(True, "gas_leak", "CRITICAL", True, True, False, temp, vuln, 0.99)

    # Electrical/fire hazard
    if any(k in tl for k in ["sparking", "sparks", "burning smell", "smoke", "electrical fire", "fire"]):
        return EmergencyAnalysis(True, "fire_hazard", "CRITICAL", True, True, False, temp, vuln, 0.98)

    # No heat
    if any(k in tl for k in ["no heat", "furnace not working", "heater broken", "heating stopped",
                              "heater stopped", "furnace stopped", "heater not working",
                              "furnace broke", "furnace broken", "furnace is broken",
                              "heater is broken", "heat stopped", "heat not",
                              "not heating", "no heating", "heating not working"]):
        critical = temp is not None and (temp < 50 or (temp < 60 and vuln))
        prio = "HIGH" if critical else "MEDIUM"
        return EmergencyAnalysis(True, "no_heat_critical" if critical else "no_heat", prio,
                                 False, False, critical, temp, vuln, 0.95 if critical else 0.85)

    # No AC
    if any(k in tl for k in ["no ac", "no air conditioning", "ac not working", "ac broken",
                              "ac is broken", "ac is out", "ac is dead", "not cooling"]):
        critical = temp is not None and (temp > 95 or (temp > 85 and vuln))
        prio = "HIGH" if critical else "MEDIUM"
        return EmergencyAnalysis(True, "no_ac_critical" if critical else "no_ac", prio,
                                 False, False, critical, temp, vuln, 0.95 if critical else 0.85)

    # Water leak from HVAC
    if any(k in tl for k in ["water leak", "flooding", "water damage"]):
        return EmergencyAnalysis(True, "water_leak", "MEDIUM", False, False, False, temp, vuln, 0.85)

    # Routine
    return EmergencyAnalysis(False, "routine", "LOW", False, False, False, temp, vuln, 0.90)

# ============================================================================
# SAFETY GUARDS
# ============================================================================

def check_prohibited(user_input: str) -> Tuple[bool, str]:
    il = user_input.lower()
    for pattern, response in PROHIBITED_PATTERNS.items():
        if pattern in il:
            return True, response
    return False, ""

def validate_response(response: str) -> Tuple[bool, str]:
    """Post-generation safety check on LLM output."""
    rl = response.lower()
    dangerous_keywords = [
        ("refrigerant", "I apologize, I can't provide refrigerant advice. Let me schedule a certified technician."),
        ("r-22", "I apologize, I can't provide refrigerant advice. Let me schedule a certified technician."),
        ("r-410a", "I apologize, I can't provide refrigerant advice. Let me schedule a certified technician."),
        ("you should replace", "I can't recommend specific parts. A technician will assess and provide options."),
        ("try turning", "For safety, please don't attempt repairs. I'll schedule a technician right away."),
    ]
    import re as _re
    dangerous_patterns = [
        (r"\b(?:i|my) (?:can |will )?diagnos", "I can't diagnose issues remotely. Let me schedule a technician to inspect your system."),
        (r"\byour (?:diagnosis|problem is)", "I can't diagnose issues remotely. Let me schedule a technician to inspect your system."),
        (r"\bthe diagnosis (?:shows?|indicates?|is\b)", "I can't diagnose issues remotely. Let me schedule a technician to inspect your system."),
    ]
    for keyword, safe_response in dangerous_keywords:
        if keyword in rl:
            return False, safe_response
    for pattern, safe_response in dangerous_patterns:
        if _re.search(pattern, rl):
            return False, safe_response
    return True, response

# ============================================================================
# RAG: Keyword Search (core) + pgvector (optional)
# ============================================================================

class RAGService:
    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.kb = DEFAULT_KNOWLEDGE_BASE

    async def retrieve(self, query: str, top_k: int = 3, company_id: str = None) -> List[Dict]:
        if USE_PGVECTOR and HAS_PG and self.db_pool:
            return await self._pgvector_search(query, top_k, company_id)
        return self._keyword_search(query, top_k)

    def _keyword_search(self, query: str, top_k: int) -> List[Dict]:
        import re as _re
        def tokenize(text):
            return set(_re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', text.lower()))
        qwords = tokenize(query)
        results = []
        for key, doc in self.kb.items():
            dwords = tokenize(doc["content"] + " " + doc["title"] + " " + key)
            score = len(qwords & dwords)
            if score > 0:
                results.append({"key": key, "title": doc["title"], "content": doc["content"],
                                "category": doc["category"], "score": score, "method": "keyword"})
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def _pgvector_search(self, query: str, top_k: int, company_id: str) -> List[Dict]:
        if not self.db_pool:
            return self._keyword_search(query, top_k)
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT doc_key, title, content, category FROM knowledge_documents "
                    "WHERE company_id = $1 AND is_active = TRUE "
                    "ORDER BY content <-> $2 LIMIT $3",
                    company_id, query, top_k,
                )
                return [{"key": r["doc_key"], "title": r["title"], "content": r["content"],
                         "category": r["category"], "score": 1.0, "method": "pgvector"} for r in rows]
        except Exception as e:
            logger.warning(f"pgvector failed, falling back: {e}")
            return self._keyword_search(query, top_k)

# ============================================================================
# LLM SERVICE: AssemblyAI Claude Haiku 4.5 + Mock Mode
# ============================================================================

class LLMService:
    """LLM via AssemblyAI LLM Gateway (Claude Haiku 4.5).
    Same pattern as hvac_voice.py AssemblyLLM class."""
    def __init__(self, api_key: str = "", mock: bool = False):
        self.api_key = api_key
        self.mock = mock or not api_key
        self.url = ASSEMBLYAI_LLM_URL
        self.model = ASSEMBLYAI_LLM_MODEL
        self._cache: Dict[str, Any] = {}

    async def generate(self, prompt: str, temperature: float = 0.1, max_tokens: int = 256) -> Dict:
        start = time.time()
        if self.mock:
            return self._mock_generate(prompt, start)

        cache_key = hashlib.md5(f"{prompt}:{temperature}".encode()).hexdigest()
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if time.time() - cached["ts"] < 600:
                return {**cached["resp"], "cached": True}

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
                            {"role": "system", "content": "You are a professional HVAC receptionist. Be helpful, warm, concise (2-3 sentences), and accurate. Never diagnose problems. Never give refrigerant advice. Never provide DIY instructions. For gas leaks or CO: always say evacuate and call 911. When asked about pricing, quote our standard rates from the provided knowledge. Always offer to schedule a technician."},
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
                conf = self._estimate_confidence(text)
                latency_ms = int((time.time() - start) * 1000)
                if HAS_PROM:
                    llm_latency.observe(latency_ms / 1000)
                result = {"text": text, "confidence": conf, "latency_ms": latency_ms,
                          "method": "assembly_llm", "model": self.model, "cached": False}
                self._cache[cache_key] = {"resp": result, "ts": time.time()}
                return result
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return {"text": "I'm having trouble right now. Let me connect you with our team.",
                    "confidence": 0.5, "latency_ms": int((time.time() - start) * 1000),
                    "method": "error", "error": str(e)}

    def _mock_generate(self, prompt: str, start: float) -> Dict:
        """Intelligent mock responses based on prompt content."""
        pl = prompt.lower()
        # Extract customer text to avoid false matches on RAG knowledge
        import re as _re
        cm = _re.search(r'customer said:\s*"([^"]*)"', pl)
        ct = cm.group(1) if cm else pl
        if ("gas leak" in ct or "gas smell" in ct or "smell gas" in ct or
            "carbon monoxide" in ct or "co detector" in ct or "co alarm" in ct):
            text = "This is a critical safety emergency. Please evacuate immediately and call 911. Do not touch any electrical switches. Once you're safe, we'll send an emergency technician right away."
        elif ("no heat" in ct or "heater stopped" in ct or "furnace stopped" in ct) and ("critical" in pl or "high" in pl):
            text = "I understand this is urgent. I'm scheduling an emergency technician for you right away. Can you confirm your address so we can dispatch the closest available tech?"
        elif "no heat" in ct or "furnace" in ct or "heater" in ct:
            text = "I'm sorry to hear about your heating issue. Let me get a technician scheduled for you as soon as possible. What's the best time for a service call?"
        elif "no ac" in ct or "not cooling" in ct or "ac broken" in ct:
            text = "I understand how uncomfortable that is. Let me schedule a technician to look at your cooling system. Do you prefer morning or afternoon?"
        elif "price" in ct or "cost" in ct or "how much" in ct:
            text = "Our service call fee is $89 (applied to repair). Tune-ups are $129. Common repairs: $150-$500. Would you like to schedule a visit?"
        elif "maintenance" in ct or "tune" in ct:
            text = "Great idea to schedule maintenance! Regular tune-ups are $129 and help prevent breakdowns. I can book you for next available. Would morning or afternoon work better?"
        elif "appointment" in ct or "schedule" in ct:
            text = "I'd be happy to help schedule an appointment. We have openings tomorrow morning and afternoon. Which would you prefer?"
        else:
            text = "Thank you for calling. I'd be happy to help you with your HVAC needs. Could you tell me more about what's going on so I can get the right technician scheduled?"

        return {"text": text, "confidence": 0.92, "latency_ms": int((time.time() - start) * 1000) + 50,
                "method": "mock", "cached": False}

    def _estimate_confidence(self, text: str) -> float:
        conf = 0.90
        tl = text.lower()
        for p in ["i think", "maybe", "possibly", "i'm not sure", "perhaps"]:
            if p in tl: conf -= 0.10
        for p in ["probably", "likely", "apparently", "seems"]:
            if p in tl: conf -= 0.05
        for p in ["i can", "i will", "let me", "i'll schedule", "right away"]:
            if p in tl: conf += 0.02
        return max(0.5, min(0.98, conf))

# ============================================================================
# TELNYX TELEPHONY: SMS + Mock Mode
# ============================================================================

class TelnyxService:
    def __init__(self, api_key: str, phone: str, mock: bool = False):
        self.api_key = api_key
        self.phone = phone
        self.mock = mock or not api_key
        self.base_url = "https://api.telnyx.com/v2"
        self.sent_messages: List[Dict] = []  # Track in mock mode

    async def send_sms(self, to: str, body: str) -> Dict:
        if self.mock:
            msg = {"id": f"mock_sms_{uuid.uuid4().hex[:8]}", "to": to, "body": body,
                   "status": "sent", "mock": True, "ts": datetime.now(timezone.utc).isoformat()}
            self.sent_messages.append(msg)
            logger.info(f"[MOCK SMS] To: {to} | Body: {body[:50]}...")
            return msg
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/messages",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"from": self.phone, "to": to, "text": body, "type": "SMS"},
                )
                return resp.json()
        except Exception as e:
            logger.error(f"Telnyx SMS error: {e}")
            return {"error": str(e)}

    async def handle_webhook(self, data: Dict) -> Dict:
        """Process Telnyx webhook for incoming calls/SMS."""
        event_type = data.get("data", {}).get("event_type", "")
        payload = data.get("data", {}).get("payload", {})
        logger.info(f"Telnyx webhook: {event_type}")
        return {"status": "received", "event_type": event_type}

# ============================================================================
# CONVERSATION ENGINE: Orchestrates STT → LLM → TTS flow
# ============================================================================

class ConversationEngine:
    def __init__(self, llm: LLMService, rag: RAGService, telnyx: TelnyxService):
        self.llm = llm
        self.rag = rag
        self.telnyx = telnyx
        self.conversations: Dict[str, List[Dict]] = {}

    async def process_message(self, text: str, session_id: str = None,
                              from_number: str = "", company_id: str = None) -> Dict:
        start = time.time()
        session_id = session_id or uuid.uuid4().hex
        calls_total.labels(status="received").inc()

        # Initialize conversation history
        if session_id not in self.conversations:
            self.conversations[session_id] = []

        # 1. Check prohibited
        is_prohibited, blocked_resp = check_prohibited(text)
        if is_prohibited:
            calls_total.labels(status="blocked").inc()
            return {"response": blocked_resp, "confidence": 1.0, "blocked": True,
                    "session_id": session_id, "emergency": asdict(EmergencyAnalysis(False, "routine", "LOW", False, False, False, None, False, 0.9)),
                    "rag_results": 0, "fallback_triggered": False, "sms_sent": False,
                    "latency_ms": int((time.time() - start) * 1000), "llm_method": "blocked"}

        # 2. Emergency triage (rule-based, zero hallucination risk)
        emergency = analyze_emergency(text)
        if emergency.is_emergency:
            emergency_total.labels(type=emergency.emergency_type).inc()

        # 3. RAG retrieval
        rag_results = await self.rag.retrieve(text, top_k=3, company_id=company_id)
        knowledge = "\n".join([r["content"] for r in rag_results]) if rag_results else "No specific knowledge found."

        # 4. Build conversation context
        history = self.conversations[session_id][-6:]  # Last 3 turns
        history_text = "\n".join([f"{'Customer' if h['role']=='user' else 'You'}: {h['text']}" for h in history])

        # 5. Build constrained prompt
        prompt = f"""You are a professional HVAC receptionist. Be helpful, warm, concise, and accurate.

CONVERSATION HISTORY:
{history_text}

CUSTOMER SAID: "{text}"

EMERGENCY STATUS: {emergency.emergency_type} (Priority: {emergency.priority})
{"⚠️ CRITICAL: " + ("Evacuate + call 911!" if emergency.requires_evacuation else "Dispatch immediately!") if emergency.priority in ("CRITICAL", "HIGH") else ""}

RELEVANT KNOWLEDGE:
{knowledge}

ABSOLUTE RULES (NEVER violate):
1. NEVER diagnose problems or recommend specific parts
2. NEVER give refrigerant/chemical advice (EPA violation = $37K fine)
3. NEVER provide DIY repair instructions
4. ONLY quote prices that appear in the RELEVANT KNOWLEDGE section above — NEVER invent prices
5. ALWAYS offer to schedule a certified technician
6. For gas leaks/CO: ALWAYS say evacuate + call 911 FIRST
7. Keep responses under 3 sentences
8. Be empathetic but efficient

YOUR RESPONSE (2-3 sentences max):"""

        # 6. Generate response
        llm_resp = await self.llm.generate(prompt, temperature=0.1, max_tokens=200)
        response_text = llm_resp["text"]
        confidence = llm_resp["confidence"]

        # 7. Post-generation safety validation
        is_safe, safe_text = validate_response(response_text)
        if not is_safe:
            response_text = safe_text
            confidence = 1.0  # Override with safe response

        # 8. Fallback logic
        fallback_triggered = False
        sms_sent = False
        if confidence < HUMAN_FALLBACK_THRESHOLD:
            response_text = "I want to make sure we help you properly. Let me connect you with our dispatch team right away."
            fallback_triggered = True
            calls_total.labels(status="fallback").inc()
        elif confidence < 0.95 and from_number:
            sms_result = await self.telnyx.send_sms(
                from_number,
                f"HVAC Service: We received your request. Reply CONFIRM or call {HUMAN_FALLBACK_NUMBER} for questions."
            )
            sms_sent = "error" not in sms_result

        # 9. Update conversation history
        self.conversations[session_id].append({"role": "user", "text": text, "ts": time.time()})
        self.conversations[session_id].append({"role": "assistant", "text": response_text, "ts": time.time()})

        total_ms = int((time.time() - start) * 1000)
        if HAS_PROM:
            e2e_latency.observe(total_ms / 1000)
        calls_total.labels(status="completed").inc()

        return {
            "response": response_text,
            "confidence": confidence,
            "session_id": session_id,
            "emergency": asdict(emergency),
            "rag_results": len(rag_results),
            "fallback_triggered": fallback_triggered,
            "sms_sent": sms_sent,
            "latency_ms": total_ms,
            "llm_method": llm_resp.get("method", "unknown"),
        }

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

db_pool = None
redis_client = None
rag_service = None
llm_service = None
telnyx_service = None
conversation_engine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, redis_client, rag_service, llm_service, telnyx_service, conversation_engine
    logger.info("Starting HVAC AI Receptionist v6.0...")

    # Database (optional)
    if HAS_PG and not MOCK_MODE:
        try:
            db_pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", "5432")),
                user=os.getenv("DB_USER", "hvac"),
                password=os.getenv("DB_PASSWORD", "hvac_pass"),
                database=os.getenv("DB_NAME", "hvac_ai"),
                min_size=2, max_size=10,
            )
            logger.info("PostgreSQL connected")
        except Exception as e:
            logger.warning(f"DB unavailable (running without): {e}")

    # Redis (optional — for session sharing and pub-sub)
    if HAS_REDIS and REDIS_URL:
        try:
            redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
            await redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis unavailable (running without): {e}")
            redis_client = None

    # Services
    rag_service = RAGService(db_pool)
    llm_service = LLMService(ASSEMBLYAI_API_KEY, mock=MOCK_MODE)
    telnyx_service = TelnyxService(TELNYX_API_KEY, TELNYX_PHONE, mock=MOCK_MODE)
    conversation_engine = ConversationEngine(llm_service, rag_service, telnyx_service)

    logger.info(f"Services ready | Mock={MOCK_MODE} | LLM={'mock' if llm_service.mock else 'assembly_llm'} | Redis={'yes' if redis_client else 'no'}")
    yield

    if redis_client:
        await redis_client.close()
    if db_pool:
        await db_pool.close()
    logger.info("Shutdown complete")

app = FastAPI(
    title="HVAC AI Receptionist v6.0",
    description="AI Receptionist + Smart Dispatch + Route Optimization + Emergency Triage + Voice Pipeline",
    version="6.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Auth integration (optional — graceful if hvac_auth not available)
try:
    from hvac_auth import (
        create_token, verify_token, extract_token_from_request,
        hash_password, verify_password, rate_limiter, sanitize_input,
        validate_phone, validate_email, audit_log, SECURITY_HEADERS
    )
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    logger.warning("hvac_auth module not found — running without auth")

# Security headers middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    response = await call_next(request)
    if HAS_AUTH:
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
    return response

# Voice pipeline integration (optional — graceful if not available)
try:
    from hvac_voice import register_voice_endpoints
    register_voice_endpoints(app)
    logger.info("Voice pipeline endpoints registered")
except ImportError:
    logger.warning("hvac_voice module not found — voice endpoints unavailable")

# Telnyx telephony integration (optional — graceful if not available)
try:
    from hvac_telnyx import register_telnyx_endpoints
    register_telnyx_endpoints(app)
    logger.info("Telnyx telephony endpoints registered")
except ImportError:
    logger.warning("hvac_telnyx module not found — telephony unavailable")

# CRM integration (optional — graceful if not available)
try:
    from hvac_crm import register_crm_endpoints
    register_crm_endpoints(app)
    logger.info("CRM endpoints registered")
except ImportError:
    logger.warning("hvac_crm module not found — CRM integration unavailable")

# LiveKit voice pipeline integration (optional — graceful if not available)
try:
    from hvac_livekit import register_livekit_endpoints
    register_livekit_endpoints(app)
    logger.info("LiveKit voice pipeline endpoints registered")
except ImportError:
    logger.warning("hvac_livekit module not found — LiveKit voice pipeline unavailable")

# Mount static files for web demo (MUST be after route registration)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "6.0.0",
        "mock_mode": MOCK_MODE,
        "toggles": {"pgvector": USE_PGVECTOR, "self_consistency": USE_SELF_CONS,
                     "graphhopper": bool(GRAPH_KEY), "epa": USE_EPA},
        "services": {
            "llm": "mock" if (llm_service and llm_service.mock) else "claude-haiku-4.5-assemblyai",
            "telephony": "mock" if (telnyx_service and telnyx_service.mock) else "telnyx",
            "rag": "pgvector" if USE_PGVECTOR else "keyword",
            "db": "connected" if db_pool else "unavailable",
            "redis": "connected" if redis_client else "unavailable",
        },
    }

@app.get("/metrics")
async def metrics():
    if HAS_PROM:
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    return {"message": "Install prometheus_client for metrics"}

# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

# In-memory user store (DB-backed in production)
_users_store: Dict[str, Dict] = {}

@app.post("/api/auth/signup")
async def signup(request: Request):
    """Create a new account."""
    if not HAS_AUTH:
        return JSONResponse({"error": "Auth module not available"}, 501)
    data = await request.json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    company_name = data.get("company_name", "").strip()

    if not email or not password or not company_name:
        raise HTTPException(400, "Missing email, password, or company_name")
    if not validate_email(email):
        raise HTTPException(400, "Invalid email format")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if email in _users_store:
        raise HTTPException(409, "Account already exists")

    company_id = f"comp_{uuid.uuid4().hex[:8]}"
    _users_store[email] = {
        "email": email,
        "password_hash": hash_password(password),
        "company_id": company_id,
        "company_name": company_name,
        "role": "owner",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    token = create_token(company_id, "owner", email)
    audit_log.log(company_id, email, "SIGNUP", company_name)
    logger.info(f"New signup: {email} → {company_id}")
    return {"token": token, "company_id": company_id, "company_name": company_name}

@app.post("/api/auth/login")
async def login(request: Request):
    """Login and get a JWT token."""
    if not HAS_AUTH:
        return JSONResponse({"error": "Auth module not available"}, 501)
    data = await request.json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = _users_store.get(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    # Rate limit login attempts
    allowed, info = rate_limiter.is_allowed(f"login:{email}")
    if not allowed:
        raise HTTPException(429, "Too many login attempts. Try again later.")

    token = create_token(user["company_id"], user["role"], email)
    audit_log.log(user["company_id"], email, "LOGIN", "")
    return {"token": token, "company_id": user["company_id"], "company_name": user["company_name"]}

@app.get("/api/auth/verify")
async def verify_auth(request: Request):
    """Verify a JWT token."""
    if not HAS_AUTH:
        return JSONResponse({"error": "Auth module not available"}, 501)
    token = extract_token_from_request(dict(request.headers))
    if not token:
        raise HTTPException(401, "Missing Authorization header")
    valid, payload = verify_token(token)
    if not valid:
        raise HTTPException(401, "Invalid or expired token")
    return {"valid": True, "company_id": payload["company_id"], "role": payload["role"]}

@app.get("/api/auth/audit")
async def get_audit(request: Request):
    """Get audit log for authenticated company."""
    if not HAS_AUTH:
        return JSONResponse({"error": "Auth module not available"}, 501)
    token = extract_token_from_request(dict(request.headers))
    if not token:
        raise HTTPException(401, "Missing token")
    valid, payload = verify_token(token)
    if not valid:
        raise HTTPException(401, "Invalid token")
    entries = audit_log.get_entries(payload["company_id"], limit=50)
    return {"entries": entries}

@app.post("/api/chat")
async def chat(request: Request):
    """Main chat endpoint - text in, text + metadata out."""
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Missing 'text' field")
    result = await conversation_engine.process_message(
        text=text,
        session_id=data.get("session_id"),
        from_number=data.get("from_number", ""),
        company_id=data.get("company_id"),
    )
    return result

@app.post("/api/telnyx/webhook")
async def telnyx_webhook(request: Request):
    """Telnyx webhook for incoming calls/SMS."""
    data = await request.json()
    return await telnyx_service.handle_webhook(data)

@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    """Get conversation history."""
    history = conversation_engine.conversations.get(session_id, [])
    return {"session_id": session_id, "messages": history, "count": len(history)}

@app.post("/api/emergency/analyze")
async def analyze_emergency_endpoint(request: Request):
    """Analyze text for emergency indicators."""
    data = await request.json()
    result = analyze_emergency(data.get("text", ""))
    return asdict(result)

# ============================================================================
# MOCK TESTING ENDPOINTS (only in mock mode)
# ============================================================================

@app.get("/api/mock/sms-log")
async def mock_sms_log():
    """View mock SMS messages sent (testing only)."""
    if not MOCK_MODE:
        raise HTTPException(403, "Only available in mock mode")
    return {"messages": telnyx_service.sent_messages}

@app.post("/api/mock/simulate-call")
async def mock_simulate_call(request: Request):
    """Simulate a full call flow for testing."""
    data = await request.json()
    scenarios = data.get("scenarios", [
        "My furnace stopped working and it's 45 degrees inside. I have an elderly parent.",
        "I smell gas in my basement!",
        "I'd like to schedule a maintenance tune-up.",
        "My AC is not cooling and it's 98 degrees. I have a baby.",
        "How much does a repair cost?",
    ])
    results = []
    for scenario in scenarios:
        result = await conversation_engine.process_message(text=scenario, session_id=f"test_{uuid.uuid4().hex[:6]}")
        results.append({"input": scenario, "output": result})
    return {"test_results": results, "count": len(results)}

# ============================================================================
# WEB VOICE DEMO
# ============================================================================

@app.get("/demo", response_class=HTMLResponse)
async def voice_demo():
    """Serve the web voice demo page."""
    demo_path = Path(__file__).parent / "static" / "web_demo.html"
    if demo_path.exists():
        return HTMLResponse(demo_path.read_text())
    # Inline fallback
    return HTMLResponse(_get_inline_demo_html())

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    """Sales landing page — client-facing."""
    lp = Path(__file__).parent / "static" / "landing.html"
    if lp.exists():
        return HTMLResponse(lp.read_text())
    return HTMLResponse("<h1>HVAC AI Receptionist</h1><p><a href='/demo'>Try Demo</a> | <a href='/docs'>API Docs</a></p>")

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket for real-time voice chat (text-based for web demo)."""
    await websocket.accept()
    session_id = uuid.uuid4().hex
    logger.info(f"WebSocket connected: {session_id}")
    try:
        while True:
            data = await websocket.receive_json()
            text = data.get("text", "")
            if text:
                result = await conversation_engine.process_message(text=text, session_id=session_id)
                await websocket.send_json(result)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")

# ============================================================================
# ONBOARDING PORTAL
# ============================================================================

@app.get("/onboard", response_class=HTMLResponse)
async def onboarding():
    return HTMLResponse(_get_onboard_html())

@app.post("/api/onboard")
async def process_onboard(request: Request):
    data = await request.json()
    required = ["company_name", "email", "city", "state", "business_number", "fallback_number"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return {"success": False, "error": f"Missing: {', '.join(missing)}"}
    company_id = f"comp_{int(time.time())}_{uuid.uuid4().hex[:4]}"
    logger.info(f"New onboard: {data.get('company_name')} ({company_id})")
    return {"success": True, "company_id": company_id,
            "next_steps": ["Add API keys to .env", "Start with: docker compose up -d"]}

# ============================================================================
# HTML TEMPLATES (inline for self-contained deployment)
# ============================================================================

def _get_inline_demo_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HVAC AI Receptionist - Voice Demo</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.container{max-width:500px;width:100%;padding:40px 20px;text-align:center}
h1{font-size:1.5rem;margin-bottom:8px;color:#38bdf8}
.subtitle{color:#94a3b8;margin-bottom:30px;font-size:0.9rem}
.chat-box{background:#1e293b;border-radius:16px;padding:20px;min-height:300px;max-height:400px;overflow-y:auto;margin-bottom:20px;text-align:left}
.msg{margin:10px 0;padding:10px 14px;border-radius:12px;max-width:85%;font-size:0.95rem;line-height:1.4}
.msg.user{background:#3b82f6;color:white;margin-left:auto}
.msg.ai{background:#334155;color:#e2e8f0}
.msg.system{background:#7c3aed22;color:#a78bfa;font-size:0.8rem;text-align:center;max-width:100%}
.msg .meta{font-size:0.7rem;color:#64748b;margin-top:4px}
.controls{display:flex;gap:10px;margin-bottom:15px}
.controls input{flex:1;padding:12px 16px;border-radius:12px;border:2px solid #334155;background:#1e293b;color:#e2e8f0;font-size:1rem}
.controls input:focus{outline:none;border-color:#3b82f6}
.btn{padding:12px 20px;border-radius:12px;border:none;font-size:1rem;cursor:pointer;font-weight:600;transition:all 0.2s}
.btn-send{background:#3b82f6;color:white}
.btn-send:hover{background:#2563eb}
.btn-mic{background:#10b981;color:white;width:50px}
.btn-mic.active{background:#ef4444;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.7}}
.status{color:#64748b;font-size:0.8rem;margin-top:10px}
.badge{display:inline-block;padding:2px 8px;border-radius:8px;font-size:0.7rem;font-weight:600}
.badge.emergency{background:#ef444433;color:#f87171}
.badge.mock{background:#f59e0b33;color:#fbbf24}
</style>
</head>
<body>
<div class="container">
<h1>🔧 HVAC AI Receptionist</h1>
<p class="subtitle">Speak or type your HVAC question <span class="badge mock">DEMO</span></p>
<div class="chat-box" id="chatBox">
<div class="msg ai">Hello! Thank you for calling. How can I help you with your heating or cooling needs today?</div>
</div>
<div class="controls">
<input type="text" id="msgInput" placeholder="Type your message or click mic..." onkeydown="if(event.key==='Enter')sendMsg()">
<button class="btn btn-mic" id="micBtn" onclick="toggleMic()">🎤</button>
<button class="btn btn-send" onclick="sendMsg()">Send</button>
</div>
<div class="status" id="status">Ready • Web Speech API for voice</div>
</div>
<script>
const chatBox=document.getElementById('chatBox');
const input=document.getElementById('msgInput');
const micBtn=document.getElementById('micBtn');
const status=document.getElementById('status');
let recognition=null;
let isListening=false;
let sessionId=null;

// Web Speech API for STT (free, browser-native)
if('webkitSpeechRecognition' in window||'SpeechRecognition' in window){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  recognition=new SR();
  recognition.continuous=false;
  recognition.interimResults=true;
  recognition.lang='en-US';
  recognition.onresult=(e)=>{
    const t=Array.from(e.results).map(r=>r[0].transcript).join('');
    input.value=t;
    if(e.results[0].isFinal){stopMic();sendMsg();}
  };
  recognition.onerror=(e)=>{status.textContent='Mic error: '+e.error;stopMic();};
  recognition.onend=()=>{if(isListening)stopMic();};
}

function toggleMic(){isListening?stopMic():startMic();}
function startMic(){
  if(!recognition){status.textContent='Speech recognition not supported in this browser';return;}
  recognition.start();isListening=true;
  micBtn.classList.add('active');micBtn.textContent='⏹';
  status.textContent='Listening...';
}
function stopMic(){
  if(recognition)try{recognition.stop();}catch(e){}
  isListening=false;micBtn.classList.remove('active');micBtn.textContent='🎤';
  status.textContent='Ready';
}

async function sendMsg(){
  const text=input.value.trim();
  if(!text)return;
  addMsg(text,'user');
  input.value='';
  status.textContent='Thinking...';
  try{
    const resp=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text,session_id:sessionId})
    });
    const data=await resp.json();
    sessionId=data.session_id;
    let meta=`${data.latency_ms}ms • ${data.llm_method}`;
    if(data.emergency?.is_emergency)meta+=' • <span class="badge emergency">'+data.emergency.priority+'</span>';
    addMsg(data.response,'ai',meta);
    // TTS via Web Speech API (free)
    if('speechSynthesis' in window){
      const u=new SpeechSynthesisUtterance(data.response);
      u.rate=1.0;u.pitch=1.0;speechSynthesis.speak(u);
    }
    status.textContent=`Ready • Session: ${sessionId.slice(0,8)}...`;
  }catch(e){
    addMsg('Connection error. Please try again.','system');
    status.textContent='Error: '+e.message;
  }
}

function addMsg(text,type,meta=''){
  const d=document.createElement('div');
  d.className='msg '+type;
  d.innerHTML=text+(meta?'<div class="meta">'+meta+'</div>':'');
  chatBox.appendChild(d);
  chatBox.scrollTop=chatBox.scrollHeight;
}
</script>
</body>
</html>"""

def _get_onboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HVAC AI Setup</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,sans-serif;max-width:700px;margin:0 auto;padding:20px;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh}
.c{background:#fff;border-radius:16px;padding:40px;box-shadow:0 20px 60px rgba(0,0,0,.3)}h1{color:#1a365d;margin-bottom:10px}
.sub{color:#4a5568;margin-bottom:30px}.s{background:#f7fafc;padding:25px;margin:20px 0;border-radius:12px;border-left:4px solid #4299e1}
label{display:block;margin:12px 0 4px;font-weight:600;color:#4a5568}
input{width:100%;padding:12px;border:2px solid #e2e8f0;border-radius:8px;font-size:16px}input:focus{outline:none;border-color:#4299e1}
button{background:linear-gradient(135deg,#4299e1,#3182ce);color:#fff;padding:16px;border:none;border-radius:8px;font-size:18px;width:100%;margin-top:20px;cursor:pointer;font-weight:600}
.ok{display:none;background:#c6f6d5;color:#22543d;padding:20px;border-radius:8px;margin-top:20px}
.err{display:none;background:#fed7d7;color:#742a2a;padding:20px;border-radius:8px;margin-top:20px}
</style></head><body><div class="c">
<h1>HVAC AI Receptionist Setup</h1><p class="sub">Get running in 10 minutes</p>
<form id="f"><div class="s"><h2>Company Info</h2>
<label>Company Name *</label><input name="company_name" required placeholder="ABC Heating">
<label>Email *</label><input type="email" name="email" required placeholder="you@company.com">
<label>City *</label><input name="city" required placeholder="Chicago">
<label>State (2 letters) *</label><input name="state" required placeholder="IL" maxlength="2">
</div><div class="s"><h2>Phone Config</h2>
<label>Business Phone *</label><input type="tel" name="business_number" required placeholder="+15551234567">
<label>Fallback Number *</label><input type="tel" name="fallback_number" required placeholder="+15559876543">
</div><button type="submit">Launch AI Receptionist</button></form>
<div class="ok" id="ok"><strong>Setup Complete!</strong> Check email for next steps.</div>
<div class="err" id="err"><strong>Error:</strong> <span id="et"></span></div>
</div><script>
document.getElementById('f').onsubmit=async(e)=>{e.preventDefault();
const d=Object.fromEntries(new FormData(e.target));
try{const r=await fetch('/api/onboard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
const j=await r.json();if(j.success){document.getElementById('ok').style.display='block';e.target.style.display='none';}
else{document.getElementById('et').textContent=j.error;document.getElementById('err').style.display='block';}}
catch(x){document.getElementById('et').textContent=x.message;document.getElementById('err').style.display='block';}};
</script></body></html>"""

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
