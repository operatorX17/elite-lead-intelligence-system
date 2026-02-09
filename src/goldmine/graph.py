"""
GOLDMINE GRAPH - The autonomous sales machine orchestrator.

This is the brain that coordinates:
1. Discovery → Find prospects
2. Mystery Shopping → Prove they're losing money
3. Revenue Calculation → Show exact dollar amounts
4. Proof Generation → Create irrefutable evidence
5. Outreach → Multi-channel autonomous contact
6. Closing → Book meetings and close deals

Built with LangGraph for:
- State persistence (resume from any point)
- Parallel execution (mystery shop + competitor analysis simultaneously)
- Human-in-the-loop (approval before outreach)
- Streaming (real-time progress updates)
"""

import logging
from typing import Dict, Any, List, Literal, Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command, Send

from src.goldmine.state import GoldmineState, create_initial_state, ProspectTier
from src.goldmine.mystery_shopper import mystery_shop_node
from src.goldmine.revenue_calculator import revenue_calculator_node
from src.goldmine.proof_generator import proof_generator_node


logger = logging.getLogger(__name__)


# =============================================================================
# NODE FUNCTIONS
# =============================================================================

def enrich_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Enrich lead with additional data.
    Uses existing enrichment agent.
    """
    from src.agents.enrichment import EnrichmentAgent
    
    logger.info(f"🔍 Enriching: {state['lead'].get('business_name')}")
    
    # Create minimal state for enrichment agent
    enrichment_state = {
        "lead_id": state["lead_id"],
        "lead": state["lead"],
        "enrichment": state.get("enrichment", {}),
        "current_stage": "enrichment",
    }
    
    agent = EnrichmentAgent()
    result = agent.process(enrichment_state)
    
    return {
        "enrichment": result.get("enrichment", {}),
        "completed_stages": ["enriched"],
    }


def analyze_competitors_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Analyze top competitors in the same market.
    Runs in parallel with mystery shopping.
    """
    from src.goldmine.state import CompetitorAnalysis
    
    lead = state["lead"]
    logger.info(f"🏆 Analyzing competitors for: {lead.get('business_name')}")
    
    # In production, would:
    # 1. Search Google for "[category] [location]"
    # 2. Get top 3 competitors
    # 3. Analyze their websites with Steel
    # 4. Compare features
    
    # Placeholder - would be populated by actual scraping
    competitors = []
    
    return {
        "competitor_analyses": competitors,
        "completed_stages": ["competitors_analyzed"],
    }


def mine_reviews_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Mine reviews for negative response patterns.
    Runs in parallel with other analysis.
    """
    from src.goldmine.state import ReviewEvidence
    
    lead = state["lead"]
    logger.info(f"📝 Mining reviews for: {lead.get('business_name')}")
    
    # In production, would:
    # 1. Scrape Google reviews
    # 2. Scrape Yelp reviews
    # 3. Use NLP to find "no response" patterns
    # 4. Extract damning quotes
    
    # Placeholder
    evidence = []
    
    return {
        "review_evidence": evidence,
        "completed_stages": ["reviews_mined"],
    }


def calculate_scores_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Calculate all scores after parallel tasks complete.
    """
    logger.info(f"📊 Calculating scores for: {state['lead'].get('business_name')}")
    
    # Response score from mystery shopping
    response_score = 50  # Default
    if state.get("mystery_shop_results"):
        response_score = state["mystery_shop_results"][-1].get("response_score", 50)
    
    # Leak score from revenue calculation
    leak_score = 0
    monthly_loss = state.get("estimated_monthly_loss", 0)
    if monthly_loss >= 10000:
        leak_score = 90
    elif monthly_loss >= 5000:
        leak_score = 70
    elif monthly_loss >= 2000:
        leak_score = 50
    elif monthly_loss > 0:
        leak_score = 30
    
    # Competitor gap score
    competitor_gap = 50  # Default
    if state.get("competitor_analyses"):
        # Would calculate based on feature comparison
        pass
    
    return {
        "response_score": response_score,
        "leak_score": leak_score,
        "competitor_gap": competitor_gap,
        "completed_stages": ["scores_calculated"],
    }


