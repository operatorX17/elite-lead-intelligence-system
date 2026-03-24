"""
GOLDMINE AUTONOMOUS ENGINE - The living, breathing sales machine.

This is the heartbeat of the system. It:
1. Discovers leads continuously
2. Qualifies and scores them
3. Generates proof of money leaks
4. Executes multi-channel outreach
5. Books meetings
6. Closes deals

All autonomously. All in seconds.
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from src.goldmine.graph import run_goldmine_pipeline, create_goldmine_graph
from src.goldmine.state import create_initial_state, ProspectTier
from src.goldmine.integrations.gmail import GmailSender, send_goldmine_email
from src.goldmine.integrations.stripe_payments import StripePayments, get_payment_link
from src.goldmine.integrations.twilio_comms import TwilioComms
from src.goldmine.integrations.pdf_generator import ProofDeckPDF, generate_proof_pdf
from src.goldmine.integrations.loom_video import LoomVideo, create_outreach_video
from src.goldmine.integrations.calendar_booking import CalendarBooking, get_booking_link

logger = logging.getLogger(__name__)


class GoldmineEngine:
    """
    The autonomous sales machine.
    
    This engine runs continuously, processing leads through the full pipeline:
    Discovery → Qualification → Proof → Outreach → Booking → Close
    
    It's designed to be "breathing" - always running, always learning, always closing.
    """
    
    def __init__(self):
        """Initialize the engine with all integrations."""
        # Core pipeline
        self.graph = create_goldmine_graph()
        
        # Integrations
        self.gmail = GmailSender()
        self.stripe = StripePayments()
        self.twilio = TwilioComms()
        self.pdf = ProofDeckPDF()
        self.video = LoomVideo()
        self.calendar = CalendarBooking()
        
        # State
        self.running = False
        self.processed_leads = set()
        self.stats = {
            "leads_processed": 0,
            "emails_sent": 0,
            "sms_sent": 0,
            "calls_made": 0,
            "meetings_booked": 0,
            "deals_closed": 0,
            "revenue_generated": 0,
        }
        
        # Config
        self.booking_url = os.getenv("BOOKING_URL") or self.calendar.get_booking_url()
        self.payment_links = {}
        
        logger.info("🚀 Goldmine Engine initialized")
        self._log_integration_status()
        
    def _log_integration_status(self):
        """Log which integrations are available."""
        integrations = {
            "Gmail": self.gmail._initialized if hasattr(self.gmail, '_initialized') else False,
            "Stripe": self.stripe.is_configured(),
            "Twilio": self.twilio.is_configured(),
            "PDF": self.pdf.reportlab_available,
            "Video": self.video.is_configured(),
            "Calendar": self.calendar.is_configured(),
        }
        
        for name, status in integrations.items():
            emoji = "✅" if status else "❌"
            logger.info(f"  {emoji} {name}: {'Ready' if status else 'Not configured'}")
            
    def process_lead(
        self,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any] = None,
        auto_outreach: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a single lead through the full pipeline.
        
        Args:
            lead: Lead data
            enrichment: Optional existing enrichment
            auto_outreach: Whether to automatically send outreach
            
        Returns:
            Processing result with all generated assets
        """
        lead_id = lead.get("lead_id", lead.get("id"))
        business_name = lead.get("business_name", "Unknown")
        
        logger.info(f"🎯 Processing: {business_name}")
        
        result = {
            "lead_id": lead_id,
            "business_name": business_name,
            "success": False,
            "stages_completed": [],
            "assets": {},
            "outreach_results": {},
            "errors": [],
        }
        
        try:
            # 1. Run the Goldmine pipeline
            logger.info(f"  📊 Running pipeline...")
            
            # run_goldmine_pipeline returns a generator when stream=False, need to get final state
            pipeline_result = run_goldmine_pipeline(lead, enrichment, stream=False)
            
            # If it's a generator, iterate to get final state
            if hasattr(pipeline_result, '__iter__') and not isinstance(pipeline_result, dict):
                final_state = None
                for state in pipeline_result:
                    final_state = state
                if final_state is None:
                    final_state = {}
            else:
                final_state = pipeline_result or {}
            
            result["stages_completed"] = final_state.get("completed_stages", [])
            result["goldmine_score"] = final_state.get("goldmine_score", 0)
            result["monthly_loss"] = final_state.get("estimated_monthly_loss", 0)
            result["tier"] = self._get_tier(final_state.get("goldmine_score", 0))
            
            # 2. Generate proof deck PDF
            if final_state.get("estimated_monthly_loss", 0) > 0:
                logger.info(f"  📄 Generating proof deck...")
                pdf_bytes = self.pdf.generate_proof_deck(
                    lead=lead,
                    monthly_loss=final_state.get("estimated_monthly_loss", 0),
                    loss_breakdown=final_state.get("loss_breakdown"),
                    mystery_shop_results=final_state.get("mystery_shop_results", [{}])[0] if final_state.get("mystery_shop_results") else None,
                    booking_url=self.booking_url,
                )
                result["assets"]["proof_pdf"] = pdf_bytes
                result["stages_completed"].append("pdf_generated")
                
            # 3. Generate video (if configured)
            if self.video.is_configured() and result["tier"] in ["goldmine", "hot"]:
                logger.info(f"  🎬 Creating video...")
                video_result = self.video.create_personalized_video(
                    lead=lead,
                    monthly_loss=final_state.get("estimated_monthly_loss", 0),
                    booking_url=self.booking_url,
                )
                result["assets"]["video"] = video_result
                if video_result.get("success"):
                    result["stages_completed"].append("video_created")
                    
            # 4. Execute outreach (if enabled and qualified)
            if auto_outreach and result["tier"] in ["goldmine", "hot", "warm"]:
                logger.info(f"  📤 Executing outreach...")
                outreach_result = self._execute_outreach(
                    lead=lead,
                    state=final_state,
                    proof_pdf=result["assets"].get("proof_pdf"),
                )
                result["outreach_results"] = outreach_result
                result["stages_completed"].append("outreach_executed")
                
            result["success"] = True
            self.stats["leads_processed"] += 1
            
            logger.info(f"  ✅ Complete! Score: {result['goldmine_score']}, Loss: ${result['monthly_loss']:,.0f}/mo")
            
        except Exception as e:
            logger.error(f"  ❌ Error processing {business_name}: {e}")
            result["errors"].append(str(e))
            
        return result
        
    def _get_tier(self, score: int) -> str:
        """Get tier name from score."""
        if score >= 80:
            return "goldmine"
        elif score >= 60:
            return "hot"
        elif score >= 40:
            return "warm"
        else:
            return "cold"
            
    def _execute_outreach(
        self,
        lead: Dict[str, Any],
        state: Dict[str, Any],
        proof_pdf: bytes = None,
    ) -> Dict[str, Any]:
        """
        Execute multi-channel outreach for a lead.
        
        Sequence:
        1. Email with proof deck
        2. SMS follow-up (if phone available)
        3. WhatsApp (if configured)
        """
        results = {}
        monthly_loss = state.get("estimated_monthly_loss", 0)
        tier = self._get_tier(state.get("goldmine_score", 0))
        
        # 1. Email
        if lead.get("email"):
            email_result = send_goldmine_email(
                lead=lead,
                monthly_loss=monthly_loss,
                proof_pdf=proof_pdf,
                booking_url=self.booking_url,
            )
            results["email"] = email_result
            if email_result.get("success"):
                self.stats["emails_sent"] += 1
                
        # 2. SMS (for hot leads with phone)
        if lead.get("phone") and tier in ["goldmine", "hot"]:
            if self.twilio.is_configured():
                sms_result = self.twilio.send_outreach_sms(
                    lead=lead,
                    booking_url=self.booking_url,
                )
                results["sms"] = sms_result
                if sms_result.get("success"):
                    self.stats["sms_sent"] += 1
                    
        # 3. WhatsApp (for goldmine leads)
        if lead.get("phone") and tier == "goldmine":
            if self.twilio.is_configured():
                business_name = lead.get("business_name", "your business")
                whatsapp_result = self.twilio.send_whatsapp(
                    to=lead["phone"],
                    message=f"Hi! 👋 I found some growth opportunities for {business_name} - could save you ${monthly_loss:,.0f}/month. Mind if I share? {self.booking_url}",
                )
                results["whatsapp"] = whatsapp_result
                
        return results
        
    def process_batch(
        self,
        leads: List[Dict[str, Any]],
        parallel: bool = True,
        max_workers: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Process multiple leads in batch.
        
        Args:
            leads: List of leads to process
            parallel: Whether to process in parallel
            max_workers: Max parallel workers
            
        Returns:
            List of results
        """
        logger.info(f"🚀 Processing batch of {len(leads)} leads...")
        
        if parallel:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(self.process_lead, leads))
        else:
            results = [self.process_lead(lead) for lead in leads]
            
        # Summary
        successful = sum(1 for r in results if r["success"])
        total_loss = sum(r.get("monthly_loss", 0) for r in results)
        
        logger.info(f"📊 Batch complete: {successful}/{len(leads)} successful")
        logger.info(f"💰 Total monthly loss identified: ${total_loss:,.0f}")
        
        return results
        
    def get_payment_link(self, tier: str = "basic") -> str:
        """Get a payment link for a tier."""
        if tier not in self.payment_links:
            if self.stripe.is_configured():
                result = self.stripe.create_payment_link(tier)
                if result.get("success"):
                    self.payment_links[tier] = result["url"]
                else:
                    self.payment_links[tier] = None
            else:
                self.payment_links[tier] = None
                
        return self.payment_links.get(tier)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            **self.stats,
            "integrations": {
                "gmail": self.gmail._initialized if hasattr(self.gmail, '_initialized') else False,
                "stripe": self.stripe.is_configured(),
                "twilio": self.twilio.is_configured(),
                "video": self.video.is_configured(),
                "calendar": self.calendar.is_configured(),
            },
            "payment_links": self.payment_links,
            "booking_url": self.booking_url,
        }
        
    def print_status(self):
        """Print current engine status."""
        stats = self.get_stats()
        
        print("\n" + "=" * 50)
        print("🏆 GOLDMINE ENGINE STATUS")
        print("=" * 50)
        
        print("\n📊 STATS:")
        print(f"  Leads Processed: {stats['leads_processed']}")
        print(f"  Emails Sent: {stats['emails_sent']}")
        print(f"  SMS Sent: {stats['sms_sent']}")
        print(f"  Calls Made: {stats['calls_made']}")
        print(f"  Meetings Booked: {stats['meetings_booked']}")
        print(f"  Deals Closed: {stats['deals_closed']}")
        print(f"  Revenue: ${stats['revenue_generated']:,.0f}")
        
        print("\n🔌 INTEGRATIONS:")
        for name, status in stats["integrations"].items():
            emoji = "✅" if status else "❌"
            print(f"  {emoji} {name.title()}")
            
        print("\n💳 PAYMENT LINKS:")
        for tier, url in stats.get("payment_links", {}).items():
            if url:
                print(f"  {tier.title()}: {url}")
                
        print(f"\n📅 Booking URL: {stats.get('booking_url', 'Not configured')}")
        print("=" * 50 + "\n")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def quick_process(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Quick process a single lead."""
    engine = GoldmineEngine()
    return engine.process_lead(lead)


def batch_process(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Batch process multiple leads."""
    engine = GoldmineEngine()
    return engine.process_batch(leads)


def get_engine_status() -> Dict[str, Any]:
    """Get engine status."""
    engine = GoldmineEngine()
    return engine.get_stats()


# =============================================================================
# CLI RUNNER
# =============================================================================

if __name__ == "__main__":
    import argparse
    from src.db.client import get_supabase_client
    
    parser = argparse.ArgumentParser(description="Goldmine Autonomous Engine")
    parser.add_argument("--status", action="store_true", help="Show engine status")
    parser.add_argument("--process", type=str, help="Process a specific lead by ID")
    parser.add_argument("--batch", type=int, help="Process N leads from database")
    parser.add_argument("--tier", type=str, default="A", help="Filter by tier (A, B, C)")
    
    args = parser.parse_args()
    
    engine = GoldmineEngine()
    
    if args.status:
        engine.print_status()
        
    elif args.process:
        # Get lead from database
        supabase = get_supabase_client()
        result = supabase.table("leads").select("*").eq("lead_id", args.process).single().execute()
        if result.data:
            engine.process_lead(result.data)
        else:
            print(f"Lead not found: {args.process}")
            
    elif args.batch:
        # Get leads from database
        supabase = get_supabase_client()
        query = supabase.table("leads").select("*")
        
        if args.tier:
            query = query.eq("tier", args.tier)
            
        result = query.limit(args.batch).execute()
        
        if result.data:
            engine.process_batch(result.data)
        else:
            print("No leads found")
            
    else:
        engine.print_status()
