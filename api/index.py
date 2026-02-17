"""
HVAC AI Receptionist - Vercel Serverless Entry Point
"""
import sys
import os
# Add parent directory to path so we can import hvac_main
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvac_main import app



