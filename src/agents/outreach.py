"""
Outreach Agent - Proof-based outreach generation.
Requirements: 8.1-8.8
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4
import logging

from src.agents.base import BaseAgent
from src.graph.state import LeadGraphState
from src.db.models import (
    OutreachQueue, OutreachChannel, OutreachVariant, 
    OutreachStatus, Personalization, LeadTier
)
from src.tools.pinecone_client import PineconeClient


logger = logging.getLogger(__name__)


class OutreachAgent(BaseAgent):
    """
    Outreach Agent for proof-based message generation.
    
    Requirements:
    - 8.1: Include proof screenshots from Proof_Pack
    - 8.2: Include audit_bullets showing evidence, impact, offer
    - 8.3: Follow required structure: observation, impact, offer, single CTA
    - 8.4: Include opt-out line for email
    - 8.5: Create A/B variants for testing
    - 8.6: Create channel-ready payloads (email, DM, form)
    - 8.7: Queue messages for human approval by default
    - 8.8: Auto-send for tier A if enabled
    """
    
    # Message structure template (Requirement 8.3)
    EMAIL_TEMPLATE = """Hi {decision_maker_name},

{observation}

{impact}

{offer}

{cta}

{opt_out}"""
    
    DM_TEMPLATE = """Hi {decision_maker_name},

{observation}

{impact}

{offer}

