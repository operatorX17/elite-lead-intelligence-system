"""
Enrichment Agent - Contact and context extraction.
Requirements: 4.1-4.6
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import logging

from src.agents.base import BaseAgent, CircuitBreakerMixin
from src.graph.state import LeadGraphState
from src.db.models import EnrichmentData
from src.tools.apify import ApifyClient


logger = logging.getLogger(__name__)


# Tech signal patterns
BOOKING_PROVIDERS = {
    "calendly": r"calendly\.com",
    "acuity": r"acuityscheduling\.com",
    "square": r"squareup\.com|square\.site",
    "setmore": r"setmore\.com",
    "booksy": r"booksy\.com",
    "vagaro": r"vagaro\.com",
    "mindbody": r"mindbodyonline\.com",
}

CRM_HINTS = {
    "hubspot": r"hubspot|hs-scripts",
    "salesforce": r"salesforce|pardot",
    "zoho": r"zoho",
    "pipedrive": r"pipedrive",
    "freshsales": r"freshsales",
}

CHAT_WIDGETS = {
    "intercom": r"intercom",
    "drift": r"drift\.com|driftt",
    "zendesk": r"zendesk|zopim",
    "crisp": r"crisp\.chat",
    "tawk": r"tawk\.to",
    "livechat": r"livechatinc",
    "freshchat": r"freshchat",
}

FORM_TOOLS = {
    "typeform": r"typeform\.com",
    "jotform": r"jotform\.com",
    "google_forms": r"docs\.google\.com/forms",
    "wufoo": r"wufoo\.com",
    "formstack": r"formstack\.com",
}


class EnrichmentAgent(BaseAgent, CircuitBreakerMixin):
    """
    Enrichment Agent for contact and context extraction.
    
    Requirements:
    - 4.1: Extract technology signals (booking_provider, crm_hint, chat_widget, form_tool)
    - 4.2: Extract decision-maker hints from owner names, team pages, LinkedIn
    - 4.3: Normalize phone and email formats, validate email domains
    - 4.4: Compute enrichment_confidence score (0-1)
    - 4.5: Compute contact_quality_score (0-100)
    - 4.6: Deduplicate and merge duplicate contacts
    """
    
    def __init__(self):
        super().__init__("enrichment")
        self._apify = ApifyClient()
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process enrichment for a lead."""
        if not state.lead:
            self._logger.warning("No lead data to enrich")
            return state
        
        state.current_stage = "enrichment"
        
        # Extract tech signals from website
        tech_signals = {}
        if state.lead.website:
            tech_signals = self._extract_tech_signals(state.lead.website)
        
        # Extract decision maker info
        decision_maker = self._extract_decision_maker(state.lead)
        
        # Normalize contacts
        normalized_phone = self._normalize_phone(state.lead.phone)
        validated_emails = self._validate_emails(state.lead.emails_found)
        
        # Compute scores
        enrichment_confidence = self._compute_enrichment_confidence(
            tech_signals, decision_maker, normalized_phone, validated_emails
        )
        contact_quality_score = self._compute_contact_quality_score(
            normalized_phone, validated_emails, decision_maker
        )
        
        # Create enrichment data
        enrichment = EnrichmentData(
            lead_id=state.lead.lead_id,
            enrichment_confidence=enrichment_confidence,
            booking_provider=tech_signals.get("booking_provider"),
            crm_hint=tech_signals.get("crm_hint"),
            chat_widget=tech_signals.get("chat_widget"),
            form_tool=tech_signals.get("form_tool"),
            decision_maker_name=decision_maker.get("name"),
            decision_maker_linkedin=decision_maker.get("linkedin"),
            contact_quality_score=contact_quality_score,
            normalized_phone=normalized_phone,
            validated_emails=validated_emails,
        )
        
        state.enrichment = enrichment
        
        # Save to database
        self._save_enrichment(enrichment)
        
        return state
    
    def _extract_tech_signals(self, website: str) -> Dict[str, str]:
        """
        Extract technology signals from website.
        Requirements: 4.1
        """
        signals = {}
        
        try:
            # Crawl website for tech signals
            crawl_result = self._apify.crawl_website(website, max_pages=5)
            
            # Get page content (simplified - in production would analyze HTML)
            page_content = str(crawl_result).lower()
            
            # Check for booking providers
            for provider, pattern in BOOKING_PROVIDERS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["booking_provider"] = provider
                    break
            
            # Check for CRM hints
            for crm, pattern in CRM_HINTS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["crm_hint"] = crm
                    break
            
            # Check for chat widgets
            for widget, pattern in CHAT_WIDGETS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["chat_widget"] = widget
                    break
            
            # Check for form tools
            for tool, pattern in FORM_TOOLS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["form_tool"] = tool
                    break
            
        except Exception as e:
            self._logger.error(f"Error extracting tech signals: {e}")
        
        return signals
    
    def _extract_decision_maker(self, lead) -> Dict[str, str]:
        """
        Extract decision-maker information.
        Requirements: 4.2
        """
        decision_maker = {}
        
        # Try to extract from business name (e.g., "John's Plumbing")
        name_match = re.match(r"^([A-Z][a-z]+(?:'s)?)\s", lead.business_name)
        if name_match:
            potential_name = name_match.group(1).replace("'s", "")
            if len(potential_name) > 2:
                decision_maker["name"] = potential_name
        
        # In production, would also:
        # - Scrape team/about pages
        # - Search LinkedIn
        # - Use data enrichment APIs
        
        return decision_maker
    
    def _normalize_phone(self, phone: Optional[str]) -> Optional[str]:
        """
        Normalize phone number format.
        Requirements: 4.3
        """
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Handle US numbers
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        elif len(digits) > 10:
            return f"+{digits}"
        
        return None
    
    def _validate_emails(self, emails: List[str]) -> List[str]:
        """
        Validate email addresses.
        Requirements: 4.3
        """
        validated = []
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        # Disposable email domains to filter out
        disposable_domains = {
            'tempmail.com', 'throwaway.com', 'mailinator.com',
            'guerrillamail.com', '10minutemail.com',
        }
        
        for email in emails:
            email = email.lower().strip()
            
            # Check format
            if not re.match(email_pattern, email):
                continue
            
            # Check for disposable domains
            domain = email.split('@')[1]
            if domain in disposable_domains:
                continue
            
            # In production, would also check MX records
            validated.append(email)
        
        return list(set(validated))  # Deduplicate
    
    def _compute_enrichment_confidence(
        self,
        tech_signals: Dict[str, str],
        decision_maker: Dict[str, str],
        normalized_phone: Optional[str],
        validated_emails: List[str],
    ) -> float:
        """
        Compute enrichment confidence score.
        Requirements: 4.4
        """
        score = 0.0
        
        # Tech signals contribute 0.3
        if tech_signals:
            score += 0.1 * len(tech_signals)
            score = min(score, 0.3)
        
        # Decision maker contributes 0.3
        if decision_maker.get("name"):
            score += 0.15
        if decision_maker.get("linkedin"):
            score += 0.15
        
        # Contact info contributes 0.4
        if normalized_phone:
            score += 0.2
        if validated_emails:
            score += 0.2
        
        return min(score, 1.0)
    
    def _compute_contact_quality_score(
        self,
        normalized_phone: Optional[str],
        validated_emails: List[str],
        decision_maker: Dict[str, str],
    ) -> int:
        """
        Compute contact quality score.
        Requirements: 4.5
        
        Score breakdown:
        - has_validated_email: +40
        - has_normalized_phone: +30
        - has_decision_maker: +20
        - has_linkedin: +10
        """
        score = 0
        
        if validated_emails:
            score += 40
        
        if normalized_phone:
            score += 30
        
        if decision_maker.get("name"):
            score += 20
        
        if decision_maker.get("linkedin"):
            score += 10
        
        return min(score, 100)
    
    def _save_enrichment(self, enrichment: EnrichmentData) -> None:
        """Save enrichment data to database."""
        data = enrichment.model_dump()
        data["lead_id"] = str(enrichment.lead_id)
        data["created_at"] = datetime.utcnow().isoformat()
        
        self._db.save_enrichment_data(data)


# Create singleton instance for LangGraph node
_enrichment_agent = EnrichmentAgent()


def enrichment_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for enrichment."""
    return _enrichment_agent(state)
