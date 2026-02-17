"""
HVAC AI Receptionist - Vercel Serverless Entry Point
"""

from mangum import Mangum
from hvac_main import app

handler = Mangum(app, lifespan="off")
