"""
HVAC AI Receptionist - Vercel Serverless Entry Point
Simplified for serverless: no lifespan events, lazy initialization, comprehensive logging
"""
import os
import sys
import logging
import traceback
import re
import uuid
import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

# Configure logging FIRST before any imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("hvac-vercel")

# Log startup
logger.info("=" * 60)
logger.info("HVAC AI Receptionist - Vercel Serverless Starting...")
logger.info(f"Python version: {sys.version}")
logger.info(f"MOCK_MODE: {os.getenv('MOCK_MODE', '1')}")
logger.info(f"ASSEMBLYAI_API_KEY set: {bool(os.getenv('ASSEMBLYAI_API_KEY'))}")
logger.info(f"TELNYX_API_KEY set: {bool(os.getenv('TELNYX_API_KEY'))}")
logger.info(f"LIVEKIT_API_KEY set: {bool(os.getenv('LIVEKIT_API_KEY'))}")
logger.info("=" * 60)

# Minimal FastAPI app for serverless
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="HVAC AI Receptionist",
    description="AI Receptionist for HVAC Contractors",
    version="6.0.0",
    # NO lifespan - serverless incompatible
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"UNHANDLED EXCEPTION: {type(exc).__name__} - {str(exc)}")
    logger.error(f"Request URL: {request.url}")
    logger.error(f"Request method: {request.method}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "type": type(exc).__name__,
            "detail": str(exc),
            "path": str(request.url)
        }
    )

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "hvac-ai-receptionist",
        "version": "6.0.0",
        "mock_mode": os.getenv("MOCK_MODE", "1") == "1",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "HVAC AI Receptionist",
        "version": "6.0.0",
        "endpoints": {
            "health": "/health",
            "voice": "/voice",
            "sms": "/sms",
            "dispatch": "/dispatch"
        }
    }

# Simple echo endpoint for testing
@app.post("/echo")
async def echo(request: Request):
    """Echo endpoint for testing"""
    try:
        data = await request.json()
        return {"echo": data, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"error": str(e)}

