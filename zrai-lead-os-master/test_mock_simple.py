"""Simple test for mock discover - runs inline without server"""
import sys
sys.path.insert(0, '.')

from uuid import uuid4

# Simulate mock response
niche = "saas"
geo = "us"
limit = 5

mock_leads = []
for i in range(min(limit, 20)):
    mock_leads.append({
        "id": str(uuid4()),
        "company_name": f"{niche.upper()} Company {i+1}",
        "domain": f"company{i+1}.com",
        "niche": niche,
        "geo": geo,
        "status": "discovered",
        "score": None,
        "contacts": [{"email": f"contact{i+1}@company{i+1}.com"}],
        "intent_signals": [],
    })

print("Mock leads generated successfully!")
print(f"Count: {len(mock_leads)}")
for lead in mock_leads:
    print(f"  - {lead['company_name']} ({lead['domain']})")
