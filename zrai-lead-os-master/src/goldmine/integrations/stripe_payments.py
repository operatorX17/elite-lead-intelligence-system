"""
STRIPE PAYMENTS - Collect money in seconds.

Creates payment links for the 3 pricing tiers:
- Basic: $500/month
- Pro: $1,200/month  
- Enterprise: $12,000/month
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class StripePayments:
    """
    Stripe payment integration for Goldmine.
    
    Setup:
    1. Create Stripe account at stripe.com
    2. Get API keys from Dashboard > Developers > API keys
    3. Create products and prices in Dashboard
    4. Add to .env:
       STRIPE_SECRET_KEY=sk_live_xxx
       STRIPE_PRICE_BASIC=price_xxx
       STRIPE_PRICE_PRO=price_xxx
       STRIPE_PRICE_ENTERPRISE=price_xxx
    """
    
    # Pricing tiers
    TIERS = {
        "basic": {
            "name": "Basic",
            "price": 500,
            "description": "Essential lead generation and outreach",
            "features": [
                "50 leads/month",
                "Email outreach",
                "Basic proof decks",
                "Email support",
            ],
        },
        "pro": {
            "name": "Pro", 
            "price": 1200,
            "description": "Full autonomous sales machine",
            "features": [
                "200 leads/month",
                "Multi-channel outreach",
                "Video proof decks",
                "Priority support",
                "A/B testing",
            ],
        },
        "enterprise": {
            "name": "Enterprise",
            "price": 12000,
            "description": "Unlimited scale with white-glove service",
            "features": [
                "Unlimited leads",
                "All channels",
                "Custom integrations",
                "Dedicated account manager",
                "API access",
                "Custom branding",
            ],
        },
    }
    
    def __init__(self):
        """Initialize Stripe client."""
        self.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.stripe = None
        
        # Price IDs from Stripe Dashboard
        self.price_ids = {
            "basic": os.getenv("STRIPE_PRICE_BASIC"),
            "pro": os.getenv("STRIPE_PRICE_PRO"),
            "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE"),
        }
        
        if self.api_key:
            try:
                import stripe
                stripe.api_key = self.api_key
                self.stripe = stripe
                logger.info("✅ Stripe initialized")
            except ImportError:
                logger.warning("Stripe not installed. Run: pip install stripe")
                
    def is_configured(self) -> bool:
        """Check if Stripe is properly configured."""
        return self.stripe is not None and self.api_key is not None
        
    def create_payment_link(
        self,
        tier: str,
        lead: Dict[str, Any] = None,
        custom_amount: int = None,
    ) -> Dict[str, Any]:
        """
        Create a Stripe payment link for a tier.
        
        Args:
            tier: "basic", "pro", or "enterprise"
            lead: Optional lead data for metadata
            custom_amount: Override price in cents
            
        Returns:
            {"success": bool, "url": str, "error": str}
        """
        if not self.is_configured():
            return {"success": False, "error": "Stripe not configured"}
            
        try:
            price_id = self.price_ids.get(tier)
            
            if price_id:
                # Use existing price
                payment_link = self.stripe.PaymentLink.create(
                    line_items=[{"price": price_id, "quantity": 1}],
                    metadata={
                        "tier": tier,
                        "lead_id": lead.get("lead_id") if lead else None,
                        "business_name": lead.get("business_name") if lead else None,
                    } if lead else {"tier": tier},
                )
            else:
                # Create ad-hoc price
                tier_info = self.TIERS.get(tier, self.TIERS["basic"])
                amount = custom_amount or (tier_info["price"] * 100)  # Convert to cents
                
                # Create product
                product = self.stripe.Product.create(
                    name=f"Goldmine {tier_info['name']}",
                    description=tier_info["description"],
                )
                
                # Create price
                price = self.stripe.Price.create(
                    product=product.id,
                    unit_amount=amount,
                    currency="usd",
                    recurring={"interval": "month"},
                )
                
                # Create payment link
                payment_link = self.stripe.PaymentLink.create(
                    line_items=[{"price": price.id, "quantity": 1}],
                    metadata={
                        "tier": tier,
                        "lead_id": lead.get("lead_id") if lead else None,
                        "business_name": lead.get("business_name") if lead else None,
                    } if lead else {"tier": tier},
                )
                
            logger.info(f"💳 Payment link created: {payment_link.url}")
            return {
                "success": True,
                "url": payment_link.url,
                "id": payment_link.id,
                "tier": tier,
                "amount": self.TIERS.get(tier, {}).get("price", 0),
            }
            
        except Exception as e:
            logger.error(f"Failed to create payment link: {e}")
            return {"success": False, "error": str(e)}
            
    def create_checkout_session(
        self,
        tier: str,
        lead: Dict[str, Any],
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout session for a specific lead.
        
        Args:
            tier: Pricing tier
            lead: Lead data
            success_url: Redirect URL after successful payment
            cancel_url: Redirect URL if cancelled
            
        Returns:
            {"success": bool, "url": str, "session_id": str}
        """
        if not self.is_configured():
            return {"success": False, "error": "Stripe not configured"}
            
        try:
            tier_info = self.TIERS.get(tier, self.TIERS["basic"])
            price_id = self.price_ids.get(tier)
            
            session_params = {
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "customer_email": lead.get("email"),
                "metadata": {
                    "tier": tier,
                    "lead_id": lead.get("lead_id"),
                    "business_name": lead.get("business_name"),
                },
                "subscription_data": {
                    "metadata": {
                        "tier": tier,
                        "lead_id": lead.get("lead_id"),
                    },
                },
            }
            
            if price_id:
                session_params["line_items"] = [{"price": price_id, "quantity": 1}]
            else:
                # Create price on the fly
                session_params["line_items"] = [{
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": tier_info["price"] * 100,
                        "recurring": {"interval": "month"},
                        "product_data": {
                            "name": f"Goldmine {tier_info['name']}",
                            "description": tier_info["description"],
                        },
                    },
                    "quantity": 1,
                }]
                
            session = self.stripe.checkout.Session.create(**session_params)
            
            logger.info(f"💳 Checkout session created for {lead.get('business_name')}")
            return {
                "success": True,
                "url": session.url,
                "session_id": session.id,
                "tier": tier,
            }
            
        except Exception as e:
            logger.error(f"Failed to create checkout session: {e}")
            return {"success": False, "error": str(e)}
            
    def get_payment_links_for_all_tiers(self) -> Dict[str, str]:
        """
        Get or create payment links for all tiers.
        
        Returns:
            {"basic": "url", "pro": "url", "enterprise": "url"}
        """
        links = {}
        for tier in self.TIERS.keys():
            result = self.create_payment_link(tier)
            if result["success"]:
                links[tier] = result["url"]
            else:
                links[tier] = None
        return links
        
    def verify_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Verify and parse a Stripe webhook.
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header
            
        Returns:
            Parsed event or error
        """
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            return {"success": False, "error": "Webhook secret not configured"}
            
        try:
            event = self.stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return {"success": True, "event": event}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Convenience functions
def get_payment_link(tier: str = "basic") -> str:
    """Get a payment link for a tier."""
    payments = StripePayments()
    result = payments.create_payment_link(tier)
    return result.get("url", "")


def create_deal_checkout(
    lead: Dict[str, Any],
    tier: str,
    base_url: str = "https://yourdomain.com",
) -> Dict[str, Any]:
    """
    Create a checkout session for closing a deal.
    
    Args:
        lead: Lead data
        tier: Pricing tier
        base_url: Your website base URL
        
    Returns:
        Checkout session info
    """
    payments = StripePayments()
    return payments.create_checkout_session(
        tier=tier,
        lead=lead,
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
    )
