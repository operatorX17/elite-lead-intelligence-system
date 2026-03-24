"""
REVENUE CALCULATOR - Shows them exactly how much money they're losing.

This is the CLOSER. When you can say "You're losing $8,500/month" with proof,
the sale becomes obvious.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.goldmine.state import GoldmineState, MysteryShopResult


logger = logging.getLogger(__name__)


# Industry average ticket prices (conservative estimates)
INDUSTRY_TICKET_PRICES = {
    # Home Services
    "plumber": 350,
    "plumbing": 350,
    "hvac": 500,
    "heating": 500,
    "cooling": 500,
    "air conditioning": 500,
    "roofing": 8000,
    "roofer": 8000,
    "electrical": 300,
    "electrician": 300,
    "solar": 25000,
    "remodeling": 15000,
    "contractor": 10000,
    "landscaping": 2500,
    "pool": 3000,
    "pest control": 200,
    "garage door": 400,
    "painting": 3000,
    "flooring": 4000,
    
    # Medical/Health
    "dental": 1500,
    "dentist": 1500,
    "orthodontist": 5000,
    "chiropractic": 200,
    "chiropractor": 200,
    "physical therapy": 150,
    "veterinary": 300,
    "vet": 300,
    "optometry": 400,
    "dermatology": 300,
    "plastic surgery": 8000,
    "mental health": 200,
    "therapy": 150,
    
    # Professional Services
    "legal": 3000,
    "lawyer": 3000,
    "attorney": 3000,
    "accountant": 1500,
    "cpa": 1500,
    "financial": 2000,
    "insurance": 1200,
    "real estate": 15000,
    
    # Automotive
    "auto repair": 500,
    "mechanic": 400,
    "body shop": 2000,
    
    # Other
    "moving": 1500,
    "storage": 150,
    "cleaning": 200,
    "security": 500,
    
    # Default
    "default": 500,
}

# Response time impact on conversion
# Industry data: 78% of customers buy from first responder
RESPONSE_TIME_CONVERSION_LOSS = {
    "5_min": 0.0,      # No loss - you're the first responder
    "30_min": 0.15,    # 15% loss
    "1_hour": 0.30,    # 30% loss
    "4_hours": 0.50,   # 50% loss
    "24_hours": 0.70,  # 70% loss
    "never": 0.90,     # 90% loss - they went to competitor
}


class RevenueCalculator:
    """
    Calculate exactly how much money a business is losing.
    
    This creates the "holy shit" moment that closes deals.
    """
    
    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.RevenueCalculator")
    
    def calculate_losses(self, state: GoldmineState) -> Dict[str, Any]:
        """
        Calculate total revenue losses with breakdown.
        
        Returns updated state with loss calculations.
        """
        lead = state["lead"]
        mystery_results = state.get("mystery_shop_results", [])
        
        business_name = lead.get("business_name", "Unknown")
        category = lead.get("category", "").lower()
        
        self._logger.info(f"💰 Calculating losses for: {business_name}")
        
        # Get average ticket price for this industry
        ticket_price = self._get_ticket_price(category)
        
        # Calculate individual loss components
        loss_breakdown = {}
        
        # 1. Slow response loss
        response_loss = self._calculate_response_loss(
            mystery_results, ticket_price
        )
        loss_breakdown["slow_response"] = response_loss
        
        # 2. After-hours loss
        after_hours_loss = self._calculate_after_hours_loss(
            lead, ticket_price
        )
        loss_breakdown["after_hours"] = after_hours_loss
        
        # 3. No online booking loss
        booking_loss = self._calculate_booking_loss(
            state.get("enrichment", {}), ticket_price
        )
        loss_breakdown["no_online_booking"] = booking_loss
        
        # 4. Mobile/UX loss
        ux_loss = self._calculate_ux_loss(
            state.get("enrichment", {}), ticket_price
        )
        loss_breakdown["poor_ux"] = ux_loss
        
        # 5. Review reputation loss
        review_loss = self._calculate_review_loss(
            lead, ticket_price
        )
        loss_breakdown["reputation"] = review_loss
        
        # Total monthly loss
        monthly_loss = sum(loss_breakdown.values())
        annual_loss = monthly_loss * 12
        
        self._logger.info(
            f"📊 {business_name} losing ${monthly_loss:,.0f}/month "
            f"(${annual_loss:,.0f}/year)"
        )
        
        return {
            "estimated_monthly_loss": monthly_loss,
            "estimated_annual_loss": annual_loss,
            "loss_breakdown": loss_breakdown,
            "completed_stages": ["revenue_calculated"],
        }
    
    def _get_ticket_price(self, category: str) -> float:
        """Get average ticket price for industry."""
        category_lower = category.lower()
        
        for keyword, price in INDUSTRY_TICKET_PRICES.items():
            if keyword in category_lower:
                return price
        
        return INDUSTRY_TICKET_PRICES["default"]
    
    def _calculate_response_loss(
        self,
        mystery_results: list,
        ticket_price: float,
    ) -> float:
        """
        Calculate loss from slow response times.
        
        Formula:
        - Estimate 50 leads/month for local business
        - Apply conversion loss based on response time
        - Multiply by ticket price
        """
        if not mystery_results:
            # No mystery shop data - assume average
            return ticket_price * 50 * 0.30  # 30% loss assumed
        
        # Get worst response score
        worst_score = min(r.get("response_score", 50) for r in mystery_results)
        
        # Convert score to conversion loss
        if worst_score >= 80:
            conversion_loss = 0.10
        elif worst_score >= 60:
            conversion_loss = 0.25
        elif worst_score >= 40:
            conversion_loss = 0.40
        elif worst_score >= 20:
            conversion_loss = 0.60
        else:
            conversion_loss = 0.80
        
        # Estimate 50 leads/month, 20% would convert
        potential_customers = 50 * 0.20
        lost_customers = potential_customers * conversion_loss
        
        return lost_customers * ticket_price
    
    def _calculate_after_hours_loss(
        self,
        lead: Dict[str, Any],
        ticket_price: float,
    ) -> float:
        """
        Calculate loss from no after-hours lead capture.
        
        40% of searches happen after business hours.
        Without chat/booking, you lose most of these.
        """
        # Check if they have after-hours capture
        has_chat = False  # Would come from enrichment
        has_booking = False  # Would come from enrichment
        
        if has_chat or has_booking:
            return 0.0
        
        # 40% of 50 leads = 20 after-hours leads
        # 70% of those are lost without capture
        after_hours_leads = 50 * 0.40
        lost_leads = after_hours_leads * 0.70
        
        # 20% would have converted
        lost_customers = lost_leads * 0.20
        
        return lost_customers * ticket_price
    
    def _calculate_booking_loss(
        self,
        enrichment: Dict[str, Any],
        ticket_price: float,
    ) -> float:
        """
        Calculate loss from no online booking.
        
        Businesses with online booking convert 30% more leads.
        """
        has_booking = enrichment.get("booking_provider")
        
        if has_booking:
            return 0.0
        
        # 30% conversion improvement missed
        # On 50 leads with 20% base conversion = 10 customers
        # 30% more = 3 additional customers
        
        return 3 * ticket_price
    
    def _calculate_ux_loss(
        self,
        enrichment: Dict[str, Any],
        ticket_price: float,
    ) -> float:
        """
        Calculate loss from poor website UX.
        
        Slow sites, no mobile optimization, etc.
        """
        # Would need PageSpeed data
        # Assume 10% loss for now
        
        potential_customers = 50 * 0.20
        ux_loss_rate = 0.10
        
        return potential_customers * ux_loss_rate * ticket_price
    
    def _calculate_review_loss(
        self,
        lead: Dict[str, Any],
        ticket_price: float,
    ) -> float:
        """
        Calculate loss from poor reviews/reputation.
        
        Each star below 4.5 = 5-9% revenue loss.
        """
        rating = lead.get("rating") or lead.get("review_rating")
        
        if not rating:
            return 0.0
        
        try:
            rating = float(rating)
        except:
            return 0.0
        
        if rating >= 4.5:
            return 0.0
        
        # Calculate loss per star below 4.5
        stars_below = 4.5 - rating
        loss_rate = stars_below * 0.07  # 7% per star
        
        potential_revenue = 50 * 0.20 * ticket_price
        
        return potential_revenue * loss_rate
    
    def generate_loss_headline(self, state: GoldmineState) -> str:
        """Generate the attention-grabbing headline."""
        monthly_loss = state.get("estimated_monthly_loss", 0)
        business_name = state["lead"].get("business_name", "Your business")
        
        if monthly_loss >= 10000:
            return f"🚨 {business_name} is losing ${monthly_loss:,.0f}+ every month"
        elif monthly_loss >= 5000:
            return f"⚠️ {business_name} is leaving ${monthly_loss:,.0f}/month on the table"
        elif monthly_loss >= 2000:
            return f"📉 {business_name} could be making ${monthly_loss:,.0f} more per month"
        else:
            return f"💡 {business_name} has room to grow by ${monthly_loss:,.0f}/month"


def revenue_calculator_node(state: GoldmineState) -> Dict[str, Any]:
    """LangGraph node for revenue calculation."""
    calculator = RevenueCalculator()
    return calculator.calculate_losses(state)
