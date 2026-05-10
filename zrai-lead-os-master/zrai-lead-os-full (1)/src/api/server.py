"""
ZRAI Lead OS - FastAPI Server

Exposes the LangGraph pipeline via REST API for the frontend.
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Request/Response Models
# ============================================================================

class DiscoverRequest(BaseModel):
    niche: str = Field(..., description="Industry niche to search")
    geo: str = Field(default="us", description="Geographic region")
    limit: int = Field(default=50, ge=1, le=200, description="Max leads to discover")

class LeadResponse(BaseModel):
    id: str
    company_name: str
    domain: Optional[str] = None
    niche: Optional[str] = None
    geo: Optional[str] = None
    status: str = "discovered"
    score: Optional[float] = None
    contacts: List[dict] = []
    intent_signals: List[dict] = []

class DiscoverResponse(BaseModel):
    leads: List[LeadResponse]
    count: int
    run_id: str

class EnrichRequest(BaseModel):
    lead_id: str

class IntentRequest(BaseModel):
    lead_id: str

class ProofRequest(BaseModel):
    lead_id: str
    proof_type: str = "screenshot"

class ScoreRequest(BaseModel):
    niche: Optional[str] = None
    geo: Optional[str] = None
    min_score: Optional[float] = None
    lead_ids: Optional[List[str]] = None

class OutreachRequest(BaseModel):
    lead_id: str
    channel: str = "email"
    action: str = "draft"
    message: Optional[str] = None

class ConversationRequest(BaseModel):
    lead_id: str
    message: str
    channel: Optional[str] = "email"

class RunPipelineRequest(BaseModel):
    mode: str = "full"
    config: Optional[dict] = None
    run_id: Optional[str] = None
    limit: Optional[int] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: dict

# ============================================================================
# Lifespan and App Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    logger.info("Starting ZRAI Lead OS API Server...")
    
    # Initialize agents and orchestrator
    try:
        from src.graph.orchestrator import LeadOrchestrator
        from src.agents.discovery import DiscoveryAgent
        from src.agents.enrichment import EnrichmentAgent
        from src.agents.intent import IntentAgent
        from src.agents.audit import AuditAgent
        from src.agents.scoring import ScoringAgent
        from src.agents.outreach import OutreachAgent
        from src.agents.conversation import ConversationAgent
        from src.agents.governance import GovernanceAgent
        from src.db.client import get_supabase_client
        
        app.state.orchestrator = LeadOrchestrator()
        app.state.discovery_agent = DiscoveryAgent()
        app.state.enrichment_agent = EnrichmentAgent()
        app.state.intent_agent = IntentAgent()
        app.state.audit_agent = AuditAgent()
        app.state.scoring_agent = ScoringAgent()
        app.state.outreach_agent = OutreachAgent()
        app.state.conversation_agent = ConversationAgent()
        app.state.governance_agent = GovernanceAgent()
        app.state.db = get_supabase_client()
        
        logger.info("All agents initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agents: {e}")
        import traceback
        traceback.print_exc()
        app.state.orchestrator = None
    
    yield
    
    logger.info("Shutting down ZRAI Lead OS API Server...")

app = FastAPI(
    title="ZRAI Lead OS API",
    description="REST API for the ZRAI Lead OS LangGraph pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Dependencies
# ============================================================================

async def get_user_id(x_user_id: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user ID from header."""
    return x_user_id

def get_db():
    """Get the database client."""
    if not hasattr(app.state, 'db') or app.state.db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return app.state.db

def get_discovery_agent():
    """Get the discovery agent."""
    if not hasattr(app.state, 'discovery_agent') or app.state.discovery_agent is None:
        raise HTTPException(status_code=503, detail="Discovery agent not initialized")
    return app.state.discovery_agent

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    agents_status = {
        "orchestrator": hasattr(app.state, 'orchestrator') and app.state.orchestrator is not None,
        "discovery": hasattr(app.state, 'discovery_agent') and app.state.discovery_agent is not None,
        "enrichment": hasattr(app.state, 'enrichment_agent') and app.state.enrichment_agent is not None,
        "scoring": hasattr(app.state, 'scoring_agent') and app.state.scoring_agent is not None,
    }
    return {
        "status": "healthy" if all(agents_status.values()) else "degraded",
        "service": "zrai-lead-os",
        "agents": agents_status,
    }