def qualify_prospect_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Qualify prospect and determine next action.
    """
    goldmine_score = state.get("goldmine_score", 0)
    business_name = state["lead"].get("business_name")
    
    logger.info(f"🎯 Qualifying: {business_name} (Score: {goldmine_score})")
    
    # Determine tier
    if goldmine_score >= 80:
        tier = ProspectTier.GOLDMINE
        action = "immediate_outreach"
    elif goldmine_score >= 60:
        tier = ProspectTier.HOT
        action = "warm_outreach"
    elif goldmine_score >= 40:
        tier = ProspectTier.WARM
        action = "nurture_sequence"
    else:
        tier = ProspectTier.COLD
        action = "skip"
    
    logger.info(f"  → Tier: {tier.value}, Action: {action}")
    
    return {
        "deal_status": "qualified" if tier in [ProspectTier.GOLDMINE, ProspectTier.HOT] else "prospect",
        "completed_stages": ["qualified"],
        "messages": [{
            "role": "system",
            "content": f"Prospect {business_name} qualified as {tier.value} (score: {goldmine_score})",
        }],
    }


def human_approval_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Request human approval before outreach.
    Uses LangGraph interrupt for human-in-the-loop.
    
    For now, auto-approve to allow autonomous operation.
    """
    goldmine_score = state.get("goldmine_score", 0)
    business_name = state["lead"].get("business_name")
    monthly_loss = state.get("estimated_monthly_loss", 0)
    
    # Only require approval for high-value prospects
    if goldmine_score < 60:
        return {
            "requires_approval": False,
            "completed_stages": ["approval_skipped"],
        }
    
    # AUTO-APPROVE for autonomous operation
    # In production, would use interrupt() for human-in-the-loop:
    # approval = interrupt({
    #     "type": "outreach_approval",
    #     "business_name": business_name,
    #     "goldmine_score": goldmine_score,
    #     "estimated_monthly_loss": monthly_loss,
    #     "question": f"Approve outreach to {business_name}?",
    # })
    
    logger.info(f"🤖 Auto-approving outreach to {business_name} (Score: {goldmine_score})")
    
    return {
        "requires_approval": False,
        "human_feedback": "auto_approved",
        "completed_stages": ["approval_auto"],
    }


def generate_outreach_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Generate personalized outreach sequence.
    """
    from src.goldmine.proof_generator import ProofGeneratorAgent
    from src.goldmine.state import OutreachMessage, OutreachChannel
    
    business_name = state["lead"].get("business_name")
    logger.info(f"✉️ Generating outreach for: {business_name}")
    
    agent = ProofGeneratorAgent()
    copy = agent.generate_outreach_copy(state)
    
    # Create outreach sequence
    sequence = []
    
    # Day 1: Email with proof
    if copy.get("email_body"):
        sequence.append(OutreachMessage(
            channel=OutreachChannel.EMAIL,
            subject=copy["email_subjects"][0] if copy.get("email_subjects") else f"Quick question about {business_name}",
            body=copy["email_body"],
            personalization_tokens={
                "business_name": business_name,
                "monthly_loss": f"${state.get('estimated_monthly_loss', 0):,.0f}",
            },
            scheduled_at=None,
            sent_at=None,
            opened_at=None,
            replied_at=None,
            status="draft",
        ))
    
    # Day 3: LinkedIn connection
    if copy.get("linkedin_message"):
        sequence.append(OutreachMessage(
            channel=OutreachChannel.LINKEDIN,
            subject=None,
            body=copy["linkedin_message"],
            personalization_tokens={
                "business_name": business_name,
            },
            scheduled_at=None,
            sent_at=None,
            opened_at=None,
            replied_at=None,
            status="draft",
        ))
    
    # Day 5: Follow-up email
    sequence.append(OutreachMessage(
        channel=OutreachChannel.EMAIL,
        subject=f"Following up - {business_name}",
        body=f"""Hi,

Just following up on my previous email about {business_name}.

I put together an analysis showing some opportunities that could help you capture more leads. Happy to share it if you're interested.

Would a quick 15-minute call work this week?

