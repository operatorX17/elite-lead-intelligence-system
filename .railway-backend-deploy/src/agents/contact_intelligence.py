"""Canonical contact intelligence helpers for ZRAI Lead OS."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


INVALID_PERSON_TOKENS = {
    "clinic",
    "clinics",
    "center",
    "centers",
    "hospital",
    "hospitals",
    "care",
    "health",
    "skin",
    "dental",
    "laser",
    "esthetic",
    "aesthetic",
    "cosmetic",
    "medspa",
    "spa",
    "group",
    "private",
    "limited",
    "pvt",
    "ltd",
    "llp",
    "llc",
    "brand",
    "owner",
    "hint",
    "consultant",
    "dermatologist",
    "specialist",
    "doctor",
    "physician",
    "surgeon",
    "receptionist",
    "admin",
    "manager",
}

FOUNDER_ROLES = {
    "founder",
    "co_founder",
    "co-founder",
    "director",
    "owner",
    "ceo",
    "managing_director",
    "managing director",
    "senior_doctor",
    "senior doctor",
}

TYPE_PRIORITY = {
    "founder_direct": 60,
    "doctor_direct": 50,
    "actual_contact": 45,
    "decision_maker_candidate": 40,
    "contact_candidate": 30,
    "social_profile": 20,
    "branch_public": 10,
}


def _normalize_person_candidate(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", str(value or ""))).strip()


def _is_plausible_person_name(value: Optional[str]) -> bool:
    cleaned = _normalize_person_candidate(value)
    if not cleaned or len(cleaned) < 4 or any(char.isdigit() for char in cleaned):
        return False

    tokens = [token.replace(".", "").strip() for token in cleaned.split() if token.strip()]
    if len(tokens) < 2:
        return False

    lowered = [token.lower() for token in tokens]
    if all(token in INVALID_PERSON_TOKENS for token in lowered):
        return False

    if any(token in INVALID_PERSON_TOKENS for token in lowered):
        non_generic_count = sum(1 for token in lowered if token not in INVALID_PERSON_TOKENS)
        if non_generic_count < 2:
            return False

    significant_tokens = [token for token in tokens if len(token) > 1]
    has_initial_token = any(len(token) == 1 for token in tokens)
    if len(significant_tokens) < 2 and not (len(significant_tokens) >= 1 and has_initial_token):
        return False

    return True


def _normalize_confidence(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None

    if confidence <= 1:
        confidence *= 100

    return max(0.0, min(confidence, 100.0))


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 7:
        return None
    core = digits[-10:]
    if len(set(core)) == 1:
        return None
    if core in {"0123456789", "1234567890", "0987654321", "9876543210"}:
        return None
    if core.endswith("123456789") or core.endswith("987654321"):
        return None
    return digits


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(value).strip().lower()


def _normalize_linkedin(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(value).strip().lower()


def _is_junk_email(value: Optional[str]) -> bool:
    if not value:
        return True
    lowered = value.strip().lower()
    if lowered.startswith("frame-"):
        return True
    if any(token in lowered for token in ("@mht", "@mhtml", ".mht", ".mhtml", "cid:", "content-id")):
        return True
    if lowered.endswith("@example.com") or lowered.endswith("@example.org"):
        return True
    local_part = lowered.split("@", 1)[0]
    if len(local_part) > 48 and any(char.isdigit() for char in local_part):
        return True
    return False


def _normalize_branch_candidate_name(value: Optional[str]) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -,:;")
    if not text or len(text) > 60:
        return None
    lowered = text.lower()
    blocked_terms = {
        "consultant",
        "dermatologist",
        "specialist",
        "doctor",
        "physician",
        "surgeon",
        "receptionist",
        "manager",
        "admin",
        "book",
        "appointment",
        "contact us",
        "about us",
        "treatments",
        "offers",
        "gallery",
        "email",
        "phone",
    }
    if "@" in lowered or lowered.startswith("http"):
        return None
    if any(token in lowered for token in blocked_terms):
        return None
    location_tokens = (
        "nagar",
        "layout",
        "road",
        "rd",
        "block",
        "phase",
        "cross",
        "main",
        "koramangala",
        "jayanagar",
        "indiranagar",
        "whitefield",
        "hsr",
        "jp",
        "bengaluru",
        "bangalore",
        "branch",
    )
    if not any(token in lowered for token in location_tokens):
        return None
    return text


def _contact_identity_key(contact: Dict[str, Any]) -> str:
    phone = _normalize_phone(contact.get("phone"))
    if phone:
        return f"phone:{phone}"
    linkedin = _normalize_linkedin(contact.get("linkedin"))
    if linkedin:
        return f"linkedin:{linkedin}"
    email = _normalize_email(contact.get("email"))
    if email and not _is_junk_email(email):
        return f"email:{email}"
    name = str(contact.get("name") or "").strip().lower()
    role = str(contact.get("role") or "").strip().lower()
    return f"name:{name}|role:{role}"


def _contact_type_for(role: Optional[str], *, is_branch: bool = False) -> str:
    if is_branch:
        return "branch_public"

    lowered = str(role or "").strip().lower().replace("-", "_")
    if any(token in lowered for token in ("founder", "co_founder", "owner", "director")):
        return "founder_direct"
    if "doctor" in lowered or lowered.startswith("dr"):
        return "doctor_direct"
    if lowered:
        return "decision_maker_candidate"
    return "contact_candidate"


def _fingerprint_contact(contact: Dict[str, Any]) -> str:
    return "|".join(
        [
            _contact_identity_key(contact),
            str(contact.get("contact_type") or "").strip().lower(),
            str(contact.get("owner_scope") or "").strip().lower(),
        ]
    )


def _contact_rank(contact: Dict[str, Any]) -> float:
    confidence = _normalize_confidence(contact.get("confidence")) or 0.0
    contact_type = str(contact.get("contact_type") or "").strip().lower()
    type_priority = float(TYPE_PRIORITY.get(contact_type, 0))
    direct_bonus = 6.0 if contact.get("is_direct") else 0.0
    channel_bonus = 3.0 if contact.get("channel") else 0.0
    evidence_bonus = 2.0 if any([contact.get("phone"), contact.get("email"), contact.get("linkedin")]) else 0.0
    return type_priority + confidence + direct_bonus + channel_bonus + evidence_bonus


def _build_contact_point(
    *,
    name: Optional[str],
    role: Optional[str],
    clinic: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    linkedin: Optional[str],
    source: Optional[str],
    confidence: Optional[Any],
    reason: Optional[str],
    channel: Optional[str],
    contact_type: Optional[str] = None,
    owner_scope: Optional[str] = None,
    is_primary: bool = False,
    is_direct: Optional[bool] = None,
    is_public: Optional[bool] = None,
) -> Optional[Dict[str, Any]]:
    normalized_name = _normalize_person_candidate(name)
    normalized_phone = _normalize_phone(phone)
    normalized_email = _normalize_email(email)
    normalized_linkedin = _normalize_linkedin(linkedin)
    if normalized_email and _is_junk_email(normalized_email):
        normalized_email = None
    if not normalized_name and not any([normalized_phone, normalized_email, normalized_linkedin]):
        return None

    effective_contact_type = contact_type or _contact_type_for(role)
    if is_primary and effective_contact_type == "contact_candidate":
        effective_contact_type = "decision_maker_candidate"

    owner_scope_value = owner_scope or ("branch" if effective_contact_type == "branch_public" else "person")
    if normalized_name and effective_contact_type != "branch_public" and not _is_plausible_person_name(normalized_name):
        normalized_name = None

    if effective_contact_type != "branch_public" and not normalized_name and not any([normalized_email, normalized_linkedin]):
        return None

    display_name = normalized_name
    if not display_name:
        display_name = clinic or ("Clinic branch" if owner_scope_value == "branch" else "Clinic contact")

    return {
        "name": display_name,
        "role": role or None,
        "clinic": clinic or None,
        "phone": normalized_phone,
        "email": normalized_email,
        "linkedin": normalized_linkedin,
        "source": source or None,
        "confidence": _normalize_confidence(confidence),
        "reason": reason or None,
        "channel": channel or None,
        "contact_type": effective_contact_type,
        "owner_scope": owner_scope_value,
        "is_primary": bool(is_primary),
        "is_direct": bool(is_direct) if is_direct is not None else effective_contact_type in {"founder_direct", "doctor_direct"},
        "is_public": bool(is_public) if is_public is not None else effective_contact_type == "branch_public",
    }


def _build_branch_point(contact: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    phone = str(contact.get("phone") or "").strip() or None
    raw_name = str(contact.get("name") or "").strip() or None
    name = _normalize_branch_candidate_name(raw_name)
    if raw_name and not name:
        return None
    if not phone and not name:
        return None

    return _build_contact_point(
        name=name or "Clinic branch",
        role="branch contact",
        clinic=None,
        phone=phone,
        email=None,
        linkedin=None,
        source=str(contact.get("source") or "branch phone"),
        confidence=60,
        reason=str(contact.get("source") or "branch public contact"),
        channel="phone",
        contact_type="branch_public",
        owner_scope="branch",
        is_primary=False,
        is_direct=False,
        is_public=True,
    )


def _build_candidate_point(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = str(candidate.get("name") or "").strip() or None
    role = str(candidate.get("role") or "").strip() or None
    phones = list(candidate.get("phones") or [])
    emails = list(candidate.get("emails") or [])
    linkedin = str(candidate.get("linkedin") or "").strip() or None
    confidence = candidate.get("score")
    source = str(candidate.get("source") or "decision-maker candidate")
    has_direct_path = bool(phones or emails or linkedin)
    if not name and not any([phones, emails, linkedin]):
        return None
    if not has_direct_path:
        return None

    contact_type = _contact_type_for(role)
    is_direct = contact_type in {"founder_direct", "doctor_direct"}
    return _build_contact_point(
        name=name,
        role=role,
        clinic=str(candidate.get("clinic") or "").strip() or None,
        phone=phones[0] if phones else None,
        email=emails[0] if emails else None,
        linkedin=linkedin,
        source=source,
        confidence=confidence,
        reason=source,
        channel="linkedin" if linkedin else ("email" if emails else ("phone" if phones else None)),
        contact_type=contact_type,
        owner_scope="person",
        is_primary=False,
        is_direct=is_direct,
        is_public=False,
    )


def _build_doctor_point(doctor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = str(doctor.get("name") or "").strip() or None
    role = str(doctor.get("role") or "doctor").strip() or "doctor"
    phones = list(doctor.get("phones") or [])
    emails = list(doctor.get("emails") or [])
    linkedin = str(doctor.get("linkedin") or "").strip() or None
    source = str(doctor.get("source") or "doctor profile")
    has_direct_path = bool(phones or emails or linkedin)
    if not name and not any([phones, emails, linkedin]):
        return None
    if not has_direct_path:
        return None

    contact_type = _contact_type_for(role)
    is_direct = contact_type == "doctor_direct"
    return _build_contact_point(
        name=name or "Doctor",
        role=role,
        clinic=str(doctor.get("clinic") or "").strip() or None,
        phone=phones[0] if phones else None,
        email=emails[0] if emails else None,
        linkedin=linkedin,
        source=source,
        confidence=doctor.get("score") or 55,
        reason=source,
        channel="linkedin" if linkedin else ("email" if emails else ("phone" if phones else None)),
        contact_type=contact_type,
        owner_scope="person",
        is_primary=False,
        is_direct=is_direct,
        is_public=False,
    )


def build_contact_intelligence(signal_facts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a canonical contact model from signal facts."""

    signal_facts = dict(signal_facts or {})
    decision_maker_name = _normalize_person_candidate(signal_facts.get("decision_maker_name"))
    if not _is_plausible_person_name(decision_maker_name):
        decision_maker_name = None

    decision_maker_role = str(signal_facts.get("decision_maker_role") or "").strip() or None
    decision_maker_source = str(signal_facts.get("decision_maker_source") or "").strip() or None
    decision_maker_confidence = _normalize_confidence(signal_facts.get("decision_maker_confidence"))
    best_contact_phone = str(signal_facts.get("best_contact_phone") or "").strip() or None
    best_contact_email = str(signal_facts.get("best_contact_email") or "").strip() or None
    best_contact_linkedin = str(signal_facts.get("best_contact_linkedin") or "").strip() or None
    best_contact_channel = str(signal_facts.get("best_contact_channel") or "").strip() or None
    best_contact_reason = str(signal_facts.get("best_contact_reason") or "").strip() or None
    contact_quality_score = _normalize_confidence(signal_facts.get("contact_quality_score"))

    decision_maker_candidates = list(signal_facts.get("decision_maker_candidates") or [])
    branch_contacts = list(signal_facts.get("branch_contacts") or [])
    doctor_profiles = list(signal_facts.get("doctor_profiles") or [])
    contact_evidence = _dedupe_strings(signal_facts.get("contact_evidence") or [])
    top_contact_has_direct_path = bool(best_contact_phone or best_contact_email or best_contact_linkedin)
    top_contact_has_person_path = bool(best_contact_linkedin) or bool(
        decision_maker_name and top_contact_has_direct_path and (decision_maker_confidence or 0) >= 80
    )

    contact_points: List[Dict[str, Any]] = []
    top_contact = _build_contact_point(
        name=decision_maker_name if top_contact_has_person_path else None,
        role=(decision_maker_role or best_contact_channel or None) if top_contact_has_person_path else "clinic contact",
        clinic=str(signal_facts.get("business_name") or "").strip() or None,
        phone=best_contact_phone,
        email=best_contact_email,
        linkedin=best_contact_linkedin,
        source=decision_maker_source or best_contact_reason or "best contact",
        confidence=decision_maker_confidence or contact_quality_score,
        reason=best_contact_reason or decision_maker_source or "best contact",
        channel=best_contact_channel or ("linkedin" if best_contact_linkedin else ("email" if best_contact_email else ("phone" if best_contact_phone else None))),
        contact_type=_contact_type_for(decision_maker_role) if top_contact_has_person_path else "actual_contact",
        owner_scope="person" if top_contact_has_person_path else "clinic",
        is_primary=True,
        is_direct=top_contact_has_person_path and _contact_type_for(decision_maker_role) in {"founder_direct", "doctor_direct"},
        is_public=False,
    )
    if top_contact:
        contact_points.append(top_contact)

    for candidate in decision_maker_candidates:
        point = _build_candidate_point(candidate)
        if point:
            contact_points.append(point)

    for doctor in doctor_profiles:
        point = _build_doctor_point(doctor)
        if point:
            contact_points.append(point)

    for branch_contact in branch_contacts:
        point = _build_branch_point(branch_contact)
        if point:
            contact_points.append(point)

    deduped_points: List[Dict[str, Any]] = []
    seen = set()
    for point in contact_points:
        fingerprint = _fingerprint_contact(point)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        deduped_points.append(point)

    deduped_points.sort(key=_contact_rank, reverse=True)
    top_contact = deduped_points[0] if deduped_points else None
    alternate_contacts = deduped_points[1:]

    if top_contact:
        decision_maker_name = decision_maker_name or str(top_contact.get("name") or "").strip() or None
        decision_maker_role = decision_maker_role or str(top_contact.get("role") or "").strip() or None
        decision_maker_source = decision_maker_source or str(top_contact.get("source") or "").strip() or None
        decision_maker_confidence = decision_maker_confidence or top_contact.get("confidence")
        best_contact_phone = best_contact_phone or str(top_contact.get("phone") or "").strip() or None
        best_contact_email = best_contact_email or str(top_contact.get("email") or "").strip() or None
        best_contact_linkedin = best_contact_linkedin or str(top_contact.get("linkedin") or "").strip() or None
        best_contact_channel = best_contact_channel or str(top_contact.get("channel") or "").strip() or None
        best_contact_reason = best_contact_reason or str(top_contact.get("reason") or "").strip() or None

    return {
        "top_contact": top_contact,
        "alternate_contacts": alternate_contacts,
        "contact_points": deduped_points,
        "contact_evidence": contact_evidence,
        "best_contact_reason": best_contact_reason,
        "decision_maker_name": decision_maker_name,
        "decision_maker_role": decision_maker_role,
        "decision_maker_source": decision_maker_source,
        "decision_maker_confidence": decision_maker_confidence,
        "decision_maker_linkedin": signal_facts.get("decision_maker_linkedin") or best_contact_linkedin,
        "best_contact_phone": best_contact_phone,
        "best_contact_email": best_contact_email,
        "best_contact_linkedin": best_contact_linkedin,
        "best_contact_channel": best_contact_channel,
        "contact_quality_score": contact_quality_score,
    }