# ============================================================================
# Discovery Endpoint
# ============================================================================

@app.post("/api/v1/discover", response_model=DiscoverResponse)
async def discover_leads(
    request: DiscoverRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """
    Discover leads based on niche and geo.
    
    This endpoint triggers the Discovery Agent which uses Apify
    to scrape leads from various sources.
    """
    logger.info(f"Discovery request: niche={request.niche}, geo={request.geo}, limit={request.limit}")
    
    try:
        discovery_agent = get_discovery_agent()
        run_id = str(uuid4())
        
        # Run discovery in thread pool to not block
        loop = asyncio.get_event_loop()
        
        # Use Google Maps scraper for discovery
        leads = await loop.run_in_executor(
            None,
            lambda: discovery_agent.discover_from_google_maps(
                keywords=[request.niche],
                geo={"country": request.geo},
                limit=request.limit,
            )
        )
        
        # Convert leads to response format
        lead_responses = []
        for lead in leads:
            lead_responses.append(LeadResponse(
                id=str(lead.lead_id),
                company_name=lead.business_name,
                domain=lead.website,
                niche=request.niche,
                geo=lead.location or request.geo,
                status=lead.lead_lifecycle_state.value if hasattr(lead.lead_lifecycle_state, 'value') else str(lead.lead_lifecycle_state),
                score=None,
                contacts=[{"email": e} for e in (lead.emails_found or [])],
                intent_signals=[],
            ))
        
        return DiscoverResponse(
            leads=lead_responses,
            count=len(lead_responses),
            run_id=run_id,
        )
        
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Enrichment Endpoint
# ============================================================================

@app.post("/api/v1/enrich")
async def enrich_lead(
    request: EnrichRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Enrich a lead with additional data."""
    logger.info(f"Enrich request: lead_id={request.lead_id}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        enrichment_agent = app.state.enrichment_agent
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Create state and run enrichment
        state = LeadGraphState(
            lead_id=UUID(request.lead_id),
            current_stage="enrichment",
            last_node="discovery",
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: enrichment_agent(state))
        
        return {
            "success": True,
            "lead_id": request.lead_id,
            "enrichment": result_state.enrichment.model_dump() if result_state.enrichment else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrichment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Intent Analysis Endpoint
# ============================================================================

@app.post("/api/v1/intent")
async def analyze_intent(
    request: IntentRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Analyze intent signals for a lead."""
    logger.info(f"Intent request: lead_id={request.lead_id}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        intent_agent = app.state.intent_agent
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Create state and run intent analysis
        state = LeadGraphState(
            lead_id=UUID(request.lead_id),
            current_stage="intent",
            last_node="enrichment",
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: intent_agent(state))
        
        return {
            "success": True,
            "lead_id": request.lead_id,
            "intent": result_state.intent.model_dump() if result_state.intent else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intent analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Proof Generation Endpoint
# ============================================================================

@app.post("/api/v1/proof")
async def generate_proof(
    request: ProofRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Generate proof artifacts (screenshots, recordings)."""
    logger.info(f"Proof request: lead_id={request.lead_id}, type={request.proof_type}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        audit_agent = app.state.audit_agent
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Create state and run audit (proof generation)
        state = LeadGraphState(
            lead_id=UUID(request.lead_id),
            current_stage="audit",
            last_node="governance",
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: audit_agent(state))
        
        return {
            "success": True,
            "lead_id": request.lead_id,
            "proof": result_state.proof.model_dump() if result_state.proof else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Proof generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Scoring Endpoint
# ============================================================================

@app.post("/api/v1/score")
async def score_leads(
    request: ScoreRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Score leads based on intent, fit, and engagement."""
    logger.info(f"Score request: niche={request.niche}, geo={request.geo}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        scoring_agent = app.state.scoring_agent
        
        results = []
        
        # If specific lead_ids provided, score those
        if request.lead_ids:
            for lead_id in request.lead_ids:
                state = LeadGraphState(
                    lead_id=UUID(lead_id),
                    current_stage="scoring",
                    last_node="audit",
                )
                
                loop = asyncio.get_event_loop()
                result_state = await loop.run_in_executor(None, lambda: scoring_agent(state))
                
                if result_state.scoring:
                    results.append({
                        "lead_id": lead_id,
                        "score": result_state.scoring.total_score,
                        "tier": result_state.scoring.lead_tier,
                        "breakdown": result_state.scoring.model_dump(),
                    })
        else:
            # Get leads from database based on filters
            leads = db.get_leads(niche=request.niche, geo=request.geo, limit=100)
            for lead in leads:
                lead_id = lead.get("lead_id")
                if lead_id:
                    state = LeadGraphState(
                        lead_id=UUID(lead_id),
                        current_stage="scoring",
                        last_node="audit",
                    )
                    
                    loop = asyncio.get_event_loop()
                    result_state = await loop.run_in_executor(None, lambda: scoring_agent(state))
                    
                    if result_state.scoring:
                        results.append({
                            "lead_id": lead_id,
                            "score": result_state.scoring.total_score,
                            "tier": result_state.scoring.lead_tier,
                        })
        
        return {
            "success": True,
            "scored_leads": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Scoring error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Outreach Endpoint
# ============================================================================

@app.post("/api/v1/outreach")
async def handle_outreach(
    request: OutreachRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Draft or send outreach messages."""
    logger.info(f"Outreach request: lead_id={request.lead_id}, action={request.action}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        outreach_agent = app.state.outreach_agent
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Create state and run outreach
        state = LeadGraphState(
            lead_id=UUID(request.lead_id),
            current_stage="outreach",
            last_node="scoring",
            metadata={"channel": request.channel, "action": request.action},
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: outreach_agent(state))
        
        return {
            "success": True,
            "lead_id": request.lead_id,
            "outreach": result_state.outreach.model_dump() if result_state.outreach else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outreach error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Conversation Endpoint
# ============================================================================

@app.post("/api/v1/conversation")
async def handle_conversation(
    request: ConversationRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Handle conversation with a lead."""
    logger.info(f"Conversation request: lead_id={request.lead_id}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        conversation_agent = app.state.conversation_agent
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Create state and run conversation
        state = LeadGraphState(
            lead_id=UUID(request.lead_id),
            current_stage="conversation",
            last_node="outreach",
            metadata={"incoming_message": request.message, "channel": request.channel},
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: conversation_agent(state))
        
        return {
            "success": True,
            "lead_id": request.lead_id,
            "conversation": result_state.conversation.model_dump() if result_state.conversation else None,
            "response": result_state.conversation.transcript[-1] if result_state.conversation and result_state.conversation.transcript else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Governance Endpoint
# ============================================================================

@app.get("/api/v1/governance")
async def get_governance_status(
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get current governance status."""
    try:
        from src.config import load_config
        
        db = get_db()
        config = load_config()
        
        # Get current usage metrics
        today = datetime.utcnow()
        metrics = db.get_or_create_usage_metrics(today)
        
        # Get circuit breaker states
        circuit_breakers = {}
        for agent in ["discovery", "enrichment", "audit", "outreach"]:
            cb = db.get_circuit_breaker(agent)
            circuit_breakers[agent] = cb.get("state", "CLOSED") if cb else "CLOSED"
        
        return {
            "success": True,
            "budget": {
                "llm_tokens_used": metrics.get("llm_tokens_used", 0),
                "llm_tokens_limit": config.budget.daily_llm_token_limit,
                "browser_sessions_used": metrics.get("browser_sessions_used", 0),
                "browser_sessions_limit": config.budget.daily_browser_session_limit,
                "scraper_runs_used": metrics.get("scraper_runs_used", 0),
                "scraper_runs_limit": config.budget.daily_scraper_run_limit,
            },
            "circuit_breakers": circuit_breakers,
            "kill_switches": {
                "global": config.kill_switches.global_kill,
                "discovery": config.kill_switches.discovery_kill,
                "audit": config.kill_switches.audit_kill,
                "outreach": config.kill_switches.outreach_kill,
            },
        }
    except Exception as e:
        logger.error(f"Governance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Pipeline Run Endpoint
# ============================================================================

@app.post("/api/v1/run")
async def run_pipeline(
    request: RunPipelineRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Trigger a pipeline run."""
    logger.info(f"Pipeline run request: mode={request.mode}")
    
    try:
        from uuid import UUID
        
        orchestrator = app.state.orchestrator
        if not orchestrator:
            raise HTTPException(status_code=503, detail="Orchestrator not initialized")
        
        run_id = request.run_id or str(uuid4())
        
        # For full pipeline, we need leads to process
        db = get_db()
        
        if request.mode == "full":
            # Get unprocessed leads
            leads = db.get_leads(status="discovered", limit=request.limit or 10)
            
            results = []
            for lead in leads:
                lead_id = lead.get("lead_id")
                if lead_id:
                    try:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            lambda lid=lead_id: orchestrator.process_lead(UUID(lid))
                        )
                        results.append({
                            "lead_id": lead_id,
                            "status": "completed",
                            "stage": result.current_stage if result else "unknown",
                        })
                    except Exception as e:
                        results.append({
                            "lead_id": lead_id,
                            "status": "error",
                            "error": str(e),
                        })
            
            return {
                "success": True,
                "run_id": run_id,
                "mode": request.mode,
                "processed": len(results),
                "results": results,
            }
        
        elif request.mode == "dry_run":
            # Dry run mode - simulate without writes
            leads = db.get_leads(status="discovered", limit=request.limit or 5)
            
            results = []
            for lead in leads:
                lead_id = lead.get("lead_id")
                if lead_id:
                    try:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            lambda lid=lead_id: orchestrator.dry_run(UUID(lid))
                        )
                        results.append({
                            "lead_id": lead_id,
                            "status": "simulated",
                            "stage": result.current_stage if result else "unknown",
                        })
                    except Exception as e:
                        results.append({
                            "lead_id": lead_id,
                            "status": "error",
                            "error": str(e),
                        })
            
            return {
                "success": True,
                "run_id": run_id,
                "mode": request.mode,
                "processed": len(results),
                "results": results,
            }
        
        else:
            return {
                "success": True,
                "run_id": run_id,
                "mode": request.mode,
                "message": f"Mode '{request.mode}' acknowledged",
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Leads Endpoint
# ============================================================================

@app.get("/api/v1/leads")
async def get_leads(
    page: int = 1,
    page_size: int = 20,
    niche: Optional[str] = None,
    geo: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get paginated list of leads."""
    try:
        db = get_db()
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get leads from database
        leads = db.get_leads(
            niche=niche,
            geo=geo,
            status=status,
            min_score=min_score,
            limit=page_size,
            offset=offset,
        )
        
        # Get total count
        total = db.count_leads(niche=niche, geo=geo, status=status, min_score=min_score)
        
        return {
            "success": True,
            "leads": leads,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }
    except Exception as e:
        logger.error(f"Get leads error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/leads/{lead_id}")
async def get_lead(
    lead_id: str,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get a single lead by ID."""
    try:
        db = get_db()
        lead = db.get_lead(lead_id)
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        return {"success": True, "lead": lead}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get lead error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Metrics Endpoint
# ============================================================================

@app.get("/api/v1/metrics")
async def get_metrics(
    period: str = "daily",
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get system metrics."""
    try:
        db = get_db()
        
        # Get current usage metrics
        today = datetime.utcnow()
        metrics = db.get_or_create_usage_metrics(today)
        
        # Get lead counts by status
        lead_counts = db.get_lead_counts_by_status()
        
        # Get recent activity
        recent_leads = db.get_leads(limit=5)
        
        return {
            "success": True,
            "period": period,
            "usage": {
                "llm_calls": metrics.get("llm_calls_used", 0),
                "browser_sessions": metrics.get("browser_sessions_used", 0),
                "scraper_calls": metrics.get("scraper_calls_used", 0),
                "emails_sent": metrics.get("emails_sent", 0),
            },
            "leads": {
                "total": sum(lead_counts.values()) if lead_counts else 0,
                "by_status": lead_counts or {},
            },
            "recent_activity": [
                {
                    "lead_id": l.get("lead_id"),
                    "business_name": l.get("business_name"),
                    "status": l.get("lead_lifecycle_state"),
                    "updated_at": l.get("updated_at"),
                }
                for l in recent_leads
            ],
        }
    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
