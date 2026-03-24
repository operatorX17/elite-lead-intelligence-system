"""
Scoring Agent - deterministic clinic opportunity scoring.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

from src.agents.base import BaseAgent
from src.graph.state import LeadGraphState


logger = logging.getLogger(__name__)


class ScoringAgent(BaseAgent):
    """
    Score clinics on close-now opportunity rather than legacy mixed heuristics.

    Final formula:
    demand_score * 0.35
    + trust_score * 0.25
    + leak_score * 0.20
    + serviceability_score * 0.10
    + offer_fit_score * 0.10

    Strong clinics with real demand and trust should not collapse into mediocre
    final scores just because leakage is moderate instead of catastrophic.
    """

    DEFAULT_WEIGHTS = {
        "demand_score": 0.35,
        "trust_score": 0.25,
        "leak_score": 0.20,
        "serviceability_score": 0.10,
        "offer_fit_score": 0.10,
    }

    TIER_A_THRESHOLD = 70
    TIER_B_THRESHOLD = 50

    HIGH_TICKET_HINTS = (
        "skin",
        "clinic",
        "doctor",
        "physician",
        "medical",
        "hospital",
        "diagnostic",
        "fertility",
        "ivf",
        "dermatology",
        "dermatologist",
        "aesthetic",
        "laser",
        "hair",
        "cosmetic",
        "plastic surgery",
        "dental",
        "dental clinic",
        "medical dermatology",
    )

    def __init__(self):
        super().__init__("scoring")

    def process(self, state: LeadGraphState) -> LeadGraphState:
        if not state.get("lead"):
            self._logger.warning("No lead data for scoring")
            return state

        state["current_stage"] = "scoring"

        lead = state["lead"]
        enrichment = state.get("enrichment", {})
        intent = state.get("intent", {})
        proof = state.get("proof", {})
        metadata = state.get("metadata", {})
        analysis_bundle = metadata.get("intelligence") or metadata.get("analysis_bundle") or {}

        signal_facts = metadata.get("signal_facts") or analysis_bundle.get("facts") or self._build_signal_facts(
            lead=lead,
            enrichment=enrichment,
            intent=intent,
            proof=proof,
            metadata=metadata,
        )
        state["metadata"] = {
            **metadata,
            "signal_facts": signal_facts,
        }

        disqualified, reason = self._check_disqualification(
            lead=lead,
            enrichment=enrichment,
            signal_facts=signal_facts,
        )
        if disqualified:
            scoring = {
                "lead_id": lead.get("lead_id"),
                "final_score": 0,
                "score_breakdown": {
                    "demand_score": 0,
                    "trust_score": 0,
                    "leak_score": 0,
                    "serviceability_score": 0,
                    "offer_fit_score": 0,
                    "total_score": 0,
                },
                "lead_tier": "C",
                "do_not_contact": True,
                "do_not_contact_reason": reason,
            }
            state["scoring"] = scoring
            state["is_disqualified"] = True
            state["should_skip_outreach"] = True
            self._save_scoring(scoring)
            return state

        breakdown = self._compute_score_breakdown(
            lead=lead,
            enrichment=enrichment,
            intent=intent,
            signal_facts=signal_facts,
        )
        final_score = self._compute_final_score(breakdown)
        tier = self._assign_tier(final_score)

        scoring = {
            "lead_id": lead.get("lead_id"),
            "final_score": final_score,
            "score_breakdown": {
                **breakdown,
                "total_score": final_score,
            },
            "lead_tier": tier,
            "do_not_contact": False,
            "do_not_contact_reason": None,
        }

        state["scoring"] = scoring
        if tier == "C":
            state["should_skip_outreach"] = True

        self._save_scoring(scoring)
        return state

    def _build_signal_facts(
        self,
        *,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        intent: Dict[str, Any],
        proof: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        proof_extraction = (proof or {}).get("extraction_data") or {}
        contact_paths = [str(path).lower() for path in (metadata.get("contact_paths") or [])]

        phone_numbers = list(proof_extraction.get("phone_numbers") or [])
        if enrichment.get("normalized_phone"):
            phone_numbers.append(str(enrichment.get("normalized_phone")))
        if lead.get("phone"):
            phone_numbers.append(str(lead.get("phone")))
        phone_numbers = self._dedupe(phone_numbers)

        social_profiles = dict(proof_extraction.get("social_profiles") or {})
        if lead.get("facebook_page") and not social_profiles.get("facebook"):
            social_profiles["facebook"] = [str(lead.get("facebook_page"))]
        if lead.get("instagram") and not social_profiles.get("instagram"):
            social_profiles["instagram"] = [str(lead.get("instagram"))]

        whatsapp_target = proof_extraction.get("whatsapp_target")
        whatsapp_detected = bool(
            whatsapp_target
            or proof_extraction.get("chat_widget") == "whatsapp"
            or enrichment.get("chat_widget") == "whatsapp"
            or "whatsapp" in contact_paths
        )
        booking_detected = bool(
            proof_extraction.get("booking_detected")
            or proof_extraction.get("booking_link")
            or enrichment.get("booking_provider")
            or "booking" in contact_paths
            or "booking link" in contact_paths
        )
        contact_form_detected = bool(
            proof_extraction.get("contact_form_detected")
            or enrichment.get("form_tool")
            or proof_extraction.get("form_field_count")
            or "contact form" in contact_paths
            or "form" in contact_paths
        )

        ads_verification = metadata.get("ads_verification") or {}
        if ads_verification.get("status") in {"yes", "no", "not_checked"}:
            ads_status = ads_verification.get("status")
        elif lead.get("ad_last_seen") or lead.get("ad_start_date"):
            ads_status = "yes" if lead.get("ads_active") else "not_checked"
        else:
            ads_status = "not_checked"

        services = self._dedupe(
            list(proof_extraction.get("services") or [])
            + ([lead.get("category")] if lead.get("category") else [])
        )
        branch_names = self._dedupe(list(proof_extraction.get("branch_names") or []))
        doctor_names = self._dedupe(list(proof_extraction.get("doctor_names") or []))
        branch_count = proof_extraction.get("branch_count") if isinstance(proof_extraction.get("branch_count"), int) else len(branch_names)
        doctor_count = proof_extraction.get("doctor_count") if isinstance(proof_extraction.get("doctor_count"), int) else len(doctor_names)

        return {
            "phone_visible": bool(phone_numbers) or str(proof_extraction.get("phone_visibility") or "").lower() in {"hero", "visible", "above_fold", "below_fold"},
            "phone_numbers": phone_numbers,
            "booking_detected": booking_detected,
            "booking_target": proof_extraction.get("booking_link"),
            "contact_form_detected": contact_form_detected,
            "whatsapp_detected": whatsapp_detected,
            "whatsapp_target": whatsapp_target,
            "chat_widget_type": "whatsapp" if whatsapp_detected else proof_extraction.get("chat_widget") or enrichment.get("chat_widget"),
            "ads_status": ads_status,
            "ads_channels": list(ads_verification.get("channels") or []),
            "ads_last_seen": ads_verification.get("last_seen") or lead.get("ad_last_seen"),
            "reviews_count": lead.get("reviews_count") or lead.get("review_count"),
            "rating": lead.get("rating") or lead.get("review_rating"),
            "volume_score_inputs": {
                "volume_score": intent.get("volume_score"),
                "peak_busyness": enrichment.get("peak_busyness"),
                "avg_busyness": enrichment.get("avg_busyness"),
                "busy_hours_count": enrichment.get("busy_hours_count"),
                "avg_visit_duration_min": enrichment.get("avg_visit_duration_min"),
            },
            "services": services,
            "social_profiles": social_profiles,
            "multi_clinic": bool(proof_extraction.get("multi_clinic") or branch_count > 1),
            "branch_count": branch_count,
            "branch_names": branch_names,
            "doctor_count": doctor_count,
            "doctor_names": doctor_names,
            "instagram_present": bool(proof_extraction.get("instagram_present") or social_profiles.get("instagram")),
            "youtube_present": bool(proof_extraction.get("youtube_present") or social_profiles.get("youtube")),
            "testimonials_present": bool(proof_extraction.get("testimonials_present")),
            "gallery_present": bool(proof_extraction.get("gallery_present")),
            "content_ready_score": int(proof_extraction.get("content_ready_score") or 0),
            "booking_flow_quality": proof_extraction.get("booking_flow_quality") or ("basic" if booking_detected else "none"),
            "after_hours_capture": bool(proof_extraction.get("after_hours_capture")),
            "instant_response_path": bool(proof_extraction.get("instant_response_path") or whatsapp_detected or booking_detected),
        }

    def _compute_score_breakdown(
        self,
        *,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        intent: Dict[str, Any],
        signal_facts: Dict[str, Any],
    ) -> Dict[str, int]:
        reviews = self._to_int(signal_facts.get("reviews_count"))
        rating = self._to_float(signal_facts.get("rating"))
        branch_count = self._to_int(signal_facts.get("branch_count"))
        doctor_count = self._to_int(signal_facts.get("doctor_count"))
        services = list(signal_facts.get("services") or [])
        social_profiles = signal_facts.get("social_profiles") or {}
        social_count = len([value for value in social_profiles.values() if value])
        ads_status = signal_facts.get("ads_status")
        volume_score = self._to_int(intent.get("volume_score") or (signal_facts.get("volume_score_inputs") or {}).get("volume_score"))
        intent_score = self._to_int(intent.get("intent_score"))
        intent_leak_score = self._to_int(intent.get("leak_score"))
        reactivation_fit = self._to_int(intent.get("reactivation_fit"))
        content_ready_score = self._to_int(signal_facts.get("content_ready_score"))
        booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
        contact_intelligence = signal_facts.get("contact_intelligence") or {}
        contact_quality_score = self._to_int(
            signal_facts.get("contact_quality_score") or contact_intelligence.get("contact_quality_score")
        )
        top_contact = contact_intelligence.get("top_contact") or {}
        alternate_contacts = contact_intelligence.get("alternate_contacts") or []
        branch_contacts = signal_facts.get("branch_contacts") or []

        demand_score = 0
        if reviews >= 500:
            demand_score += 45
        elif reviews >= 200:
            demand_score += 35
        elif reviews >= 100:
            demand_score += 25
        elif reviews >= 50:
            demand_score += 15
        elif reviews >= 20:
            demand_score += 8
        if rating >= 4.7:
            demand_score += 15
        elif rating >= 4.3:
            demand_score += 10
        elif rating >= 4.0:
            demand_score += 6
        demand_score += min(branch_count, 4) * 3
        demand_score += min(len(services), 4) * 2
        if ads_status == "yes":
            demand_score += 10
        demand_score += min(int(volume_score / 10), 10)
        demand_score += min(int(intent_score / 20), 5)

        trust_score = 0
        trust_score += min(doctor_count, 4) * 8
        if rating >= 4.5:
            trust_score += 15
        elif rating >= 4.0:
            trust_score += 10
        if signal_facts.get("testimonials_present"):
            trust_score += 12
        if signal_facts.get("gallery_present"):
            trust_score += 10
        if social_count:
            trust_score += min(social_count, 3) * 5
        trust_score += min(int(content_ready_score / 10), 20)
        if contact_quality_score:
            trust_score += min(int(contact_quality_score / 8), 15)
        if top_contact:
            trust_score += 4
            contact_type = str(top_contact.get("contact_type") or "").lower()
            if contact_type in {"founder_direct", "doctor_direct", "actual_contact"}:
                trust_score += 8
            if top_contact.get("phone"):
                trust_score += 3
            if top_contact.get("email"):
                trust_score += 3
            if top_contact.get("linkedin"):
                trust_score += 3
            confidence = self._to_int(top_contact.get("confidence"))
            if confidence:
                trust_score += min(int(confidence / 15), 6)
        if alternate_contacts:
            trust_score += min(len(alternate_contacts), 4) * 2
        if branch_contacts:
            trust_score += min(len(branch_contacts), 3) * 2
        if reviews >= 200 and rating >= 4.5:
            trust_score = max(trust_score, 35)

        leak_score = 0
        if not signal_facts.get("phone_visible"):
            leak_score += 25
        if not signal_facts.get("whatsapp_detected"):
            leak_score += 15
        if booking_quality == "none":
            leak_score += 20
        elif booking_quality == "weak":
            leak_score += 12
        if not signal_facts.get("contact_form_detected"):
            leak_score += 10
        if not signal_facts.get("after_hours_capture"):
            leak_score += 10
        if not signal_facts.get("instant_response_path"):
            leak_score += 10
        if signal_facts.get("phone_visible") and not any([
            signal_facts.get("whatsapp_detected"),
            signal_facts.get("booking_detected"),
            signal_facts.get("contact_form_detected"),
        ]):
            leak_score += 10
        leak_score = max(leak_score, min(int(intent_leak_score * 0.6), 80))

        serviceability_score = 0
        if self._is_high_ticket_category(str(lead.get("category") or "")):
            serviceability_score += 40
        if signal_facts.get("phone_numbers") or lead.get("website") or lead.get("landing_page_url"):
            serviceability_score += 30
        category = str(lead.get("category") or "").lower()
        if not any(token in category for token in ["emergency only", "24/7 emergency"]):
            serviceability_score += 15
        if services:
            serviceability_score += 15

        offer_fit_score = 0
        if signal_facts.get("multi_clinic"):
            offer_fit_score += 25
        offer_fit_score += min(len(services), 4) * 5
        offer_fit_score += min(int(content_ready_score / 10), 20)
        if booking_quality in {"none", "weak"}:
            offer_fit_score += 15
        if not signal_facts.get("whatsapp_detected"):
            offer_fit_score += 10
        if social_count:
            offer_fit_score += 10
        offer_fit_score += min(int(reactivation_fit / 12), 8)

        return {
            "demand_score": min(demand_score, 100),
            "trust_score": min(trust_score, 100),
            "leak_score": min(leak_score, 100),
            "serviceability_score": min(serviceability_score, 100),
            "offer_fit_score": min(offer_fit_score, 100),
        }

    def _compute_final_score(self, breakdown: Dict[str, int]) -> int:
        score = (
            self.DEFAULT_WEIGHTS["demand_score"] * breakdown.get("demand_score", 0)
            + self.DEFAULT_WEIGHTS["trust_score"] * breakdown.get("trust_score", 0)
            + self.DEFAULT_WEIGHTS["leak_score"] * breakdown.get("leak_score", 0)
            + self.DEFAULT_WEIGHTS["serviceability_score"] * breakdown.get("serviceability_score", 0)
            + self.DEFAULT_WEIGHTS["offer_fit_score"] * breakdown.get("offer_fit_score", 0)
        )
        quality_bonus = self._compute_quality_bonus(breakdown)
        score += quality_bonus
        return int(min(max(score, 0), 100))

    def _compute_quality_bonus(self, breakdown: Dict[str, int]) -> int:
        demand = breakdown.get("demand_score", 0)
        trust = breakdown.get("trust_score", 0)
        leak = breakdown.get("leak_score", 0)
        offer_fit = breakdown.get("offer_fit_score", 0)
        serviceability = breakdown.get("serviceability_score", 0)

        bonus = 0
        if demand >= 70 and trust >= 60:
            bonus += 5
        if demand >= 80 and trust >= 70:
            bonus += 4
        if leak >= 15 and offer_fit >= 40:
            bonus += 3
        if serviceability >= 80 and demand >= 70:
            bonus += 2
        return min(bonus, 12)

    def _assign_tier(self, final_score: int) -> str:
        if final_score >= self.TIER_A_THRESHOLD:
            return "A"
        if final_score >= self.TIER_B_THRESHOLD:
            return "B"
        return "C"

    def _check_disqualification(
        self,
        *,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        signal_facts: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        category = str(lead.get("category") or "").lower()
        if any(token in category for token in ["emergency only", "24/7 emergency"]):
            return True, "Emergency-only service"

        has_phone = bool(signal_facts.get("phone_numbers") or lead.get("phone"))
        has_email = bool(lead.get("emails_found"))
        has_website = bool(lead.get("website") or lead.get("landing_page_url"))
        has_validated_email = bool(enrichment and enrichment.get("validated_emails"))
        has_booking = bool(signal_facts.get("booking_detected"))
        has_contact_form = bool(signal_facts.get("contact_form_detected"))
        if not has_phone and not has_email and not has_website and not has_validated_email and not has_booking and not has_contact_form:
            return True, "No valid contact method"

        return False, None

    def _is_high_ticket_category(self, category: str) -> bool:
        category_lower = str(category or "").lower()
        return any(keyword in category_lower for keyword in self.HIGH_TICKET_HINTS)

    def _to_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    def _to_float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def _dedupe(self, values: list[Any]) -> list[str]:
        seen = set()
        cleaned: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
        return cleaned

    def _save_scoring(self, scoring: Dict[str, Any]) -> None:
        data = dict(scoring)
        data["lead_id"] = str(scoring.get("lead_id", ""))
        data["created_at"] = datetime.utcnow().isoformat()
        self._db.save_scoring_result(data)


_scoring_agent: Optional[ScoringAgent] = None


def _get_scoring_agent() -> ScoringAgent:
    global _scoring_agent
    if _scoring_agent is None:
        _scoring_agent = ScoringAgent()
    return _scoring_agent


def scoring_node(state: LeadGraphState) -> LeadGraphState:
    return _get_scoring_agent()(state)