{cta}"""
    
    def __init__(self):
        super().__init__("outreach")
        try:
            self._pinecone = PineconeClient()
        except:
            self._pinecone = None
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process outreach generation for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data for outreach")
            return state
        
        # Check if should skip
        if state.get("should_skip_outreach"):
            self._logger.info(f"Skipping outreach for lead {state['lead'].get('lead_id')}")
            return state
        
        # Check kill switch
        if self._check_kill_switch():
            self._logger.warning("Outreach kill switch is active")
            return state
        
        state["current_stage"] = "outreach"
        
        lead = state["lead"]
        enrichment = state.get("enrichment", {})
        scoring = state.get("scoring", {})
        proof = state.get("proof", {})
        metadata = state.get("metadata", {}) or {}
        analysis_bundle = metadata.get("intelligence") or metadata.get("analysis_bundle") or {}
        signal_facts = metadata.get("signal_facts") or analysis_bundle.get("facts") or {}
        
        # Get tier
        tier = scoring.get("lead_tier", "B") if scoring else "B"
        channel = (state.get("metadata", {}).get("channel") or "email").lower()
        
        # Generate personalization data
        personalization = self._create_personalization(lead, enrichment, proof)
        
        # Generate A/B variants (Requirement 8.5)
        messages = []
        
        # Variant A
        variant_a = self._generate_message(
            lead, enrichment, proof, personalization,
            variant="A",
            tier=tier,
            channel=channel,
            signal_facts=signal_facts,
            analysis_bundle=analysis_bundle,
        )
        messages.append(variant_a)
        
        # Variant B
        variant_b = self._generate_message(
            lead, enrichment, proof, personalization,
            variant="B",
            tier=tier,
            channel=channel,
            signal_facts=signal_facts,
            analysis_bundle=analysis_bundle,
        )
        messages.append(variant_b)
        
        # Determine if auto-send (Requirement 8.8)
        auto_send = self._config.system.environment == "production" and tier == "A"
        
        # Save messages to queue
        for msg in messages:
            msg["requires_approval"] = not auto_send
            self._save_outreach(msg)
        
        state["outreach_messages"] = messages
        
        return state
    
    def _create_personalization(
        self,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        proof: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create personalization data for message."""
        decision_maker_name = "there"  # Default
        
        if enrichment and enrichment.get("decision_maker_name"):
            decision_maker_name = enrichment["decision_maker_name"]
        elif lead.get("business_name"):
            # Try to extract name from business name
            if "'s" in lead["business_name"]:
                decision_maker_name = lead["business_name"].split("'s")[0]
        
        # Get evidence from proof pack
        evidence = None
        if proof and proof.get("audit_bullets"):
            for bullet in proof["audit_bullets"]:
                if bullet.get("type") == "leak" and bullet.get("evidence"):
                    evidence = bullet["evidence"]
                    break
        
        return {
            "decision_maker_name": decision_maker_name,
            "business_name": lead.get("business_name"),
            "category": lead.get("category"),
            "evidence": evidence,
        }
    
    def _generate_message(
        self,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        proof: Dict[str, Any],
        personalization: Dict[str, Any],
        variant: str,
        tier: str,
        channel: str,
        signal_facts: Optional[Dict[str, Any]] = None,
        analysis_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate outreach message.
        Requirements: 8.1-8.4, 8.6
        """
        # Get observation (evidence from proof pack)
        observation = self._generate_observation(
            lead,
            proof,
            variant,
            signal_facts,
            analysis_bundle,
        )
        
        # Get impact (money/loss framing)
        impact = self._generate_impact(
            lead,
            proof,
            variant,
            signal_facts,
            analysis_bundle,
        )
        
        # Get offer (done-for-you solution)
        offer = self._generate_offer(lead, tier, variant)
        
        # Get CTA (single action)
        cta = self._generate_cta(tier, variant)
        
        # Opt-out line (Requirement 8.4)
        opt_out = "[Reply STOP to unsubscribe]"
        
        template = self.EMAIL_TEMPLATE if channel == "email" else self.DM_TEMPLATE
        message_body = template.format(
            decision_maker_name=personalization.get("decision_maker_name", "there"),
            observation=observation,
            impact=impact,
            offer=offer,
            cta=cta,
            opt_out=opt_out,
        )

        subject = self._generate_subject(lead, variant) if channel == "email" else None
        
        # Get attachments (screenshots)
        attachments = []
        if proof:
            if proof.get("hero_screenshot_url"):
                attachments.append(proof["hero_screenshot_url"])
            if proof.get("cta_screenshot_url"):
                attachments.append(proof["cta_screenshot_url"])
        
        return {
            "outreach_id": str(uuid4()),
            "lead_id": lead.get("lead_id"),
            "channel": channel,
            "variant": variant,
            "subject": subject,
            "body": message_body,
            "attachments": attachments,
            "personalization": personalization,
            "status": "pending",
            "requires_approval": True,
        }

    def _extract_proof_truth(
        self,
        proof: Dict[str, Any],
        signal_facts: Optional[Dict[str, Any]] = None,
        analysis_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extraction = (proof or {}).get("extraction_data") or {}
        analysis_bundle = analysis_bundle or {}
        guidance = analysis_bundle.get("guidance") or {}
        signal_facts = signal_facts or analysis_bundle.get("facts") or {}
        phone_visible = signal_facts.get("phone_visible")
        if phone_visible is None:
            phone_visible = str(extraction.get("phone_visibility") or "").lower() in {
                "hero",
                "visible",
                "above_fold",
                "below_fold",
            } or bool(extraction.get("phone_numbers"))
        has_booking = signal_facts.get("booking_detected")
        if has_booking is None:
            has_booking = bool(extraction.get("booking_link"))
        has_whatsapp = signal_facts.get("whatsapp_detected")
        if has_whatsapp is None:
            has_whatsapp = extraction.get("chat_widget") == "whatsapp" or bool(
                extraction.get("whatsapp_target")
            )
        form_fields = extraction.get("form_field_count")
        return {
            "phone_visible": bool(phone_visible),
            "has_booking": bool(has_booking),
            "has_whatsapp": bool(has_whatsapp),
            "form_fields": form_fields if isinstance(form_fields, int) else None,
            "booking_link": signal_facts.get("booking_target") or extraction.get("booking_link"),
            "whatsapp_target": signal_facts.get("whatsapp_target") or extraction.get("whatsapp_target"),
            "top_issue": signal_facts.get("top_issue") or guidance.get("top_issue"),
            "next_best_action": signal_facts.get("next_best_action") or guidance.get("next_best_action"),
        }
    
    def _generate_observation(
        self,
        lead: Dict[str, Any],
        proof: Dict[str, Any],
        variant: str,
        signal_facts: Optional[Dict[str, Any]] = None,
        analysis_bundle: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate observation section (evidence).
        Requirements: 8.3
        """
        business_name = (
            lead.get("business_name")
            or lead.get("company_name")
            or "your business"
        )
        truth = self._extract_proof_truth(proof, signal_facts, analysis_bundle)

        if truth["phone_visible"] and truth["has_booking"] and truth["has_whatsapp"]:
            if variant == "A":
                return (
                    f"I reviewed {business_name}'s site and confirmed you already have a visible "
                    "phone path, booking flow, and WhatsApp capture in place."
                )
            return (
                f"While looking at your website, I confirmed your core contact paths are live: "
                "phone, booking, and WhatsApp."
            )

        if truth.get("top_issue") == "WhatsApp capture is missing":
            if variant == "A":
                return f"I reviewed {business_name}'s site and noticed there is no clear WhatsApp capture path."
            return f"While looking at your website, I noticed a likely lead leak: no clear WhatsApp path for visitors."

        if truth.get("top_issue") == "Booking flow is weak":
            if variant == "A":
                return f"I reviewed {business_name}'s site and noticed the booking path still looks weak."
            return f"While looking at your website, I noticed the booking path could be stronger for ready-to-book visitors."

        if proof and proof.get("audit_bullets"):
            for bullet in proof["audit_bullets"]:
                if bullet.get("type") == "leak" and bullet.get("evidence"):
                    evidence = bullet["evidence"].lower()
                    if variant == "A":
                        return f"I was reviewing {business_name}'s lead capture and noticed {evidence}."
                    return f"While looking at your website, I spotted something that might be costing you leads: {evidence}."

        if variant == "A":
            return (
                f"I reviewed {business_name}'s site and noticed there is still room to improve "
                "how efficiently visitors convert into booked conversations."
            )
        return (
            f"I came across {business_name} and noticed your site could convert more of the traffic "
            "you already earn."
        )
    
    def _generate_impact(
        self,
        lead: Dict[str, Any],
        proof: Dict[str, Any],
        variant: str,
        signal_facts: Optional[Dict[str, Any]] = None,
        analysis_bundle: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate impact section (money/loss framing).
        Requirements: 8.3
        """
        category = lead.get("category", "service")
        truth = self._extract_proof_truth(proof, signal_facts, analysis_bundle)

        if truth["phone_visible"] and truth["has_booking"] and truth["has_whatsapp"]:
            if variant == "A":
                return (
                    f"For high-intent {category} traffic, the upside is usually in conversion rate "
                    "optimization and faster lead handling rather than adding more contact options."
                )
            return (
                "When the basic contact paths already exist, the next gain usually comes from making "
                "those paths convert more visitors into booked appointments."
            )

        if truth.get("top_issue") == "WhatsApp capture is missing":
            if variant == "A":
                return (
                    f"For high-intent {category} traffic, missing WhatsApp usually means ready prospects "
                    "drop before they ever start a conversation."
                )
            return "For businesses like yours, a missing WhatsApp path usually means warm intent leaks before booking starts."

        if truth.get("top_issue") == "Booking flow is weak":
            if variant == "A":
                return (
                    f"For high-intent {category} traffic, a weak booking flow usually means ready visitors stall "
                    "before they convert into confirmed appointments."
                )
            return "When booking is weak, a lot of purchase intent never turns into a real appointment."

        if proof and proof.get("audit_bullets"):
            for bullet in proof["audit_bullets"]:
                if bullet.get("type") == "upside" and bullet.get("estimate"):
                    estimate = bullet["estimate"].lower()
                    if variant == "A":
                        return f"Based on similar {category} businesses, this typically means you could {estimate}."
                    return f"For businesses like yours, fixing this usually helps {estimate}."

        if variant == "A":
            return "Based on similar businesses, optimizing lead capture typically recovers 15-25% of missed opportunities."
        return "Most businesses in your space see a 15-25% improvement after optimizing their lead capture."
    
    def _generate_offer(
        self,
        lead: Dict[str, Any],
        tier: str,
        variant: str,
    ) -> str:
        """
        Generate offer section (done-for-you solution).
        Requirements: 8.3
        """
        if tier == "A":
            if variant == "A":
                return "We help businesses like yours recover this lost revenue by optimizing lead capture without changing your ad spend."
            else:
                return "I specialize in helping service businesses capture more leads from their existing traffic."
        else:
            if variant == "A":
                return "We've helped similar businesses improve their lead capture with minimal effort on their end."
            else:
                return "I'd be happy to share some quick wins that could help."
    
    def _generate_cta(
        self,
        tier: str,
        variant: str,
    ) -> str:
        """
        Generate CTA section (single action).
        Requirements: 8.3
        """
        if tier == "A":
            if variant == "A":
                return "Worth a 15-minute conversation? Reply YES and I'll send a calendar link."
            else:
                return "Would you be open to a quick call this week? Just reply with a good time."
        else:
            if variant == "A":
                return "Would you like me to send over a few specific suggestions? Just reply YES."
            else:
                return "Interested in learning more? Reply and I'll share some ideas."
    
    def _generate_subject(
        self,
        lead: Dict[str, Any],
        variant: str,
    ) -> str:
        """Generate email subject line."""
        business_name = lead.get("business_name", "your business")
        if variant == "A":
            return f"Quick question about {business_name}'s lead capture"
        else:
            return f"Noticed something on your website"
    
    def _save_outreach(self, outreach: Dict[str, Any]) -> None:
        """Save outreach to database."""
        data = dict(outreach)
        data["lead_id"] = str(outreach.get("lead_id", ""))
        data["created_at"] = datetime.utcnow().isoformat()
        
        self._db.create_outreach(data)


_outreach_agent: Optional[OutreachAgent] = None


def _get_outreach_agent() -> OutreachAgent:
    global _outreach_agent
    if _outreach_agent is None:
        _outreach_agent = OutreachAgent()
    return _outreach_agent


def outreach_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for outreach."""
    return _get_outreach_agent()(state)
