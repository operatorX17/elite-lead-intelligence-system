"""
Audit Agent - Precision audit and proof generation via Steel.dev.
Requirements: 6.1-6.7
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import base64

from src.agents.base import BaseAgent, CircuitBreakerMixin
from src.graph.state import LeadGraphState
from src.db.models import ProofArtifact, AuditBullet
from src.tools.steel import SteelClient
from src.tools.llm import get_llm_client


logger = logging.getLogger(__name__)


class AuditAgent(BaseAgent, CircuitBreakerMixin):
    """
    Audit Agent for proof generation via Steel.dev browser automation.
    
    Requirements:
    - 6.1: Trigger Steel_Task when lead exceeds score threshold
    - 6.2: Open landing_page_url in a real browser
    - 6.3: Interact like a human (scroll, click CTAs, open forms)
    - 6.4: Extract phone_visibility, form_field_count, booking_link, etc.
    - 6.5: Capture screenshots of hero section and CTA/form/phone section
    - 6.6: Save artifacts to object storage and link URLs in database
    - 6.7: Generate Proof_Pack with 3 audit_bullets
    """
    
    SCORE_THRESHOLD = 70  # Minimum score to trigger audit
    
    def __init__(self):
        super().__init__("audit")
        self._steel = SteelClient()
        self._llm = get_llm_client()
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process audit for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data for audit")
            return state
        
        # Check kill switch
        if self._check_kill_switch():
            self._logger.warning("Audit kill switch is active")
            state["should_skip_audit"] = True
            return state
        
        # Check circuit breaker
        if self._is_circuit_open("audit"):
            self._logger.warning("Audit circuit breaker is open")
            state["should_skip_audit"] = True
            return state
        
        # Check budget
        if not self._check_budget("browser"):
            self._logger.warning("Browser budget exceeded")
            state["should_skip_audit"] = True
            state["last_error"] = "budget_exceeded"
            return state
        
        lead = state["lead"]
        scoring = state.get("scoring", {})
        intent = state.get("intent", {})
        
        # Check score threshold (Requirement 6.1)
        should_audit = False
        if scoring and scoring.get("final_score", 0) >= self.SCORE_THRESHOLD:
            should_audit = True
        elif scoring and scoring.get("lead_tier") == "A":
            should_audit = True
        elif intent:
            avg_score = (intent.get("intent_score", 0) + intent.get("leak_score", 0)) / 2
            if avg_score >= self.SCORE_THRESHOLD:
                should_audit = True
        
        if not should_audit:
            self._logger.info(f"Lead {lead.get('lead_id')} below audit threshold, skipping")
            state["should_skip_audit"] = True
            return state
        
        state["current_stage"] = "audit"
        
        # Get landing page URL
        landing_page_url = lead.get("landing_page_url") or lead.get("website")
        if not landing_page_url:
            self._logger.warning("No landing page URL for audit")
            state["should_skip_audit"] = True
            return state
        
        try:
            # Run Steel audit
            audit_result = self._steel.audit_landing_page(landing_page_url)
            
            if not audit_result.get("success"):
                self._record_failure("audit")
                state["last_error"] = audit_result.get("error", "Audit failed")
                return state
            
            # Save screenshots to storage
            hero_url = self._save_screenshot(
                lead.get("lead_id"),
                "hero",
                audit_result.get("hero_screenshot", b""),
            )
            cta_url = self._save_screenshot(
                lead.get("lead_id"),
                "cta",
                audit_result.get("cta_screenshot", b""),
            )
            
            # Generate audit bullets
            extraction_data = audit_result.get("extraction_data", {})
            audit_bullets = self._generate_audit_bullets(lead, extraction_data)
            
            # Create proof artifact dict
            proof = {
                "lead_id": lead.get("lead_id"),
                "hero_screenshot_url": hero_url,
                "cta_screenshot_url": cta_url,
                "audit_bullets": audit_bullets,
                "extraction_data": extraction_data,
            }
            
            state["proof"] = proof
            
            # Save to database
            self._save_proof(proof)
            
            self._record_success("audit")
            self._increment_usage("browser")
            
        except Exception as e:
            self._logger.error(f"Audit error: {e}")
            self._record_failure("audit")
            state["last_error"] = str(e)
        
        return state
    
    def _save_screenshot(
        self,
        lead_id,
        screenshot_type: str,
        data: bytes,
    ) -> Optional[str]:
        """
        Save screenshot to storage.
        Requirements: 6.6
        """
        if not data:
            return None
        
        # In production, would upload to S3/Supabase Storage
        # For now, return a placeholder URL
        # TODO: Implement actual storage upload
        
        filename = f"{lead_id}/{screenshot_type}.png"
        
        # Placeholder - would be actual S3 URL
        return f"https://storage.zrai.io/artifacts/{filename}"
    
    def _generate_audit_bullets(
        self,
        lead: Dict[str, Any],
        extraction_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate proof pack audit bullets.
        Requirements: 6.7
        
        Each bullet has:
        - type: 'leak', 'fix', or 'upside'
        - evidence/specific/estimate based on type
        """
        bullets = []
        
        # Analyze extraction data for leak evidence
        phone_visibility = extraction_data.get("phone_visibility", "none")
        form_field_count = extraction_data.get("form_field_count", 0)
        booking_link = extraction_data.get("booking_link")
        chat_widget = extraction_data.get("chat_widget")
        after_hours_capture = extraction_data.get("after_hours_capture", False)
        
        # Generate leak bullet
        leak_evidence = None
        if phone_visibility == "below_fold":
            leak_evidence = "Phone number hidden below the fold - visitors may leave before finding it"
        elif phone_visibility == "hidden":
            leak_evidence = "Phone number requires click to reveal - adds friction for callers"
        elif phone_visibility == "none":
            leak_evidence = "No visible phone number on landing page"
        elif not booking_link and not chat_widget:
            leak_evidence = "No online booking or chat widget for after-hours lead capture"
        elif form_field_count > 5:
            leak_evidence = f"Contact form has {form_field_count} fields - high friction may reduce submissions"
        
        if leak_evidence:
            bullets.append({
                "type": "leak",
                "evidence": leak_evidence,
            })
        
        # Generate fix bullet
        fix_specific = None
        if phone_visibility in ["below_fold", "hidden", "none"]:
            fix_specific = "Add prominent phone number in hero section with click-to-call"
        elif not booking_link:
            fix_specific = "Add online booking widget (Calendly, Acuity) for 24/7 scheduling"
        elif not chat_widget:
            fix_specific = "Add chat widget with after-hours auto-response"
        elif form_field_count > 5:
            fix_specific = "Reduce form to essential fields (name, phone, email, message)"
        
        if fix_specific:
            bullets.append({
                "type": "fix",
                "specific": fix_specific,
            })
        
        # Generate upside bullet
        upside_estimate = None
        if phone_visibility in ["below_fold", "hidden", "none"]:
            upside_estimate = "Recover 15-20% of missed calls by making phone prominent"
        elif not booking_link:
            upside_estimate = "Capture 10-15% more leads with 24/7 online booking"
        elif not after_hours_capture:
            upside_estimate = "Capture after-hours leads (30-40% of traffic) with chat/booking"
        elif form_field_count > 5:
            upside_estimate = "Increase form submissions 20-30% by reducing friction"
        
        if upside_estimate:
            bullets.append({
                "type": "upside",
                "estimate": upside_estimate,
            })
        
        # Ensure we have 3 bullets
        while len(bullets) < 3:
            if len(bullets) == 0:
                bullets.append({
                    "type": "leak",
                    "evidence": "Landing page could benefit from conversion optimization",
                })
            elif len(bullets) == 1:
                bullets.append({
                    "type": "fix",
                    "specific": "Implement lead capture best practices",
                })
            else:
                bullets.append({
                    "type": "upside",
                    "estimate": "Potential 10-20% improvement in lead capture rate",
                })
        
        return bullets[:3]  # Return exactly 3 bullets
    
    def _save_proof(self, proof: Dict[str, Any]) -> None:
        """Save proof artifact to database."""
        data = dict(proof)
        data["lead_id"] = str(proof.get("lead_id", ""))
        data["generated_at"] = datetime.utcnow().isoformat()
        
        # audit_bullets is already a list of dicts
        
        self._db.save_proof_artifact(data)


# Create singleton instance for LangGraph node
_audit_agent = AuditAgent()


def audit_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for audit."""
    return _audit_agent(state)