# Voice webhook endpoint (simplified for serverless)
@app.post("/voice")
async def voice_webhook(request: Request):
    """Handle incoming voice calls from Telnyx"""
    logger.info("Voice webhook received")
    try:
        form_data = await request.form()
        logger.info(f"Form data: {dict(form_data)}")
        
        # In MOCK_MODE, return a simple TwiML-like response
        if os.getenv("MOCK_MODE", "1") == "1":
            return PlainTextResponse(
                content='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you for calling HVAC AI Receptionist. This is a test response in mock mode.</Say></Response>',
                media_type="application/xml"
            )
        
        # Real mode would process the call
        return JSONResponse({"status": "received", "mode": "production"})
    except Exception as e:
        logger.error(f"Voice webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# SMS webhook endpoint
@app.post("/sms")
async def sms_webhook(request: Request):
    """Handle incoming SMS from Telnyx"""
    logger.info("SMS webhook received")
    try:
        form_data = await request.form()
        logger.info(f"SMS data: {dict(form_data)}")
        return JSONResponse({"status": "received"})
    except Exception as e:
        logger.error(f"SMS webhook error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Dispatch endpoint
@app.post("/dispatch")
async def dispatch(request: Request):
    """Handle dispatch requests"""
    logger.info("Dispatch request received")
    try:
        data = await request.json()
        logger.info(f"Dispatch data: {data}")
        
        # Mock response
        if os.getenv("MOCK_MODE", "1") == "1":
            return {
                "status": "dispatched",
                "technician": "John Doe",
                "eta_minutes": 45,
                "job_id": "JOB-001"
            }
        
        return JSONResponse({"status": "received", "mode": "production"})
    except Exception as e:
        logger.error(f"Dispatch error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================================
# LIVEKIT TOKEN ENDPOINT
# ============================================================================

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

@app.get("/api/livekit/health")
async def livekit_health():
    """Check LiveKit connection status."""
    return {
        "status": "ok" if LIVEKIT_URL else "not_configured",
        "livekit_url": LIVEKIT_URL[:30] + "..." if LIVEKIT_URL else None,
    }

@app.post("/api/livekit/token")
async def get_livekit_token(request: Request):
    """Generate LiveKit access token for client."""
    data = await request.json()
    room_name = data.get("room_name", f"demo-{int(time.time())}")
    participant_name = data.get("participant_name", "visitor")

    if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL]):
        return JSONResponse(
            {"error": "LiveKit not configured", "demo_mode": True},
            status_code=503
        )

    try:
        # Try to import livekit.api
        from livekit.api import AccessToken, VideoGrants

        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        token.with_identity(participant_name)
        token.with_name(participant_name)
        token.with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))

        return {"token": token.to_jwt(), "url": LIVEKIT_URL}
    except ImportError:
        logger.warning("livekit.api not installed, returning demo mode")
        return JSONResponse(
            {"error": "LiveKit SDK not installed", "demo_mode": True},
            status_code=503
        )
    except Exception as e:
        logger.error(f"Failed to generate LiveKit token: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# ============================================================================
# EMERGENCY TRIAGE (Rule-based, zero hallucination)
# ============================================================================

EMERGENCY_PATTERNS = {
    "critical": [
        r"\bgas\s*leak\b", r"\bsmell\s*gas\b", r"\bgas\s*smell\b",
        r"\bcarbon\s*monoxide\b", r"\bco\s*detector\b", r"\bco\s*alarm\b",
        r"\bfire\b", r"\bsmoke\b", r"\bexplosion\b", r"\bevacuate\b",
    ],
    "high": [
        r"\bno\s*heat\b", r"\bfurnace\s*stopped\b", r"\bfurnace\s*not\s*working\b",
        r"\bheater\s*down\b", r"\bno\s*hot\s*water\b", r"\bboiler\s*down\b",
        r"\bfrozen\s*pipes\b", r"\bpipe\s*burst\b",
    ],
    "vulnerable": [
        r"\belderly\b", r"\b(\d+)\s*(?:years?\s*)?old\b", r"\binfant\b",
        r"\bbaby\b", r"\bnewborn\b", r"\bdisabled\b", r"\bmedical\b",
    ],
    "temperature": [
        r"(\d+)\s*degrees?", r"(\d+)\s*°", r"(\d+)\s*f\b",
    ],
}

def detect_emergency(text: str) -> Dict[str, Any]:
    """Rule-based emergency detection."""
    text_lower = text.lower()
    result = {
        "is_emergency": False,
        "priority": "normal",
        "detected_issues": [],
        "vulnerable": False,
        "temperature": None,
    }

    # Check critical
    for pattern in EMERGENCY_PATTERNS["critical"]:
        if re.search(pattern, text_lower):
            result["is_emergency"] = True
            result["priority"] = "CRITICAL"
            result["detected_issues"].append("critical_safety")

    # Check high
    if result["priority"] != "CRITICAL":
        for pattern in EMERGENCY_PATTERNS["high"]:
            if re.search(pattern, text_lower):
                result["is_emergency"] = True
                result["priority"] = "HIGH"
                result["detected_issues"].append("no_heat")

    # Check vulnerable
    for pattern in EMERGENCY_PATTERNS["vulnerable"]:
        match = re.search(pattern, text_lower)
        if match:
            result["vulnerable"] = True
            if match.groups():
                try:
                    age = int(match.group(1))
                    if age >= 65 or age <= 1:
                        result["priority"] = "HIGH" if result["priority"] == "normal" else result["priority"]
                except:
                    pass

    # Check temperature
    for pattern in EMERGENCY_PATTERNS["temperature"]:
        match = re.search(pattern, text_lower)
        if match:
            try:
                temp = int(match.group(1))
                result["temperature"] = temp
                if temp <= 50 and result["priority"] == "normal":
                    result["priority"] = "HIGH"
            except:
                pass

    return result

# ============================================================================
# AI CHAT ENDPOINT
# ============================================================================

# Knowledge base for responses
KNOWLEDGE_BASE = {
    "pricing": {
        "service_call": "$89",
        "tune_up": "$129",
        "emergency": "$149.99",
        "new_unit": "$5,999 - $12,000 depending on size",
    },
    "services": [
        "AC repair and installation",
        "Furnace repair and installation",
        "Heat pump service",
        "Duct cleaning",
        "Maintenance tune-ups",
        "Emergency repairs 24/7",
    ],
    "hours": "24/7 emergency service, regular hours 7am-7pm",
    "contact": "Call us at (555) 123-4567",
}

# Session store for conversations
_sessions: Dict[str, List[Dict]] = {}

@app.post("/api/chat")
async def chat(request: Request):
    """Main chat endpoint for the landing page."""
    start_time = time.time()
    data = await request.json()
    text = data.get("text", "").strip()
    session_id = data.get("session_id")

    if not text:
        return {"response": "Hello! How can I help you today?", "session_id": session_id}

    # Create or get session
    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        _sessions[session_id] = []

    # Detect emergency
    emergency = detect_emergency(text)

    # Generate response
    response = generate_response(text, emergency)

    # Store in session
    _sessions[session_id].append({"role": "user", "text": text})
    _sessions[session_id].append({"role": "ai", "text": response})

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "response": response,
        "session_id": session_id,
        "emergency": emergency if emergency["is_emergency"] else None,
        "latency_ms": latency_ms,
    }

