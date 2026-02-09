#!/usr/bin/env python3
"""
ZRAI Intelligence API Server
RESTful API for Lead Intelligence Engine

Endpoints:
- POST /api/discover - Discover businesses in a niche/city
- POST /api/enrich - Enrich a single lead
- POST /api/analyze - Full intelligence analysis
- GET /api/leads - Get processed leads
- GET /api/health - Health check
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from dotenv import load_dotenv
load_dotenv('.env')

# Import intelligence engine
from ULTIMATE_INTELLIGENCE import (
    UltimateIntelligenceEngine,
    BusinessLead,
    LeadTier,
    PriorityLevel
)


# =============================================================================
# MODELS
# =============================================================================

class DiscoverRequest(BaseModel):
    niche: str = Field(..., description="Business category", example="diagnostic center")
    city: str = Field(..., description="Target city", example="Bangalore")
    country: str = Field(default="India", description="Target country")
    limit: int = Field(default=10, ge=1, le=50, description="Max results")


class DiscoverResponse(BaseModel):
    success: bool
    run_id: str
    discovered: int
    processed: int
    hot: int
    warm: int
    cold: int
    total_opportunity_inr: int
    leads: List[Dict[str, Any]]


class EnrichRequest(BaseModel):
    business_name: str
    website: Optional[str] = None
    phone: Optional[str] = None
    category: str = "general"
    city: str = "Unknown"


class AnalyzeRequest(BaseModel):
    niche: str
    city: str
    country: str = "India"
    target: int = Field(default=10, ge=1, le=100)


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    apis: Dict[str, bool]


# =============================================================================
# APP SETUP
# =============================================================================

# Initialize engine on startup
engine: Optional[UltimateIntelligenceEngine] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    print("🚀 Starting ZRAI Intelligence API...")
    engine = UltimateIntelligenceEngine()
    yield
    print("👋 Shutting down ZRAI Intelligence API...")

app = FastAPI(
    title="ZRAI Intelligence API",
    description="Lead Intelligence Engine API - Discover, Enrich, Analyze",
    version="4.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ROUTES
# =============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        apis={
            "apify": bool(os.environ.get("APIFY_API_TOKEN")),
            "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
            "firecrawl": bool(os.environ.get("FIRECRAWL_API_KEY")),
            "steel": bool(os.environ.get("STEEL_API_KEY")),
        }
    )


@app.post("/api/discover", response_model=DiscoverResponse)
async def discover_businesses(request: DiscoverRequest):
    """
    Discover and analyze businesses.
    
    Full intelligence pipeline:
    1. Discover via Apify Google Maps
    2. Deep enrich with Firecrawl/Steel
    3. AI analysis with OpenRouter
    4. Revenue calculation
    5. Outreach generation
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        report = engine.run(
            niche=request.niche,
            city=request.city,
            country=request.country,
            target=request.limit
        )
        
        if report.get("error"):
            raise HTTPException(status_code=500, detail=report["error"])
        
        summary = report.get("summary", {})
        
        return DiscoverResponse(
            success=True,
            run_id=report.get("run_id", ""),
            discovered=summary.get("discovered", 0),
            processed=summary.get("processed", 0),
            hot=summary.get("hot", 0),
            warm=summary.get("warm", 0),
            cold=summary.get("cold", 0),
            total_opportunity_inr=summary.get("total_opportunity_inr", 0),
            leads=report.get("leads", [])
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/enrich")
async def enrich_lead(request: EnrichRequest):
    """
    Enrich a single lead with deep intelligence.
    """
    if not engine:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    
    try:
        # Create raw data structure
        raw_data = {
            "title": request.business_name,
            "website": request.website,
            "phone": request.phone,
        }
        
        lead = engine.process_lead(raw_data, request.category, request.city)
        
        if not lead:
            return {"success": False, "error": "Lead rejected during processing"}
        
        return {
            "success": True,
            "lead": lead.to_dict()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/leads")
async def get_leads(
    city: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 50
):
    """
    Get processed leads from output directory.
    """
    output_dir = Path("output")
    all_leads = []
    
    # Find all leads.json files
    for leads_file in output_dir.glob("*/leads.json"):
        try:
            with open(leads_file) as f:
                leads = json.load(f)
                all_leads.extend(leads)
        except:
            pass
    
    # Filter
    if city:
        all_leads = [l for l in all_leads if l.get("city", "").lower() == city.lower()]
    if tier:
        all_leads = [l for l in all_leads if l.get("tier", "").upper() == tier.upper()]
    
    # Sort by score
    all_leads.sort(key=lambda x: -x.get("final_score", 0))
    
    return {
        "total": len(all_leads),
        "leads": all_leads[:limit]
    }


@app.get("/api/stats")
async def get_stats():
    """
    Get overall intelligence stats.
    """
    output_dir = Path("output")
    
    total_leads = 0
    hot = 0
    warm = 0
    cold = 0
    total_opportunity = 0
    cities = set()
    niches = set()
    
    for leads_file in output_dir.glob("*/leads.json"):
        try:
            with open(leads_file) as f:
                leads = json.load(f)
                for lead in leads:
                    total_leads += 1
                    tier = lead.get("tier", "COLD").upper()
                    if tier == "HOT":
                        hot += 1
                    elif tier == "WARM":
                        warm += 1
                    else:
                        cold += 1
                    total_opportunity += lead.get("estimated_revenue_loss_inr", 0)
                    cities.add(lead.get("city", ""))
                    niches.add(lead.get("category", ""))
        except:
            pass
    
    return {
        "total_leads": total_leads,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "total_opportunity_inr": total_opportunity,
        "total_opportunity_annual_inr": total_opportunity * 12,
        "cities": list(cities),
        "niches": list(niches),
    }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