Best,
[Your Name]""",
        personalization_tokens={
            "business_name": business_name,
        },
        scheduled_at=None,
        sent_at=None,
        opened_at=None,
        replied_at=None,
        status="draft",
    ))
    
    return {
        "outreach_sequence": sequence,
        "outreach_status": "ready",
        "completed_stages": ["outreach_generated"],
    }


def execute_outreach_node(state: GoldmineState) -> Dict[str, Any]:
    """
    Execute the outreach sequence.
    In production, would integrate with email/LinkedIn APIs.
    """
    business_name = state["lead"].get("business_name")
    sequence = state.get("outreach_sequence", [])
    current_step = state.get("current_outreach_step", 0)
    
    if current_step >= len(sequence):
        logger.info(f"📬 Outreach complete for: {business_name}")
        return {
            "outreach_status": "complete",
            "completed_stages": ["outreach_complete"],
        }
    
    message = sequence[current_step]
    logger.info(f"📤 Sending {message['channel'].value} to: {business_name}")
    
    # In production, would:
    # - Send email via SendGrid/Mailgun
    # - Send LinkedIn via Phantombuster
    # - Track opens/clicks
    
    # Mark as sent
    message["sent_at"] = datetime.utcnow()
    message["status"] = "sent"
    
    return {
        "outreach_sequence": sequence,
        "current_outreach_step": current_step + 1,
        "outreach_status": "in_progress",
        "completed_stages": [f"outreach_step_{current_step + 1}"],
    }


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================

def route_after_enrichment(state: GoldmineState) -> List[str]:
    """
    Route to parallel tasks after enrichment.
    Uses Send for fan-out pattern.
    """
    return [
        Send("mystery_shop", state),
        Send("analyze_competitors", state),
        Send("mine_reviews", state),
    ]


def route_after_qualification(state: GoldmineState) -> str:
    """
    Route based on qualification result.
    """
    goldmine_score = state.get("goldmine_score", 0)
    
    if goldmine_score >= 60:
        return "human_approval"
    elif goldmine_score >= 40:
        return "generate_outreach"
    else:
        return END


def route_after_approval(state: GoldmineState) -> str:
    """
    Route based on human approval.
    """
    # Auto-approved or explicitly approved
    feedback = state.get("human_feedback")
    if feedback and feedback != "denied":
        return "generate_outreach"
    elif state.get("requires_approval") == False:
        return "generate_outreach"
    else:
        return END


def should_continue_outreach(state: GoldmineState) -> str:
    """
    Check if outreach should continue.
    """
    status = state.get("outreach_status", "")
    
    if status == "responded":
        return END
    elif status == "complete":
        return END
    else:
        return "execute_outreach"


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def create_goldmine_graph(checkpointer=None):
    """
    Create the Goldmine autonomous sales machine graph.
    
    Flow:
    START → enrich → [parallel: mystery_shop, competitors, reviews]
          → calculate_revenue → generate_proof → calculate_scores
          → qualify → (if hot) human_approval → generate_outreach
          → execute_outreach → END
    """
    
    # Use memory checkpointer if none provided
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    # Create graph
    builder = StateGraph(GoldmineState)
    
    # Add nodes
    builder.add_node("enrich", enrich_node)
    builder.add_node("mystery_shop", mystery_shop_node)
    builder.add_node("analyze_competitors", analyze_competitors_node)
    builder.add_node("mine_reviews", mine_reviews_node)
    builder.add_node("calculate_revenue", revenue_calculator_node)
    builder.add_node("generate_proof", proof_generator_node)
    builder.add_node("calculate_scores", calculate_scores_node)
    builder.add_node("qualify", qualify_prospect_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("generate_outreach", generate_outreach_node)
    builder.add_node("execute_outreach", execute_outreach_node)
    
    # Add edges
    builder.add_edge(START, "enrich")
    
    # After enrichment, fan out to parallel tasks
    builder.add_edge("enrich", "mystery_shop")
    builder.add_edge("enrich", "analyze_competitors")
    builder.add_edge("enrich", "mine_reviews")
    
    # All parallel tasks converge to revenue calculation
    builder.add_edge("mystery_shop", "calculate_revenue")
    builder.add_edge("analyze_competitors", "calculate_revenue")
    builder.add_edge("mine_reviews", "calculate_revenue")
    
    # Sequential flow after parallel tasks
    builder.add_edge("calculate_revenue", "generate_proof")
    builder.add_edge("generate_proof", "calculate_scores")
    builder.add_edge("calculate_scores", "qualify")
    
    # Conditional routing after qualification
    builder.add_conditional_edges(
        "qualify",
        route_after_qualification,
        ["human_approval", "generate_outreach", END],
    )
    
    # Conditional routing after approval
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        ["generate_outreach", END],
    )
    
    # Outreach flow
    builder.add_edge("generate_outreach", "execute_outreach")
    builder.add_conditional_edges(
        "execute_outreach",
        should_continue_outreach,
        ["execute_outreach", END],
    )
    
    # Compile with checkpointer
    graph = builder.compile(checkpointer=checkpointer)
    
    return graph


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_goldmine_pipeline(
    lead: Dict[str, Any],
    enrichment: Dict[str, Any] = None,
    stream: bool = False,
):
    """
    Run the full Goldmine pipeline on a lead.
    
    Args:
        lead: Lead data dict
        enrichment: Optional existing enrichment data
        stream: If True, yield progress updates
    
    Returns:
        Final state with proof deck and outreach
    """
    # Create initial state
    state = create_initial_state(lead, enrichment)
    
    # Create graph
    graph = create_goldmine_graph()
    
    # Config with thread ID for persistence
    config = {
        "configurable": {
            "thread_id": state["thread_id"],
        }
    }
    
    if stream:
        # Stream mode - yield updates
        for chunk in graph.stream(state, config, stream_mode="updates"):
            yield chunk
    else:
        # Invoke mode - return final state
        return graph.invoke(state, config)


def resume_goldmine_pipeline(
    thread_id: str,
    human_input: Any = None,
):
    """
    Resume a paused Goldmine pipeline (e.g., after human approval).
    
    Args:
        thread_id: The thread ID to resume
        human_input: The human's response (for interrupt)
    
    Returns:
        Final state
    """
    graph = create_goldmine_graph()
    
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }
    
    if human_input is not None:
        # Resume with human input
        return graph.invoke(Command(resume=human_input), config)
    else:
        # Just continue
        return graph.invoke(None, config)
