"""
HVAC AI Receptionist - Vercel Serverless Entry Point
Simplified for serverless: no lifespan events, lazy initialization, comprehensive logging
"""
import os
import sys
import logging
import traceback
from datetime import datetime

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
logger.info("=" * 60)

# Minimal FastAPI app for serverless
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

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

# Log startup complete
logger.info("FastAPI app initialized successfully")
logger.info(f"Registered routes: {[r.path for r in app.routes]}")




