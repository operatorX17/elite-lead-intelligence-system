"""
Scoring Agent - deterministic clinic opportunity scoring.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import re

from src.agents.base import BaseAgent
from src.graph.state import LeadGraphState


logger = logging.getLogger(__name__)


class ScoringAgent(BaseAgent):
    """
    Score clinics on close-now opportunity rather than legacy mixed heuristics.

    Final formula:
      demand_score * 0.33
      + trust_score * 0.22
      + leak_score * 0.25
      + serviceability_score * 0.10
      + offer_fit_score * 0.10

    Strong clinics with real demand and trust should not collapse into mediocre
    final scores just because leakage is moderate instead of catastrophic.
    """

    DEFAULT_WEIGHTS = {
        "demand_score": 0.33,
        "trust_score": 0.22,
        "leak_score": 0.25,
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
        scoring = self._gate_judgment_for_sparse_truth(scoring, signal_facts)
        tier = scoring["lead_tier"]

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
        people_intelligence = metadata.get("people_intelligence") or {}
        raw_apify_data = metadata.get("raw_apify_data") or {}
        instagram_profile = dict(
            people_intelligence.get("instagram_profile")
            or metadata.get("signal_facts", {}).get("instagram_profile")
            or {}
        )
        youtube_channel = dict(
            people_intelligence.get("youtube_channel")
            or metadata.get("signal_facts", {}).get("youtube_channel")
            or {}
        )

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
        if instagram_profile and not social_profiles.get("instagram_profile"):
            social_profiles["instagram_profile"] = instagram_profile
        if youtube_channel and not social_profiles.get("youtube_channel"):
            social_profiles["youtube_channel"] = youtube_channel

        whatsapp_target = proof_extraction.get("whatsapp_target") or enrichment.get("whatsapp_target")
        chat_widget_type = str(proof_extraction.get("chat_widget") or enrichment.get("chat_widget") or "").strip().lower()
        whatsapp_detected = bool(
            whatsapp_target
            or chat_widget_type == "whatsapp"
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
        booking_flow_quality = str(
            proof_extraction.get("booking_flow_quality") or ("basic" if booking_detected else "none")
        ).lower()
        instant_response_path = bool(
            proof_extraction.get("instant_response_path")
            or whatsapp_target
            or chat_widget_type in {"whatsapp", "intercom", "drift", "livechat", "crisp", "tawk", "tawk.to", "zendesk"}
            or (booking_detected and contact_form_detected and booking_flow_quality == "strong")
        )

        ads_verification = metadata.get("ads_verification") or {}
        if ads_verification.get("status") in {"yes", "no", "not_checked"}:
            ads_status = ads_verification.get("status")
        elif lead.get("ad_last_seen") or lead.get("ad_start_date"):
            ads_status = "yes" if lead.get("ads_active") else "not_checked"
        else:
            ads_status = "not_checked"

        maps_reviews_count = raw_apify_data.get("reviewsCount")
        maps_rating = raw_apify_data.get("totalScore") or raw_apify_data.get("rating")
        maps_verified = bool(
            raw_apify_data.get("placeId")
            or maps_reviews_count is not None
            or maps_rating is not None
            or raw_apify_data.get("maps_url")
        )

        services = self._dedupe(
            list(proof_extraction.get("services") or [])
            + ([lead.get("category")] if lead.get("category") else [])
        )
        branch_contacts = self._clean_branch_contacts(list(people_intelligence.get("branch_contacts") or []))
        doctor_profiles = [
            profile
            for profile in self._clean_doctor_profiles(list(people_intelligence.get("doctor_profiles") or []))
            if self._is_strong_doctor_profile(profile)
        ]
        branch_contact_names = self._clean_branch_names(
            [contact.get("name") for contact in branch_contacts if isinstance(contact, dict) and contact.get("name")]
        )
        maps_branch_names = self._extract_maps_branch_names(
            raw_apify_data,
            business_name=lead.get("business_name"),
            website=lead.get("website") or lead.get("landing_page_url"),
        )
        doctor_profile_names = self._clean_doctor_names(
            [profile.get("name") for profile in doctor_profiles if isinstance(profile, dict) and profile.get("name")]
        )
        branch_names = branch_contact_names or maps_branch_names or self._clean_branch_names(
            [
                name
                for name in (
                    list(people_intelligence.get("branch_names") or [])
                    + list(proof_extraction.get("branch_names") or [])
                )
                if name in set(maps_branch_names)
            ]
        )
        doctor_names = doctor_profile_names or self._clean_doctor_names(
            list(people_intelligence.get("doctor_names") or [])
            + list(proof_extraction.get("doctor_names") or [])
        )
        branch_count = len(branch_contact_names) if branch_contact_names else len(branch_names)
        doctor_count = len(doctor_profiles) if doctor_profiles else len(doctor_names)
        contact_intelligence = metadata.get("contact_intelligence") or {}
        contact_quality_score = self._to_int(
            metadata.get("contact_quality_score") or contact_intelligence.get("contact_quality_score")
        )

        # Doctor social aggregates: doctors with thousands of personal IG
        # followers count as DEMAND/TRUST proof. We aggregate followers/posts
        # across enriched doctor IG profiles so scoring (and the inspector
        # UI) can reason about them as first-class signals.
        doctor_instagram_profiles: List[Dict[str, Any]] = []
        doctor_followers_total = 0
        doctor_posts_total = 0
        doctor_max_followers = 0
        for profile in doctor_profiles:
            if not isinstance(profile, dict):
                continue
            ig = profile.get("instagram_profile") or {}
            if not isinstance(ig, dict) or not ig:
                continue
            followers = self._to_int(ig.get("followers_count"))
            posts = self._to_int(ig.get("posts_count"))
            if followers <= 0 and posts <= 0:
                continue
            doctor_instagram_profiles.append(ig)
            doctor_followers_total += max(followers, 0)
            doctor_posts_total += max(posts, 0)
            if followers > doctor_max_followers:
                doctor_max_followers = followers

        return {
            "phone_visible": bool(phone_numbers) or str(proof_extraction.get("phone_visibility") or "").lower() in {"hero", "visible", "above_fold", "below_fold"},
            "phone_numbers": phone_numbers,
            "booking_detected": booking_detected,
            "booking_target": proof_extraction.get("booking_link"),
            "contact_form_detected": contact_form_detected,
            "whatsapp_detected": whatsapp_detected,
            "whatsapp_target": whatsapp_target,
            "chat_widget_type": (
                "whatsapp"
                if whatsapp_detected
                else proof_extraction.get("chat_widget") or enrichment.get("chat_widget")
            ),
            "ads_status": ads_status,
            "ads_channels": list(ads_verification.get("channels") or []),
            "ads_last_seen": ads_verification.get("last_seen") or lead.get("ad_last_seen"),
            "ads_active_count": self._to_int(ads_verification.get("active_ads_count")),
            "ads_creative_hints": list(ads_verification.get("creative_hints") or []),
            "paid_acquisition_active": ads_status == "yes",
            "reviews_count": maps_reviews_count if maps_reviews_count is not None else lead.get("reviews_count") or lead.get("review_count"),
            "rating": maps_rating if maps_rating is not None else lead.get("rating") or lead.get("review_rating"),
            "maps_verified": maps_verified,
            "volume_score_inputs": {
                "volume_score": intent.get("volume_score"),
                "peak_busyness": enrichment.get("peak_busyness"),
                "avg_busyness": enrichment.get("avg_busyness"),
                "busy_hours_count": enrichment.get("busy_hours_count"),
                "avg_visit_duration_min": enrichment.get("avg_visit_duration_min"),
            },
            "services": services,
            "social_profiles": social_profiles,
            "multi_clinic": bool(branch_count > 1),
            "branch_count": branch_count,
            "branch_names": branch_names,
            "maps_branch_names": maps_branch_names,
            "branch_contacts": branch_contacts,
            "doctor_count": doctor_count,
            "doctor_names": doctor_names,
            "doctor_profiles": doctor_profiles,
            "doctor_instagram_profiles": doctor_instagram_profiles,
            "doctor_followers_total": doctor_followers_total,
            "doctor_posts_total": doctor_posts_total,
            "doctor_max_followers": doctor_max_followers,
            "instagram_present": bool(proof_extraction.get("instagram_present") or social_profiles.get("instagram")),
            "instagram_profile": instagram_profile,
            "youtube_present": bool(proof_extraction.get("youtube_present") or social_profiles.get("youtube")),
            "youtube_channel": youtube_channel,
            "testimonials_present": bool(proof_extraction.get("testimonials_present")),
            "gallery_present": bool(proof_extraction.get("gallery_present")),
            "content_ready_score": int(proof_extraction.get("content_ready_score") or 0),
            "booking_flow_quality": booking_flow_quality,
            "after_hours_capture": bool(proof_extraction.get("after_hours_capture")),
            "instant_response_path": instant_response_path,
            "contact_intelligence": contact_intelligence,
            "contact_quality_score": contact_quality_score,
        }

    def _compute_score_breakdown(
        self,
        *,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        intent: Dict[str, Any],
        signal_facts: Dict[str, Any],
    ) -> Dict[str, int]:
        raw_reviews = signal_facts.get("reviews_count")
        raw_rating = signal_facts.get("rating")
        reviews = self._to_int(raw_reviews)
        rating = self._to_float(raw_rating)
        branch_count = self._to_int(signal_facts.get("branch_count"))
        doctor_count = self._to_int(signal_facts.get("doctor_count"))
        services = list(signal_facts.get("services") or [])
        social_profiles = signal_facts.get("social_profiles") or {}
        social_count = len([value for value in social_profiles.values() if value])
        ads_status = signal_facts.get("ads_status")
        ads_active_count = self._to_int(signal_facts.get("ads_active_count"))
        instagram_profile = signal_facts.get("instagram_profile") or {}
        youtube_channel = signal_facts.get("youtube_channel") or {}
        instagram_followers = self._to_int(instagram_profile.get("followers_count"))
        instagram_posts = self._to_int(instagram_profile.get("posts_count"))
        # Doctor IG counts as DEMAND/TRUST too (some clinics ride a doctor's
        # personal brand). Aggregate so scoring does not undervalue them.
        doctor_followers_total = self._to_int(signal_facts.get("doctor_followers_total"))
        doctor_posts_total = self._to_int(signal_facts.get("doctor_posts_total"))
        doctor_max_followers = self._to_int(signal_facts.get("doctor_max_followers"))
        combined_followers = instagram_followers + doctor_followers_total
        combined_posts = instagram_posts + doctor_posts_total
        youtube_subscribers = self._to_int(youtube_channel.get("subscriber_count"))
        youtube_recent_videos = self._to_int(youtube_channel.get("recent_video_count"))
        volume_score = self._to_int(intent.get("volume_score") or (signal_facts.get("volume_score_inputs") or {}).get("volume_score"))
        intent_score = self._to_int(intent.get("intent_score"))
        intent_leak_score = self._to_int(intent.get("leak_score"))
        reactivation_fit = self._to_int(intent.get("reactivation_fit"))
        content_ready_score = self._to_int(signal_facts.get("content_ready_score"))
        maps_verified = bool(signal_facts.get("maps_verified"))
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
            demand_score += min(ads_active_count * 2, 12)
        demand_score += min(int(volume_score / 10), 10)
        demand_score += min(int(intent_score / 20), 5)
        if maps_verified and raw_reviews is None and raw_rating is None:
            demand_score = max(demand_score, 18)
        if signal_facts.get("phone_visible") and signal_facts.get("booking_detected"):
            demand_score = max(demand_score, 20)

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
        # Combined social followers (clinic IG + doctor IG profiles) - doctors
        # with thousands of personal followers should count as trust signal
        # not just the clinic handle.
        if combined_followers >= 100000:
            trust_score += 12
        elif combined_followers >= 25000:
            trust_score += 8
        elif combined_followers >= 5000:
            trust_score += 5
        elif combined_followers >= 1000:
            trust_score += 2
        if combined_posts >= 30:
            trust_score += 4
        # Single-doctor superstar bonus: if any doctor has 25k+ personal
        # followers, that is independently strong demand evidence.
        if doctor_max_followers >= 25000:
            trust_score += 5
        if youtube_subscribers >= 10000:
            trust_score += 8
        elif youtube_subscribers >= 1000:
            trust_score += 4
        if youtube_recent_videos >= 5:
            trust_score += 4
        trust_score += min(int(content_ready_score / 12), 14)
        if contact_quality_score:
            trust_score += min(int(contact_quality_score / 12), 10)
        if top_contact:
            contact_type = str(top_contact.get("contact_type") or "").lower()
            confidence = self._to_int(top_contact.get("confidence"))
            if contact_type in {"founder_direct", "doctor_direct", "actual_contact"} and confidence >= 70:
                trust_score += 10
            elif confidence >= 60 and contact_type in {"decision_maker_candidate", "contact_candidate"}:
                trust_score += 4
            if confidence >= 65 and top_contact.get("phone"):
                trust_score += 2
            if confidence >= 65 and top_contact.get("email"):
                trust_score += 2
            if confidence >= 70 and top_contact.get("linkedin"):
                trust_score += 2
        verified_alternate_contacts = [
            contact
            for contact in alternate_contacts
            if self._to_int(contact.get("confidence")) >= 60
            and str(contact.get("contact_type") or "").lower() in {
                "founder_direct",
                "doctor_direct",
                "actual_contact",
                "decision_maker_candidate",
            }
        ]
        if verified_alternate_contacts:
            trust_score += min(len(verified_alternate_contacts), 2) * 2
        if branch_contacts:
            trust_score += min(len(branch_contacts), 2)
        if reviews >= 200 and rating >= 4.5:
            trust_score = max(trust_score, 30)
        has_verified_trust_markers = any(
            [
                raw_reviews is not None,
                raw_rating is not None,
                doctor_count > 0,
                branch_count > 0,
                instagram_followers > 0,
                doctor_followers_total > 0,
                youtube_subscribers > 0,
            ]
        )
        if not has_verified_trust_markers:
            if signal_facts.get("phone_visible") and signal_facts.get("booking_detected"):
                trust_score = max(trust_score, 16)
            if content_ready_score >= 60:
                trust_score = max(trust_score, 20)
            elif content_ready_score >= 40:
                trust_score = max(trust_score, 14)
            if maps_verified:
                trust_score = max(trust_score, 18)

        leak_score = 0
        if not signal_facts.get("phone_visible"):
            leak_score += 30
        if not signal_facts.get("whatsapp_detected"):
            leak_score += 14 if signal_facts.get("booking_detected") or signal_facts.get("contact_form_detected") else 22
        if booking_quality == "none":
            leak_score += 30
        elif booking_quality == "weak":
            leak_score += 22
        elif booking_quality == "basic":
            leak_score += 14
        if not signal_facts.get("contact_form_detected"):
            leak_score += 12
        if not signal_facts.get("after_hours_capture"):
            leak_score += 6 if signal_facts.get("booking_detected") or signal_facts.get("contact_form_detected") else 10
        if not signal_facts.get("instant_response_path"):
            leak_score += 8 if signal_facts.get("booking_detected") or signal_facts.get("contact_form_detected") else 12
        if (
            not signal_facts.get("whatsapp_detected")
            and booking_quality in {"basic", "weak", "none"}
            and self._to_int(signal_facts.get("reviews_count")) >= 20
        ):
            leak_score += 6
        if (
            not signal_facts.get("whatsapp_detected")
            and booking_quality in {"basic", "weak"}
            and not signal_facts.get("instant_response_path")
        ):
            leak_score += 12
        if (
            not signal_facts.get("whatsapp_detected")
            and not signal_facts.get("after_hours_capture")
            and (reviews >= 50 or branch_count > 1 or content_ready_score >= 60)
        ):
            leak_score += 8
        if ads_status == "yes" and not signal_facts.get("instant_response_path"):
            leak_score += 14
        if ads_status == "yes" and not signal_facts.get("whatsapp_detected"):
            leak_score += 10
        missing_capture_paths = sum(
            1
            for signal_present in [
                signal_facts.get("whatsapp_detected"),
                signal_facts.get("booking_detected"),
                signal_facts.get("contact_form_detected"),
            ]
            if not signal_present
        )
        if signal_facts.get("phone_visible") and missing_capture_paths >= 2:
            leak_score += 18
        if reviews >= 50 and missing_capture_paths >= 2:
            leak_score += 8
        if branch_count > 1 and missing_capture_paths >= 2:
            leak_score += 6

        capture_gap_floor = 0
        if not signal_facts.get("whatsapp_detected"):
            capture_gap_floor += 28
        if booking_quality == "none":
            capture_gap_floor += 32
        elif booking_quality == "weak":
            capture_gap_floor += 28
        elif booking_quality == "basic":
            capture_gap_floor += 18
        if not signal_facts.get("instant_response_path"):
            capture_gap_floor += 18
        if not signal_facts.get("after_hours_capture"):
            capture_gap_floor += 14
        if not signal_facts.get("contact_form_detected") and not signal_facts.get("booking_detected"):
            capture_gap_floor += 12
        if reviews >= 50 or branch_count > 1 or content_ready_score >= 60:
            capture_gap_floor += 8
        leak_score = max(leak_score, min(capture_gap_floor, 95), min(int(intent_leak_score * 0.9), 95))

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
        if ads_status == "yes":
            offer_fit_score += 14
            offer_fit_score += min(ads_active_count * 2, 10)
        if instagram_followers >= 5000 or youtube_subscribers >= 1000:
            offer_fit_score += 6
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

    # Minimum count of independently-verified commercial facts (out of:
    # reviews_count, rating, branch_count, doctor_count, verified social) below
    # which we refuse to emit a confident commercial judgment. Mirrors
    # _has_sparse_commercial_truth in src/api/server.py - keep both in sync.
    MIN_TRUTH_COVERAGE_FOR_JUDGMENT = 2

    def _truth_coverage(self, signal_facts: Optional[Dict[str, Any]]) -> int:
        """Count how many independently-verified commercial facts we have.

        Used to gate confident commercial judgment. A lead with reviews +
        rating + a doctor count is well above sparse; a lead with only a
        phone number visible is not enough to call A/B tier on."""
        facts = signal_facts or {}
        coverage = 0

        def _coerce_int(value: Any) -> Optional[int]:
            if value is None or value == "":
                return None
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        def _coerce_float(value: Any) -> Optional[float]:
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        if _coerce_int(facts.get("reviews_count")) is not None:
            coverage += 1
        if _coerce_float(facts.get("rating")) is not None:
            coverage += 1
        if _coerce_int(facts.get("branch_count")):
            coverage += 1
        if _coerce_int(facts.get("doctor_count")):
            coverage += 1
        instagram_profile = facts.get("instagram_profile") or {}
        youtube_channel = facts.get("youtube_channel") or {}
        doctor_followers_total = _coerce_int(facts.get("doctor_followers_total"))
        if (
            instagram_profile.get("followers_count") is not None
            or instagram_profile.get("posts_count") is not None
            or youtube_channel.get("subscriber_count") is not None
            or youtube_channel.get("total_videos") is not None
            or (doctor_followers_total is not None and doctor_followers_total > 0)
        ):
            coverage += 1
        return coverage

    def _gate_judgment_for_sparse_truth(
        self, scoring: Dict[str, Any], signal_facts: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Demote tier and label the lead 'needs verification' when commercial
        truth is too sparse to support a confident commercial judgment.

        Score itself is preserved for transparency/debugging, but tier is
        capped at C and a `judgment_state` flag is exposed so the inspector
        renders 'Needs verification' instead of an A/B confidence.
        """
        coverage = self._truth_coverage(signal_facts)
        scoring["truth_coverage"] = coverage
        if coverage < self.MIN_TRUTH_COVERAGE_FOR_JUDGMENT:
            scoring["judgment_state"] = "needs_verification"
            scoring["judgment_label"] = "Needs verification"
            # Cap tier at C - nothing should claim A/B confidence on <2 facts.
            scoring["original_lead_tier"] = scoring.get("lead_tier")
            scoring["lead_tier"] = "C"
            scoring["should_skip_outreach"] = True
            scoring["score_gating_reason"] = (
                f"only {coverage} verified commercial fact(s); minimum is "
                f"{self.MIN_TRUTH_COVERAGE_FOR_JUDGMENT}"
            )
        else:
            scoring["judgment_state"] = "ready"
            scoring["judgment_label"] = "Ready for outreach"
        return scoring

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

    def _clean_branch_names(self, values: List[Any]) -> List[str]:
        blocked_terms = {
            "about us",
            "contact us",
            "book appointment",
            "treatments",
            "treatment",
            "gallery",
            "offers",
            "offer",
            "popular treatments",
            "chemical peel",
            "photo facial",
            "prp",
            "microdermabrasion",
            "laser hair",
            "latest offers",
        }
        cleaned: List[str] = []
        for value in self._dedupe(values):
            text = str(value or "").strip()
            lowered = text.lower()
            if not text or "@" in lowered or lowered.startswith("http"):
                continue
            if any(term in lowered for term in blocked_terms):
                continue
            cleaned.append(text)
        return cleaned

    def _clean_branch_contacts(self, values: List[Any]) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        seen = set()
        for value in values:
            if not isinstance(value, dict):
                continue
            names = self._clean_branch_names([value.get("name")])
            name = names[0] if names else None
            phone = str(value.get("phone") or "").strip()
            if not name and not phone:
                continue
            key = ((name or "").lower(), phone)
            if key in seen:
                continue
            seen.add(key)
            normalized = dict(value)
            normalized["name"] = name
            normalized["phone"] = phone or None
            cleaned.append(normalized)
        return cleaned

    def _clean_doctor_names(self, values: List[Any]) -> List[str]:
        return [text for text in self._dedupe(values) if self._is_plausible_person_name(text)]

    def _clean_doctor_profiles(self, values: List[Any]) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        seen = set()
        for value in values:
            if not isinstance(value, dict):
                continue
            name = str(value.get("name") or "").strip()
            if not self._is_plausible_person_name(name):
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized = dict(value)
            normalized["name"] = name
            cleaned.append(normalized)
        return cleaned

    def _extract_business_tokens(self, *values: Any) -> List[str]:
        blocked = {
            "clinic",
            "clinics",
            "skin",
            "hair",
            "laser",
            "care",
            "center",
            "centre",
            "hospital",
            "dermatology",
            "aesthetic",
            "aesthetics",
            "cosmetic",
            "doctor",
            "doctors",
            "specialist",
            "specialists",
            "best",
            "top",
            "premium",
            "beauty",
            "weight",
            "loss",
            "bangalore",
            "bengaluru",
        }
        tokens: List[str] = []
        seen = set()
        for value in values:
            for token in re.findall(r"[a-z0-9]+", str(value or "").lower()):
                if len(token) < 3 or token in blocked or token in seen:
                    continue
                seen.add(token)
                tokens.append(token)
        return tokens

    def _maps_candidate_matches_business(
        self,
        candidate: Dict[str, Any],
        *,
        business_name: Optional[str],
        website: Optional[str],
    ) -> bool:
        haystack = " ".join(
            [
                str(candidate.get("title") or candidate.get("name") or ""),
                str(candidate.get("website") or ""),
                str(candidate.get("url") or ""),
                str(candidate.get("address") or ""),
            ]
        ).lower()
        if not haystack.strip():
            return False
        domain_hint = ""
        if website:
            domain_hint = re.sub(r"^www\.", "", re.sub(r"^https?://", "", str(website), flags=re.IGNORECASE)).split("/", 1)[0]
            domain_hint = domain_hint.split(".")[0].replace("-", " ").replace("_", " ")
        business_tokens = self._extract_business_tokens(business_name, domain_hint)
        if not business_tokens:
            return True
        matched = sum(1 for token in business_tokens if token in haystack)
        required = 1 if len(business_tokens) <= 2 else 2
        return matched >= required

    def _extract_maps_branch_names(
        self,
        raw_apify_data: Dict[str, Any],
        *,
        business_name: Optional[str],
        website: Optional[str],
    ) -> List[str]:
        if not isinstance(raw_apify_data, dict):
            return []
        names: List[str] = []
        seen = set()

        def add_name(value: Any) -> None:
            candidate_names = self._clean_branch_names([value])
            if not candidate_names:
                return
            key = candidate_names[0].lower()
            if key in seen:
                return
            seen.add(key)
            names.append(candidate_names[0])

        for place in list(raw_apify_data.get("relatedPlaces") or []):
            if not isinstance(place, dict):
                continue
            if not self._maps_candidate_matches_business(
                place,
                business_name=business_name,
                website=website,
            ):
                continue
            add_name(place.get("address"))

        if not names:
            candidate = {
                "title": raw_apify_data.get("maps_title"),
                "address": raw_apify_data.get("maps_address"),
                "website": raw_apify_data.get("maps_website") or website,
            }
            if self._maps_candidate_matches_business(
                candidate,
                business_name=business_name,
                website=website,
            ):
                add_name(raw_apify_data.get("maps_address"))

        return names[:4]

    def _is_strong_doctor_profile(self, profile: Dict[str, Any]) -> bool:
        if not isinstance(profile, dict):
            return False
        if profile.get("phones") or profile.get("emails") or profile.get("linkedin"):
            return True
        role = str(profile.get("role") or "").strip().lower()
        source = str(profile.get("source") or "").strip().lower()
        return any(
            token in role or token in source
            for token in ("founder", "director", "doctor", "dermatologist", "team", "roster")
        )

    def _is_plausible_person_name(self, value: Any) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        tokens = [token.lower() for token in re.findall(r"[A-Za-z]+", text)]
        if len(tokens) < 2:
            return False
        blocked_tokens = {
            "clinic",
            "skin",
            "hair",
            "laser",
            "care",
            "center",
            "centre",
            "hospital",
            "dermatology",
            "aesthetic",
            "aesthetics",
            "cosmetic",
            "consultant",
            "dermatologist",
            "doctor",
            "specialist",
            "surgeon",
            "physician",
            "admin",
            "receptionist",
        }
        return not any(token in blocked_tokens for token in tokens)

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
