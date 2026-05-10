"""
PROOF GENERATOR - Creates irrefutable evidence decks.

This generates the "holy shit" moment:
- Screenshots of their slow/broken website
- Competitor comparison showing they're behind
- Review quotes showing customers complaining
- Dollar amounts they're losing

When a business owner sees this, the sale is 80% done.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import json
import base64

from src.goldmine.state import (
    GoldmineState, 
    ProofDeck, 
    CompetitorAnalysis,
    ReviewEvidence,
)
from src.goldmine.revenue_calculator import RevenueCalculator
from src.tools.llm import get_llm_client


logger = logging.getLogger(__name__)


class ProofGeneratorAgent:
    """
    Generates proof decks that close deals.
    
    A proof deck contains:
    1. The hook: "You're losing $X,XXX/month"
    2. The evidence: Screenshots, response times, competitor gaps
    3. The solution: What we can fix
    4. The CTA: Book a call
    """
    
    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.ProofGeneratorAgent")
        self._llm = get_llm_client()
        self._calculator = RevenueCalculator()
    
    def generate_proof_deck(self, state: GoldmineState) -> Dict[str, Any]:
        """
        Generate complete proof deck for a prospect.
        """
        lead = state["lead"]
        business_name = lead.get("business_name", "Unknown")
        
        self._logger.info(f"📄 Generating proof deck for: {business_name}")
        
        # Generate headline
        headline = self._calculator.generate_loss_headline(state)
        
        # Compile mystery shop evidence
        mystery_evidence = self._compile_mystery_evidence(state)
        
        # Generate competitor comparison
        competitor_comparison = self._generate_competitor_comparison(state)
        
        # Extract review evidence
        review_evidence = self._extract_review_evidence(state)
        
        # Get screenshots
        screenshots = self._get_best_screenshots(state)
        
        # Create proof deck
        proof_deck = ProofDeck(
            lead_id=state["lead_id"],
            business_name=business_name,
            headline=headline,
            mystery_shop_evidence=mystery_evidence,
            competitor_comparison=competitor_comparison,
            review_evidence=review_evidence,
            estimated_monthly_loss=state.get("estimated_monthly_loss", 0),
            estimated_annual_loss=state.get("estimated_annual_loss", 0),
            loss_breakdown=state.get("loss_breakdown", {}),
            their_website_screenshot=screenshots.get("hero"),
            competitor_screenshot=screenshots.get("competitor"),
            pdf_url=None,  # Would generate PDF
            video_url=None,  # Would generate Loom video
            generated_at=datetime.utcnow(),
            confidence_score=self._calculate_confidence(state),
        )
        
        # Calculate goldmine score
        goldmine_score = self._calculate_goldmine_score(state, proof_deck)
        
        self._logger.info(
            f"✅ Proof deck generated for {business_name} "
            f"(Goldmine Score: {goldmine_score})"
        )
        
        return {
            "proof_deck": proof_deck,
            "goldmine_score": goldmine_score,
            "completed_stages": ["proof_generated"],
        }
    
    def _compile_mystery_evidence(self, state: GoldmineState) -> Dict[str, Any]:
        """Compile mystery shopping evidence into presentable format."""
        results = state.get("mystery_shop_results", [])
        
        if not results:
            return {
                "tested": False,
                "summary": "No mystery shopping data available",
            }
        
        # Get the most recent result
        result = results[-1]
        
        evidence = {
            "tested": True,
            "form_test": {
                "submitted": result.get("form_submitted", False),
                "submission_time": str(result.get("form_submission_time", "")),
                "response_received": result.get("form_response_received", False),
                "response_time_hours": result.get("form_response_time_hours"),
                "response_quality": result.get("form_response_quality"),
            },
            "phone_test": {
                "called": result.get("phone_called", False),
                "answered": result.get("phone_answered", False),
                "callback_received": result.get("phone_callback_received", False),
                "callback_time_hours": result.get("phone_callback_time_hours"),
            },
            "response_score": result.get("response_score", 0),
            "money_leak_detected": result.get("money_leak_detected", False),
        }
        
        # Generate summary
        if evidence["response_score"] < 40:
            evidence["summary"] = (
                "🚨 CRITICAL: Your response time is costing you customers. "
                "78% of customers buy from the first business to respond."
            )
        elif evidence["response_score"] < 70:
            evidence["summary"] = (
                "⚠️ WARNING: Your response time is below industry average. "
                "You're likely losing leads to faster competitors."
            )
        else:
            evidence["summary"] = (
                "✅ GOOD: Your response time is acceptable, but there's "
                "still room for improvement."
            )
        
        return evidence
    
    def _generate_competitor_comparison(
        self, 
        state: GoldmineState,
    ) -> List[CompetitorAnalysis]:
        """Generate competitor comparison data."""
        # In production, would scrape top 3 competitors
        # For now, return placeholder
        
        lead = state["lead"]
        category = lead.get("category", "")
        location = lead.get("location", "")
        
        # Would use Apify to find competitors
        # Then Steel to analyze their websites
        
        return state.get("competitor_analyses", [])
    
    def _extract_review_evidence(
        self,
        state: GoldmineState,
    ) -> List[ReviewEvidence]:
        """Extract damning review quotes."""
        # Would use NLP to find reviews mentioning:
        # - "no response"
        # - "never called back"
        # - "hard to reach"
        # - "waited days"
        
        return state.get("review_evidence", [])
    
    def _get_best_screenshots(
        self,
        state: GoldmineState,
    ) -> Dict[str, Optional[bytes]]:
        """Get best screenshots for proof deck."""
        screenshots = {"hero": None, "competitor": None}
        
        results = state.get("mystery_shop_results", [])
        if results and results[-1].get("screenshots"):
            screenshots["hero"] = results[-1]["screenshots"][0]
        
        return screenshots
    
    def _calculate_confidence(self, state: GoldmineState) -> float:
        """Calculate confidence score for the proof deck."""
        confidence = 0.5  # Base confidence
        
        # More mystery shop data = higher confidence
        if state.get("mystery_shop_results"):
            confidence += 0.2
        
        # Revenue calculation done = higher confidence
        if state.get("estimated_monthly_loss", 0) > 0:
            confidence += 0.15
        
        # Competitor data = higher confidence
        if state.get("competitor_analyses"):
            confidence += 0.1
        
        # Review evidence = higher confidence
        if state.get("review_evidence"):
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _calculate_goldmine_score(
        self,
        state: GoldmineState,
        proof_deck: ProofDeck,
    ) -> int:
        """
        Calculate the Goldmine Score (0-100).
        
        This is THE number that determines if we pursue this lead.
        
        Scoring:
        - Monthly loss > $10k: +30
        - Monthly loss > $5k: +20
        - Monthly loss > $2k: +10
        - Response score < 40: +25
        - Response score < 70: +15
        - High-ticket category: +20
        - Has website: +10
        - Has phone: +5
        - Confidence > 0.7: +10
        """
        score = 0
        
        # Revenue loss scoring
        monthly_loss = state.get("estimated_monthly_loss", 0)
        if monthly_loss >= 10000:
            score += 30
        elif monthly_loss >= 5000:
            score += 20
        elif monthly_loss >= 2000:
            score += 10
        
        # Response score (inverse - lower response = higher opportunity)
        results = state.get("mystery_shop_results", [])
        if results:
            response_score = results[-1].get("response_score", 50)
            if response_score < 40:
                score += 25
            elif response_score < 70:
                score += 15
        
        # Category scoring
        lead = state["lead"]
        category = (lead.get("category") or "").lower()
        high_ticket_keywords = [
            "dental", "hvac", "roofing", "solar", "legal", 
            "medical", "plumbing", "remodeling"
        ]
        if any(kw in category for kw in high_ticket_keywords):
            score += 20
        
        # Contact info scoring
        if lead.get("website") or lead.get("landing_page_url"):
            score += 10
        if lead.get("phone"):
            score += 5
        
        # Confidence scoring
        if proof_deck["confidence_score"] > 0.7:
            score += 10
        
        return min(score, 100)
    
    def generate_outreach_copy(
        self,
        state: GoldmineState,
    ) -> Dict[str, str]:
        """
        Generate personalized outreach copy using LLM.
        """
        lead = state["lead"]
        proof_deck = state.get("proof_deck")
        
        if not proof_deck:
            return {}
        
        business_name = lead.get("business_name", "your business")
        monthly_loss = state.get("estimated_monthly_loss", 0)
        category = lead.get("category", "business")
        
        # Generate email subject lines
        subjects = [
            f"Quick question about {business_name}",
            f"I found something about {business_name}...",
            f"${monthly_loss:,.0f}/month question for {business_name}",
        ]
        
        # Generate email body
        email_body = f"""Hi,

I was researching {category} businesses in your area and came across {business_name}.

I noticed a few things that might be costing you customers:

{proof_deck['headline']}

I put together a quick analysis showing exactly where the gaps are and how much they might be costing you.

Would you be open to a 15-minute call this week to walk through it? No pitch, just sharing what I found.

Best,
[Your Name]

P.S. I can send over the full analysis before our call so you can review it."""

        # Generate LinkedIn message
        linkedin_message = f"""Hi! I came across {business_name} while researching {category} businesses.

I noticed a few opportunities that could help you capture more leads. Put together a quick analysis - would love to share it with you.

Open to connecting?"""

        return {
            "email_subjects": subjects,
            "email_body": email_body,
            "linkedin_message": linkedin_message,
        }


def proof_generator_node(state: GoldmineState) -> Dict[str, Any]:
    """LangGraph node for proof generation."""
    agent = ProofGeneratorAgent()
    return agent.generate_proof_deck(state)
