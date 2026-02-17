"""
HVAC AI Receptionist - Vercel Serverless Entry Point
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mangum import Mangum
from hvac_main import app

handler = Mangum(app, lifespan="off")
