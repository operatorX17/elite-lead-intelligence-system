#!/usr/bin/env python3
"""Quick API endpoint test with proper initialization"""

import os
import sys

# Ensure we're in the right directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.server import app
from fastapi.testclient import TestClient

# Create test client
client = TestClient(app)

print('Testing API Endpoints...')
print('=' * 50)

# Test health endpoint
r = client.get('/health')
print(f'GET /health: {r.status_code} - {r.json()}')

# Test leads endpoint
r = client.get('/api/v1/leads?page=1&page_size=3')
if r.status_code == 200:
    data = r.json()
    leads = data.get('leads', [])
    print(f'GET /api/v1/leads: {r.status_code} - found {len(leads)} leads')
else:
    print(f'GET /api/v1/leads: {r.status_code} - {r.json()}')

# Test metrics endpoint
r = client.get('/api/v1/metrics')
if r.status_code == 200:
    print(f'GET /api/v1/metrics: {r.status_code} - OK')
else:
    print(f'GET /api/v1/metrics: {r.status_code} - {r.json()}')

# Test governance endpoint
r = client.get('/api/v1/governance')
if r.status_code == 200:
    data = r.json()
    print(f'GET /api/v1/governance: {r.status_code} - budget and kill switches loaded')
else:
    print(f'GET /api/v1/governance: {r.status_code} - {r.json()}')

# Test discover endpoint (mock mode for fast testing)
r = client.post('/api/v1/discover', json={
    'niche': 'restaurants',
    'geo': 'us',
    'limit': 5,
    'mock': True
})
if r.status_code == 200:
    data = r.json()
    print(f'POST /api/v1/discover (mock): {r.status_code} - discovered {data.get("count", 0)} leads')
else:
    print(f'POST /api/v1/discover (mock): {r.status_code} - {r.json()}')

print('=' * 50)
print('API Server Tests Complete!')
