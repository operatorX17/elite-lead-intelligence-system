"""
Discovery Agent - Bulk ingestion of business data via Apify.
Requirements: 3.1-3.8
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4
import logging

from src.agents.base import BaseAgent, CircuitBreakerMixin, RetryMixin
from src.graph.state import LeadGraphState
from src.db.models import Lead, CTAType, LeadLifecycleState
from src.tools.apify import ApifyClient


logger = logging.getLogger(__name__)


class DiscoveryAgent(BaseAgent, CircuitBreakerMixin, RetryMixin):
    """
    Discovery Agent for bulk business data ingestion.
    
    Requirements:
    - 3.1: Use Apify Actors to scrape Meta Ads Library
    - 3.2: Extract business_name, website_url, cta_type, ad_start_date, etc.
    - 3.3: Use Apify Actors to scrape Google Maps listings
    - 3.4: Extract business_name, category, location, phone, website, review_count
    - 3.5: Crawl contact pages for emails, phones, booking links
    - 3.6: Capture Facebook and Instagram page URLs
    - 3.7: Create Canonical_Lead record with normalized schema
    - 3.8: Store all required fields
    """
    
    def __init__(self):
        super().__init__("discovery")
        self._apify = ApifyClient()
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process discovery for a lead."""
        # Check kill switch
        if self._check_kill_switch():
            self._logger.warning("Discovery kill switch is active")
            state["should_skip_audit"] = True
            state["should_skip_outreach"] = True
            return state
        
        # Check circuit breaker
        if self._is_circuit_open("discovery"):
            self._logger.warning("Discovery circuit breaker is open")
            state["should_skip_audit"] = True
            return state
        
        # Check budget
        if not self._check_budget("scraper"):
            self._logger.warning("Scraper budget exceeded")
            state["last_error"] = "budget_exceeded"
            return state
        
        state["current_stage"] = "discovery"
        
        # If we already have a lead, just return
        if state.get("lead"):
            return state
        
        # This agent is typically called in batch mode
        # For single lead processing, we assume the lead data is in metadata
        metadata = state.get("metadata", {})
        lead_data = metadata.get("raw_lead_data") if metadata else None
        if lead_data:
            lead = self._create_canonical_lead(lead_data)
            state["lead"] = lead
            
            # Save to database
            self._save_lead(lead)
            
            self._record_success("discovery")
            self._increment_usage("scraper")
        
        return state
    
    def discover_from_meta_ads(
        self,
        keywords: List[str],
        geo: Optional[Dict[str, str]] = None,
        limit: int = 100,
        auto_process: bool = True,
    ) -> List[Lead]:
        """
        Discover businesses from Meta Ads Library.
        Requirements: 3.1, 3.2
        
        Args:
            keywords: Search keywords
            geo: Geographic filter
            limit: Max results
            auto_process: If True, automatically run enrichment/intent/scoring (100X upgrade)
        """
        if not self._check_budget("scraper"):
            raise Exception("Scraper budget exceeded")
        
        try:
            raw_results = self._apify.run_meta_ads_scraper(
                keywords=keywords,
                geo=geo,
                limit=limit,
            )
            
            leads = []
            for raw in raw_results:
                lead = self._parse_meta_ads_result(raw)
                if lead and not self._is_duplicate(lead):
                    self._save_lead(lead)
                    leads.append(lead)
                    
                    # Auto-process if enabled (100X upgrade)
                    if auto_process:
                        try:
                            result = self.auto_process_lead(lead)
                            self._logger.info(
                                f"Auto-processed {lead.business_name}: "
                                f"Tier {result.get('tier')}, Score {result.get('final_score')}"
                            )
                        except Exception as e:
                            self._logger.warning(f"Auto-process failed for {lead.business_name}: {e}")
            
            self._increment_usage("scraper")
            self._record_success("discovery")
            
            return leads
            
        except Exception as e:
            self._record_failure("discovery")
            raise
    
    def discover_from_google_maps(
        self,
        keywords: List[str],
        geo: Dict[str, str],
        limit: int = 100,
        auto_process: bool = True,
        skip_duplicate_check: bool = False,
        detailed_scrape: bool = False,
    ) -> List[Lead]:
        """
        Discover businesses from Google Maps.
        Requirements: 3.3, 3.4
        
        Args:
            keywords: Search keywords
            geo: Geographic filter (city, state, country)
            limit: Max results
            auto_process: If True, automatically run enrichment/intent/scoring (100X upgrade)
            skip_duplicate_check: If True, don't filter duplicates (for intelligence reports)
        """
        if not self._check_budget("scraper"):
            raise Exception("Scraper budget exceeded")
        
        try:
            raw_results = self._apify.run_google_maps_scraper(
                keywords=keywords,
                geo=geo,
                limit=limit,
                detailed=detailed_scrape,
            )
            
            leads = []
            for raw in raw_results:
                self._logger.info(f"Processing raw result: {raw.get('title', 'NO TITLE')}")
                lead = self._parse_google_maps_result(raw)
                if lead:
                    self._logger.info(f"Parsed lead: {lead.business_name}")
                    is_duplicate = self._is_duplicate(lead)

                    # Persist only new leads, but allow repeat discovery runs to
                    # return already-known matches in the response payload.
                    if not is_duplicate:
                        self._save_lead(lead)
                        
                        # Store raw Apify data in lead_state metadata for enrichment agent
                        self._db.save_lead_state({
                            "lead_id": str(lead.lead_id),
                            "current_stage": "discovery",
                            "last_node": "discovery",
                            "retry_count": 0,
                            "metadata": {
                                "raw_apify_data": {
                                    "reviewsCount": raw.get("reviewsCount", 0),
                                    "totalScore": raw.get("totalScore"),
                                    "reviewsDistribution": raw.get("reviewsDistribution"),
                                    "openingHours": raw.get("openingHours"),
                                    "reviews": raw.get("reviews", []),
                                    "questionsAndAnswers": raw.get("questionsAndAnswers"),
                                    "peopleAlsoSearch": raw.get("peopleAlsoSearch"),
                                    "imageCategories": raw.get("imageCategories"),
                                    "webResults": raw.get("webResults"),
                                    "tableReservationLinks": raw.get("tableReservationLinks"),
                                }
                            },
                        })

                        # Auto-process if enabled (100X upgrade)
                        if auto_process:
                            try:
                                result = self.auto_process_lead(lead)
                                self._logger.info(
                                    f"Auto-processed {lead.business_name}: "
                                    f"Tier {result.get('tier')}, Score {result.get('final_score')}"
                                )
                            except Exception as e:
                                self._logger.warning(f"Auto-process failed for {lead.business_name}: {e}")

                    if skip_duplicate_check or not is_duplicate:
                        leads.append(lead)
            
            self._increment_usage("scraper")
            self._record_success("discovery")
            
            return leads
            
        except Exception as e:
            self._record_failure("discovery")
            raise
    
    def _parse_meta_ads_result(self, raw: Dict[str, Any]) -> Optional[Lead]:
        """
        Parse Meta Ads Library result into Canonical Lead.
        Requirements: 3.2
        """
        try:
            # Extract CTA type
            cta_raw = raw.get("cta_type", "").upper()
            cta_type = None
            if "CALL" in cta_raw:
                cta_type = CTAType.CALL
            elif "FORM" in cta_raw or "LEAD" in cta_raw:
                cta_type = CTAType.FORM
            elif "BOOK" in cta_raw or "SCHEDULE" in cta_raw:
                cta_type = CTAType.BOOK
            elif cta_raw:
                cta_type = CTAType.OTHER
            
            # Parse dates
            ad_start_date = None
            if raw.get("ad_start_date"):
                try:
                    ad_start_date = datetime.fromisoformat(raw["ad_start_date"])
                except:
                    pass
            
            return Lead(
                lead_id=uuid4(),
                business_name=raw.get("page_name") or raw.get("business_name", "Unknown"),
                category=raw.get("category"),
                location=raw.get("location"),
                geo_tags=raw.get("geo_tags", []),
                website=raw.get("website_url"),
                landing_page_url=raw.get("landing_page_url") or raw.get("website_url"),
                phone=raw.get("phone"),
                emails_found=raw.get("emails", []),
                facebook_page=raw.get("facebook_page") or raw.get("page_url"),
                instagram=raw.get("instagram"),
                ads_active=raw.get("ad_active", True),
                ad_start_date=ad_start_date,
                ad_last_seen=datetime.utcnow() if raw.get("ad_active") else None,
                cta_type=cta_type,
                lead_form_detected=raw.get("lead_form_detected", False),
                lead_lifecycle_state=LeadLifecycleState.NEW,
            )
        except Exception as e:
            self._logger.error(f"Error parsing Meta Ads result: {e}")
            return None
    
    def _parse_google_maps_result(self, raw: Dict[str, Any]) -> Optional[Lead]:
        """
        Parse Google Maps result into Canonical Lead.
        Requirements: 3.4
        """
        try:
            # Extract location
            location_parts = []
            if raw.get("city"):
                location_parts.append(raw["city"])
            if raw.get("state"):
                location_parts.append(raw["state"])
            if raw.get("country"):
                location_parts.append(raw["country"])
            location = ", ".join(location_parts) if location_parts else raw.get("address")
            
            # Extract geo tags
            geo_tags = []
            if raw.get("city"):
                geo_tags.append(raw["city"])
            if raw.get("state"):
                geo_tags.append(raw["state"])
            
            # Create lead - return Lead object
            lead = Lead(
                lead_id=uuid4(),
                business_name=raw.get("title") or raw.get("name", "Unknown"),
                category=raw.get("categoryName") or raw.get("category") or (raw.get("categories", [None])[0] if raw.get("categories") else None),
                location=location,
                geo_tags=geo_tags,
                website=raw.get("website"),
                landing_page_url=raw.get("website"),
                phone=raw.get("phone"),
                emails_found=raw.get("emails", []),
                facebook_page=raw.get("facebooks", [None])[0] if raw.get("facebooks") else None,
                instagram=raw.get("instagrams", [None])[0] if raw.get("instagrams") else None,
                ads_active=False,
                lead_lifecycle_state=LeadLifecycleState.NEW,
                # Volume signals from Google Maps
                reviews_count=raw.get("reviewsCount") or raw.get("reviews_count"),
                rating=raw.get("totalScore") or raw.get("rating"),
            )
            
            return lead
            
        except Exception as e:
            self._logger.error(f"Error parsing Google Maps result: {e}")
            return None
    
    def _create_canonical_lead(self, raw: Dict[str, Any]) -> Lead:
        """
        Create a Canonical Lead from raw data.
        Requirements: 3.7, 3.8
        """
        # Determine CTA type
        cta_type = None
        cta_raw = raw.get("cta_type", "")
        if cta_raw:
            cta_map = {
                "call": CTAType.CALL,
                "form": CTAType.FORM,
                "book": CTAType.BOOK,
            }
            cta_type = cta_map.get(cta_raw.lower(), CTAType.OTHER)
        
        return Lead(
            lead_id=uuid4(),
            business_name=raw.get("business_name", "Unknown"),
            category=raw.get("category"),
            location=raw.get("location"),
            geo_tags=raw.get("geo_tags", []),
            website=raw.get("website"),
            landing_page_url=raw.get("landing_page_url") or raw.get("website"),
            phone=raw.get("phone"),
            emails_found=raw.get("emails_found", []),
            facebook_page=raw.get("facebook_page"),
            instagram=raw.get("instagram"),
            ads_active=raw.get("ads_active", False),
            ad_start_date=raw.get("ad_start_date"),
            ad_last_seen=raw.get("ad_last_seen"),
            cta_type=cta_type,
            lead_form_detected=raw.get("lead_form_detected", False),
            lead_lifecycle_state=LeadLifecycleState.NEW,
        )
    
    def _is_duplicate(self, lead: Lead) -> bool:
        """
        Check if lead is a duplicate.
        Deduplication Strategy: Hash business_name + location + website
        """
        return self._db.check_lead_exists(
            business_name=lead.business_name,
            location=lead.location or "",
            website=lead.website,
        )
    
    def _save_lead(self, lead: Lead) -> None:
        """Save lead to database."""
        lead_dict = lead.model_dump()
        lead_dict["lead_id"] = str(lead.lead_id)
        lead_dict["created_at"] = datetime.utcnow().isoformat()
        lead_dict["updated_at"] = datetime.utcnow().isoformat()
        
        # Convert enums to strings
        if lead_dict.get("cta_type"):
            lead_dict["cta_type"] = str(lead_dict["cta_type"])
        if lead_dict.get("lead_lifecycle_state"):
            lead_dict["lead_lifecycle_state"] = str(lead_dict["lead_lifecycle_state"])
        
        self._db.create_lead(lead_dict)
        
        # Create initial lead state
        self._db.save_lead_state({
            "lead_id": str(lead.lead_id),
            "current_stage": "discovery",
            "last_node": "discovery",
            "retry_count": 0,
            "metadata": {},
        })
    
    def auto_process_lead(self, lead: Lead) -> Dict[str, Any]:
        """
        Auto-process a newly discovered lead through enrichment → intent → scoring.
        Part of 100X upgrade - ensures leads don't sit idle after discovery.
        
        Returns dict with processing results.
        """
        from src.agents.enrichment import EnrichmentAgent
        from src.agents.intent import IntentAgent
        from src.agents.scoring import ScoringAgent
        from src.graph.state import LeadGraphState
        
        # Create state for this lead
        lead_dict = lead.model_dump()
        lead_dict["lead_id"] = str(lead.lead_id)
        
        state: LeadGraphState = {
            "lead_id": lead_dict["lead_id"],
            "thread_id": f"auto-{lead_dict['lead_id']}",
            "lead": lead_dict,
            "current_stage": "enrichment",
            "last_node": "discovery",
            "enrichment": {},
            "intent": {},
            "scoring": {},
            "proof": {},
            "outreach_messages": [],
            "conversation_transcript": [],
            "conversation_entities": {},
            "errors": [],
            "retry_count": 0,
            "should_skip_audit": True,
            "should_skip_outreach": True,
            "is_disqualified": False,
            "is_escalated": False,
            "is_complete": False,
            "requires_approval": False,
            "metadata": {"auto_processed": True},
            "messages": [],
        }
        
        result = {
            "lead_id": lead_dict["lead_id"],
            "business_name": lead_dict["business_name"],
            "success": False,
            "tier": None,
            "final_score": None,
        }
        
        try:
            # Run enrichment
            enrichment_agent = EnrichmentAgent()
            state = enrichment_agent.process(state)
            
            # Run intent
            intent_agent = IntentAgent()
            state = intent_agent.process(state)
            
            # Run scoring
            scoring_agent = ScoringAgent()
            state = scoring_agent.process(state)
            
            result["success"] = True
            result["tier"] = state.get("scoring", {}).get("lead_tier")
            result["final_score"] = state.get("scoring", {}).get("final_score")
            
        except Exception as e:
            self._logger.error(f"Auto-process failed for {lead_dict['business_name']}: {e}")
            result["error"] = str(e)
            import traceback
            traceback.print_exc()
        
        return result


# Create singleton instance for LangGraph node
_discovery_agent = DiscoveryAgent()


def discovery_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for discovery."""
    return _discovery_agent(state)
