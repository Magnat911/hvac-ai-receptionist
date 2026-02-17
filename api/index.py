"""
HVAC AI Receptionist - Vercel Serverless Entry Point
Exports FastAPI app for Vercel Python runtime (ASGI)
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hvac_main import app

