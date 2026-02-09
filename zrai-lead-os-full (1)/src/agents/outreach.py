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
from src.tools.llm import get_llm_client
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

{cta}"""
    
    def __init__(self):
        super().__init__("outreach")
        self._llm = get_llm_client()
        try:
            self._pinecone = PineconeClient()
        except:
            self._pinecone = None
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process outreach generation for a lead."""
        if not state.lead:
            self._logger.warning("No lead data for outreach")
            return state
        
        # Check if should skip
        if state.should_skip_outreach:
            self._logger.info(f"Skipping outreach for lead {state.lead.lead_id}")
            return state
        
        # Check kill switch
        if self._check_kill_switch():
            self._logger.warning("Outreach kill switch is active")
            return state
        
        state.current_stage = "outreach"
        
        lead = state.lead
        enrichment = state.enrichment
        scoring = state.scoring
        proof = state.proof
        
        # Get tier
        tier = scoring.lead_tier if scoring else LeadTier.B
        
        # Generate personalization data
        personalization = self._create_personalization(lead, enrichment, proof)
        
        # Generate A/B variants (Requirement 8.5)
        messages = []
        
        # Variant A
        variant_a = self._generate_message(
            lead, enrichment, proof, personalization,
            variant=OutreachVariant.A,
            tier=tier,
        )
        messages.append(variant_a)
        
        # Variant B
        variant_b = self._generate_message(
            lead, enrichment, proof, personalization,
            variant=OutreachVariant.B,
            tier=tier,
        )
        messages.append(variant_b)
        
        # Determine if auto-send (Requirement 8.8)
        auto_send = self._config.system.environment == "production" and tier == LeadTier.A
        
        # Save messages to queue
        for msg in messages:
            msg.requires_approval = not auto_send
            self._save_outreach(msg)
        
        state.outreach_messages = messages
        
        return state
    
    def _create_personalization(
        self,
        lead,
        enrichment,
        proof,
    ) -> Personalization:
        """Create personalization data for message."""
        decision_maker_name = "there"  # Default
        
        if enrichment and enrichment.decision_maker_name:
            decision_maker_name = enrichment.decision_maker_name
        elif lead.business_name:
            # Try to extract name from business name
            if "'s" in lead.business_name:
                decision_maker_name = lead.business_name.split("'s")[0]
        
        # Get evidence from proof pack
        evidence = None
        if proof and proof.audit_bullets:
            for bullet in proof.audit_bullets:
                if bullet.type == "leak" and bullet.evidence:
                    evidence = bullet.evidence
                    break
        
        return Personalization(
            decision_maker_name=decision_maker_name,
            business_name=lead.business_name,
            category=lead.category,
            evidence=evidence,
        )
    
    def _generate_message(
        self,
        lead,
        enrichment,
        proof,
        personalization: Personalization,
        variant: OutreachVariant,
        tier: LeadTier,
    ) -> OutreachQueue:
        """
        Generate outreach message.
        Requirements: 8.1-8.4, 8.6
        """
        # Get observation (evidence from proof pack)
        observation = self._generate_observation(lead, proof, variant)
        
        # Get impact (money/loss framing)
        impact = self._generate_impact(lead, proof, variant)
        
        # Get offer (done-for-you solution)
        offer = self._generate_offer(lead, tier, variant)
        
        # Get CTA (single action)
        cta = self._generate_cta(tier, variant)
        
        # Opt-out line (Requirement 8.4)
        opt_out = "[Reply STOP to unsubscribe]"
        
        # Generate email body
        email_body = self.EMAIL_TEMPLATE.format(
            decision_maker_name=personalization.decision_maker_name,
            observation=observation,
            impact=impact,
            offer=offer,
            cta=cta,
            opt_out=opt_out,
        )
        
        # Generate subject line
        subject = self._generate_subject(lead, variant)
        
        # Get attachments (screenshots)
        attachments = []
        if proof:
            if proof.hero_screenshot_url:
                attachments.append(proof.hero_screenshot_url)
            if proof.cta_screenshot_url:
                attachments.append(proof.cta_screenshot_url)
        
        return OutreachQueue(
            outreach_id=uuid4(),
            lead_id=lead.lead_id,
            channel=OutreachChannel.EMAIL,
            variant=variant,
            subject=subject,
            body=email_body,
            attachments=attachments,
            personalization=personalization,
            status=OutreachStatus.PENDING,
            requires_approval=True,
        )
    
    def _generate_observation(
        self,
        lead,
        proof,
        variant: OutreachVariant,
    ) -> str:
        """
        Generate observation section (evidence).
        Requirements: 8.3
        """
        if proof and proof.audit_bullets:
            for bullet in proof.audit_bullets:
                if bullet.type == "leak" and bullet.evidence:
                    if variant == OutreachVariant.A:
                        return f"I was reviewing {lead.business_name}'s lead capture and noticed {bullet.evidence.lower()}."
                    else:
                        return f"While looking at your website, I spotted something that might be costing you leads: {bullet.evidence.lower()}."
        
        # Fallback observation
        if variant == OutreachVariant.A:
            return f"I was reviewing {lead.business_name}'s online presence and noticed some opportunities to capture more leads."
        else:
            return f"I came across {lead.business_name} and noticed your lead capture could be optimized."
    
    def _generate_impact(
        self,
        lead,
        proof,
        variant: OutreachVariant,
    ) -> str:
        """
        Generate impact section (money/loss framing).
        Requirements: 8.3
        """
        if proof and proof.audit_bullets:
            for bullet in proof.audit_bullets:
                if bullet.type == "upside" and bullet.estimate:
                    if variant == OutreachVariant.A:
                        return f"Based on similar {lead.category or 'service'} businesses, this typically means you could {bullet.estimate.lower()}."
                    else:
                        return f"For businesses like yours, fixing this usually helps {bullet.estimate.lower()}."
        
        # Fallback impact
        if variant == OutreachVariant.A:
            return "Based on similar businesses, optimizing lead capture typically recovers 15-25% of missed opportunities."
        else:
            return "Most businesses in your space see a 15-25% improvement after optimizing their lead capture."
    
    def _generate_offer(
        self,
        lead,
        tier: LeadTier,
        variant: OutreachVariant,
    ) -> str:
        """
        Generate offer section (done-for-you solution).
        Requirements: 8.3
        """
        if tier == LeadTier.A:
            if variant == OutreachVariant.A:
                return "We help businesses like yours recover this lost revenue by optimizing lead capture without changing your ad spend."
            else:
                return "I specialize in helping service businesses capture more leads from their existing traffic."
        else:
            if variant == OutreachVariant.A:
                return "We've helped similar businesses improve their lead capture with minimal effort on their end."
            else:
                return "I'd be happy to share some quick wins that could help."
    
    def _generate_cta(
        self,
        tier: LeadTier,
        variant: OutreachVariant,
    ) -> str:
        """
        Generate CTA section (single action).
        Requirements: 8.3
        """
        if tier == LeadTier.A:
            if variant == OutreachVariant.A:
                return "Worth a 15-minute conversation? Reply YES and I'll send a calendar link."
            else:
                return "Would you be open to a quick call this week? Just reply with a good time."
        else:
            if variant == OutreachVariant.A:
                return "Would you like me to send over a few specific suggestions? Just reply YES."
            else:
                return "Interested in learning more? Reply and I'll share some ideas."
    
    def _generate_subject(
        self,
        lead,
        variant: OutreachVariant,
    ) -> str:
        """Generate email subject line."""
        if variant == OutreachVariant.A:
            return f"Quick question about {lead.business_name}'s lead capture"
        else:
            return f"Noticed something on your website"
    
    def _save_outreach(self, outreach: OutreachQueue) -> None:
        """Save outreach to database."""
        data = outreach.model_dump()
        data["outreach_id"] = str(outreach.outreach_id)
        data["lead_id"] = str(outreach.lead_id)
        data["created_at"] = datetime.utcnow().isoformat()
        
        # Convert enums
        data["channel"] = outreach.channel.value if hasattr(outreach.channel, 'value') else outreach.channel
        data["variant"] = outreach.variant.value if hasattr(outreach.variant, 'value') else outreach.variant
        data["status"] = outreach.status.value if hasattr(outreach.status, 'value') else outreach.status
        
        # Convert personalization to dict
        data["personalization"] = {
            "decision_maker_name": outreach.personalization.decision_maker_name,
            "business_name": outreach.personalization.business_name,
            "category": outreach.personalization.category,
            "evidence": outreach.personalization.evidence,
        }
        
        self._db.create_outreach(data)


# Create singleton instance for LangGraph node
_outreach_agent = OutreachAgent()


def outreach_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for outreach."""
    return _outreach_agent(state)
