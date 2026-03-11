"""
ZRAI Lead OS - Backend Server Wrapper
Bridges supervisor config to the actual implementation
"""
import sys
import os

# Add parent directory to path so we can import from src/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the actual FastAPI app from src/api/server.py
from src.api.server import app

# Re-export for uvicorn
__all__ = ['app']
