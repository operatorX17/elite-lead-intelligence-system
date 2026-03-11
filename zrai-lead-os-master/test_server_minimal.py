"""Minimal test server to verify mock mode works"""
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import uuid4
import uvicorn

app = FastAPI()

class DiscoverRequest(BaseModel):
    niche: str
    geo: str = "us"
    limit: int = 50
    mock: bool = False

class LeadResponse(BaseModel):
    id: str
    company_name: str
    domain: Optional[str] = None
    niche: Optional[str] = None
    geo: Optional[str] = None
    status: str = "discovered"

class DiscoverResponse(BaseModel):
    leads: List[LeadResponse]
    count: int
    run_id: str

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/api/v1/discover", response_model=DiscoverResponse)
def discover_leads(request: DiscoverRequest):
    print(f"Request: niche={request.niche}, geo={request.geo}, limit={request.limit}, mock={request.mock}")
    
    if request.mock:
        print("Using MOCK mode - returning instant data")
        mock_leads = []
        for i in range(min(request.limit, 20)):
            mock_leads.append(LeadResponse(
                id=str(uuid4()),
                company_name=f"{request.niche.upper()} Company {i+1}",
                domain=f"company{i+1}.com",
                niche=request.niche,
                geo=request.geo,
                status="discovered",
            ))
        
        return DiscoverResponse(
            leads=mock_leads,
            count=len(mock_leads),
            run_id=str(uuid4()),
        )
    else:
        print("Using REAL mode - this would call Apify (simulating delay)")
        # Simulate what would happen - just return empty for now
        return DiscoverResponse(
            leads=[],
            count=0,
            run_id=str(uuid4()),
        )

if __name__ == "__main__":
    print("Starting minimal test server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