def generate_response(text: str, emergency: Dict) -> str:
    """Generate AI response based on input and emergency status."""
    text_lower = text.lower()

    # Emergency response
    if emergency["is_emergency"]:
        if emergency["priority"] == "CRITICAL":
            if "gas" in text_lower or "carbon monoxide" in text_lower or "co " in text_lower:
                return ("⚠️ EMERGENCY DETECTED: This sounds like a gas leak or CO emergency. " 
                       "Please evacuate everyone from the building immediately. "
                       "Do NOT use any electrical switches. Call 911 from outside the building. "
                       "I'm dispatching an emergency technician to you right now.")
            return ("⚠️ EMERGENCY DETECTED: This is a critical safety situation. "
                   "Please ensure everyone is safe. I'm dispatching emergency help now.")

        if emergency["priority"] == "HIGH":
            vuln_note = ""
            if emergency.get("vulnerable"):
                vuln_note = " I see there may be elderly or infant at home - we prioritize these calls."
            return (f"🔴 HIGH PRIORITY: No heat detected{vuln_note}. "
                   f"I'm scheduling an emergency repair right away. "
                   f"A technician can be there within 2 hours. Can you confirm your address?")

    # Pricing questions
    if "cost" in text_lower or "price" in text_lower or "how much" in text_lower:
        return (f"Our pricing: Service call: {KNOWLEDGE_BASE['pricing']['service_call']}, "
               f"Tune-up: {KNOWLEDGE_BASE['pricing']['tune_up']}, "
               f"Emergency visit: {KNOWLEDGE_BASE['pricing']['emergency']}. "
               f"Would you like to schedule an appointment?")

    # Scheduling
    if "schedule" in text_lower or "appointment" in text_lower or "book" in text_lower:
        return ("I'd be happy to help you schedule an appointment! We have availability "
               "tomorrow between 9am-12pm or 2pm-5pm. Which works better for you?")

    # Services
    if "service" in text_lower or "do you" in text_lower or "offer" in text_lower:
        services = ", ".join(KNOWLEDGE_BASE["services"][:4])
        return f"We offer: {services}, and more. How can I help you today?"

    # Hours
    if "hour" in text_lower or "open" in text_lower or "available" in text_lower:
        return f"Our hours: {KNOWLEDGE_BASE['hours']}. We're available for emergencies 24/7!"

    # Default greeting/help
    return ("Hello! I'm the HVAC AI Receptionist. I can help you with: "
           "scheduling appointments, pricing information, emergency repairs, "
           "or answering questions about our services. What do you need help with?")

# ============================================================================
# AUTH ENDPOINTS (Simplified)
# ============================================================================

_users_store: Dict[str, Dict] = {}

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))

@app.post("/api/auth/signup")
async def signup(request: Request):
    """Create a new account."""
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

    # Simple JWT-like token (in production use proper JWT)
    token = secrets.token_urlsafe(32)

    logger.info(f"New signup: {email} -> {company_id}")
    return {"token": token, "company_id": company_id, "company_name": company_name}

@app.post("/api/auth/login")
async def login(request: Request):
    """Login and get a token."""
    data = await request.json()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = _users_store.get(email)
    if not user or user["password_hash"] != hash_password(password):
        raise HTTPException(401, "Invalid email or password")

    token = secrets.token_urlsafe(32)
    return {"token": token, "company_id": user["company_id"], "company_name": user["company_name"]}

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

# Serve landing pages
@app.get("/", response_class=HTMLResponse)
async def root_html():
    """Serve the main landing page."""
    return HTMLResponse(content=get_landing_html(), status_code=200)

@app.get("/voice", response_class=HTMLResponse)
async def voice_demo():
    """Serve the voice demo landing page."""
    return HTMLResponse(content=get_voice_landing_html(), status_code=200)

def get_landing_html() -> str:
    """Read the main landing page HTML."""
    try:
        import pathlib
        static_dir = pathlib.Path(__file__).parent.parent / "static"
        landing_path = static_dir / "landing.html"
        if landing_path.exists():
            return landing_path.read_text()
    except Exception as e:
        logger.error(f"Failed to read landing.html: {e}")
    return "<html><body><h1>HVAC AI Receptionist</h1><p>Landing page not found.</p></body></html>"

def get_voice_landing_html() -> str:
    """Read the voice landing page HTML."""
    try:
        import pathlib
        static_dir = pathlib.Path(__file__).parent.parent / "static"
        voice_path = static_dir / "voice-landing.html"
        if voice_path.exists():
            return voice_path.read_text()
    except Exception as e:
        logger.error(f"Failed to read voice-landing.html: {e}")
    return "<html><body><h1>Voice Demo</h1><p>Voice landing page not found.</p></body></html>"

# Log startup complete
logger.info("FastAPI app initialized successfully")
logger.info(f"Registered routes: {[r.path for r in app.routes]}")




