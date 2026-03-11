#!/usr/bin/env python
"""Test Steel API key"""
from src.tools.steel import SteelClient

print("Testing Steel API key...")
client = SteelClient()
session = client.create_session()
print(f"✅ Steel API key WORKS!")
print(f"Session ID: {session['session_id']}")
client.close_session(session['session_id'])
print("✅ Session closed successfully")
