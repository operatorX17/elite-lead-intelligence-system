"""
In-memory database fallback for local development.

This keeps the backend usable when Supabase is unreachable locally.
It implements the subset of the Supabase client interface the agents and API
currently rely on.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID


def _normalize_id(value: Any) -> str:
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class MemorySupabaseClient:
    """In-memory replacement for the Supabase client wrapper."""

    is_memory_backend = True

    def __init__(self):
        self._leads: Dict[str, Dict[str, Any]] = {}
        self._lead_states: Dict[str, Dict[str, Any]] = {}
        self._enrichment_data: Dict[str, Dict[str, Any]] = {}
        self._intent_data: Dict[str, Dict[str, Any]] = {}
        self._proof_artifacts: Dict[str, Dict[str, Any]] = {}
        self._scoring_results: Dict[str, Dict[str, Any]] = {}
        self._outreach_queue: Dict[str, Dict[str, Any]] = {}
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._negative_signals: List[Dict[str, Any]] = []
        self._do_not_contact: Dict[str, Dict[str, Any]] = {}
        self._audit_logs: List[Dict[str, Any]] = []
        self._usage_metrics: Dict[str, Dict[str, Any]] = {}
        self._playbooks: List[Dict[str, Any]] = []
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self._golden_dataset: List[Dict[str, Any]] = []
        self._ab_tests: Dict[str, Dict[str, Any]] = {}
        self._ab_metrics: List[Dict[str, Any]] = []
        self._daily_metrics: Dict[str, Dict[str, Any]] = {}
        self._escalations: List[Dict[str, Any]] = []

    def _copy(self, value: Any) -> Any:
        return deepcopy(value)

    def upload_artifact_bytes(
        self,
        path: str,
        data: bytes,
        content_type: str = "image/png",
        bucket_name: Optional[str] = None,
    ) -> str:
        """Return a deterministic in-memory artifact URL."""
        if not data:
            raise ValueError("Artifact upload requires non-empty bytes")
        bucket = bucket_name or "zrai-artifacts"
        return f"memory://{bucket}/{path}"

    def _get_lead_dict(self, lead_id: Any) -> Optional[Dict[str, Any]]:
        return self._leads.get(_normalize_id(lead_id))

    def _matches_lead_filters(
        self,
        lead: Dict[str, Any],
        niche: Optional[str] = None,
        geo: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        if status and lead.get("lead_lifecycle_state") != status.upper():
            return False

        if niche:
            niche_lower = niche.lower()
            haystacks = [
                str(lead.get("category") or "").lower(),
                str(lead.get("business_name") or "").lower(),
                " ".join(str(tag).lower() for tag in (lead.get("geo_tags") or [])),
            ]
            if not any(niche_lower in haystack for haystack in haystacks):
                return False

        if geo:
            geo_lower = geo.lower()
            location = str(lead.get("location") or "").lower()
            geo_tags = [str(tag).lower() for tag in (lead.get("geo_tags") or [])]
            if geo_lower not in location and geo_lower not in geo_tags:
                return False

        return True

    # ==================== LEADS ====================

    def create_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        lead = self._copy(lead_data)
        lead_id = _normalize_id(lead["lead_id"])
        self._leads[lead_id] = lead
        return self._copy(lead)

    def get_lead(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        lead = self._get_lead_dict(lead_id)
        return self._copy(lead) if lead else None

    def update_lead(self, lead_id: UUID, updates: Dict[str, Any]) -> Dict[str, Any]:
        key = _normalize_id(lead_id)
        lead = self._leads.get(key, {}).copy()
        lead.update(self._copy(updates))
        lead["updated_at"] = datetime.utcnow().isoformat()
        self._leads[key] = lead
        return self._copy(lead)

    def get_leads_by_state(self, state: str, limit: int = 100) -> List[Dict[str, Any]]:
        leads = [
            self._copy(lead)
            for lead in self._leads.values()
            if lead.get("lead_lifecycle_state") == state
        ]
        return leads[:limit]

    def check_lead_exists(
        self, business_name: str, location: str, website: Optional[str]
    ) -> bool:
        for lead in self._leads.values():
            if (
                lead.get("business_name") == business_name
                and (lead.get("location") or "") == location
                and (not website or lead.get("website") == website)
            ):
                return True
        return False

    # ==================== LEAD STATE ====================

    def save_lead_state(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(state_data)
        lead_id = _normalize_id(payload["lead_id"])
        payload["updated_at"] = datetime.utcnow().isoformat()
        self._lead_states[lead_id] = payload
        return self._copy(payload)

    def get_lead_state(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        state = self._lead_states.get(_normalize_id(lead_id))
        return self._copy(state) if state else None

    def get_failed_leads(
        self, since: datetime, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        results = []
        for state in self._lead_states.values():
            updated_at = _to_datetime(state.get("updated_at"))
            if state.get("last_error") and updated_at and updated_at >= since:
                results.append(self._copy(state))
        if limit is not None:
            return results[:limit]
        return results

    def get_leads_to_process(self, limit: int = 100) -> List[Dict[str, Any]]:
        results = []
        now = datetime.utcnow()
        for state in self._lead_states.values():
            next_run_at = _to_datetime(state.get("next_run_at"))
            if next_run_at is None or next_run_at <= now:
                results.append(self._copy(state))
        return results[:limit]

    # ==================== ENRICHMENT DATA ====================

    def save_enrichment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        lead_id = _normalize_id(payload["lead_id"])
        self._enrichment_data[lead_id] = payload
        return self._copy(payload)

    def get_enrichment_data(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        data = self._enrichment_data.get(_normalize_id(lead_id))
        return self._copy(data) if data else None

    # ==================== INTENT DATA ====================

    def save_intent_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        lead_id = _normalize_id(payload["lead_id"])
        self._intent_data[lead_id] = payload
        return self._copy(payload)

    def get_intent_data(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        data = self._intent_data.get(_normalize_id(lead_id))
        return self._copy(data) if data else None

    # ==================== PROOF ARTIFACTS ====================

    def save_proof_artifact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        lead_id = _normalize_id(payload["lead_id"])
        self._proof_artifacts[lead_id] = payload
        return self._copy(payload)

    def get_proof_artifact(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        data = self._proof_artifacts.get(_normalize_id(lead_id))
        return self._copy(data) if data else None

    # ==================== SCORING RESULTS ====================

    def save_scoring_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        lead_id = _normalize_id(payload["lead_id"])
        self._scoring_results[lead_id] = payload
        return self._copy(payload)

    def get_scoring_result(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        data = self._scoring_results.get(_normalize_id(lead_id))
        return self._copy(data) if data else None

    def get_leads_by_tier(self, tier: str, limit: int = 100) -> List[Dict[str, Any]]:
        matches = []
        for result in self._scoring_results.values():
            if (
                result.get("lead_tier") == tier
                and not result.get("do_not_contact", False)
            ):
                matches.append(self._copy(result))
        return matches[:limit]

    # ==================== OUTREACH QUEUE ====================

    def create_outreach(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        outreach_id = _normalize_id(
            payload.get("outreach_id") or payload.get("id") or datetime.utcnow().timestamp()
        )
        payload["outreach_id"] = outreach_id
        self._outreach_queue[outreach_id] = payload
        return self._copy(payload)

    def get_pending_outreach(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [
            self._copy(item)
            for item in self._outreach_queue.values()
            if item.get("status") == "pending"
        ][:limit]

    def update_outreach_status(
        self, outreach_id: UUID, status: str, sent_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        key = _normalize_id(outreach_id)
        item = self._outreach_queue.get(key, {}).copy()
        item["status"] = status
        if sent_at:
            item["sent_at"] = sent_at.isoformat()
        self._outreach_queue[key] = item
        return self._copy(item)

    # ==================== CONVERSATIONS ====================

    def create_conversation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        conversation_id = _normalize_id(payload["conversation_id"])
        self._conversations[conversation_id] = payload
        return self._copy(payload)

    def update_conversation(
        self, conversation_id: UUID, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        key = _normalize_id(conversation_id)
        conversation = self._conversations.get(key, {}).copy()
        conversation.update(self._copy(updates))
        conversation["updated_at"] = datetime.utcnow().isoformat()
        self._conversations[key] = conversation
        return self._copy(conversation)

    def get_conversation(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        data = self._conversations.get(_normalize_id(conversation_id))
        return self._copy(data) if data else None

    def get_conversations_for_lead(self, lead_id: UUID) -> List[Dict[str, Any]]:
        key = _normalize_id(lead_id)
        return [
            self._copy(conversation)
            for conversation in self._conversations.values()
            if _normalize_id(conversation.get("lead_id")) == key
        ]

    # ==================== NEGATIVE SIGNALS ====================

    def create_negative_signal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._negative_signals.append(payload)
        return self._copy(payload)

    def get_negative_signals(self, lead_id: UUID) -> List[Dict[str, Any]]:
        key = _normalize_id(lead_id)
        return [
            self._copy(signal)
            for signal in self._negative_signals
            if _normalize_id(signal.get("lead_id")) == key
        ]

    def count_negative_signals_by_domain(self, domain: str) -> int:
        domain = domain.lower()
        count = 0
        for signal in self._negative_signals:
            lead = self._get_lead_dict(signal.get("lead_id"))
            website = str(lead.get("website") or "").lower() if lead else ""
            if domain and domain in website:
                count += 1
        return count

    # ==================== DO NOT CONTACT ====================

    def add_to_dnc(
        self, lead_id: UUID, reason: str, expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        entry = {
            "lead_id": _normalize_id(lead_id),
            "reason": reason,
            "added_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
        self._do_not_contact[entry["lead_id"]] = entry
        return self._copy(entry)

    def is_on_dnc(self, lead_id: UUID) -> bool:
        entry = self._do_not_contact.get(_normalize_id(lead_id))
        if not entry:
            return False
        expires_at = _to_datetime(entry.get("expires_at"))
        return expires_at is None or expires_at > datetime.utcnow()

    # ==================== AUDIT LOG ====================

    def create_audit_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._audit_logs.append(payload)
        return self._copy(payload)

    def check_idempotency_key(self, key: str) -> bool:
        return any(log.get("idempotency_key") == key for log in self._audit_logs)

    def get_audit_logs(
        self,
        actor: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        logs = []
        for log in reversed(self._audit_logs):
            if actor and log.get("actor") != actor:
                continue
            if since:
                timestamp = _to_datetime(log.get("timestamp"))
                if not timestamp or timestamp < since:
                    continue
            logs.append(self._copy(log))
            if len(logs) >= limit:
                break
        return logs

    # ==================== USAGE METRICS ====================

    def get_or_create_usage_metrics(self, date: datetime) -> Dict[str, Any]:
        date_str = date.date().isoformat()
        if date_str not in self._usage_metrics:
            self._usage_metrics[date_str] = {
                "metric_date": date_str,
                "llm_tokens_used": 0,
                "browser_sessions_used": 0,
                "scraper_runs_used": 0,
                "llm_cost_usd": 0.0,
                "browser_cost_usd": 0.0,
                "scraper_cost_usd": 0.0,
                "updated_at": datetime.utcnow().isoformat(),
            }
        return self._copy(self._usage_metrics[date_str])

    def increment_usage(self, date: datetime, field: str, amount: int = 1) -> Dict[str, Any]:
        date_str = date.date().isoformat()
        metrics = self.get_or_create_usage_metrics(date)
        metrics[field] = metrics.get(field, 0) + amount
        metrics["updated_at"] = datetime.utcnow().isoformat()
        self._usage_metrics[date_str] = metrics
        return self._copy(metrics)

    # ==================== PLAYBOOKS ====================

    def create_playbook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._playbooks.append(payload)
        return self._copy(payload)

    def get_playbooks(
        self,
        niche: Optional[str] = None,
        tier: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for playbook in self._playbooks:
            if niche and playbook.get("niche") != niche:
                continue
            if tier and playbook.get("tier") != tier:
                continue
            if channel and playbook.get("channel") != channel:
                continue
            results.append(self._copy(playbook))
        return results

    # ==================== CIRCUIT BREAKERS ====================

    def get_circuit_breaker(self, node_name: str) -> Optional[Dict[str, Any]]:
        cb = self._circuit_breakers.get(node_name)
        return self._copy(cb) if cb else None

    def save_circuit_breaker(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._circuit_breakers[payload["node_name"]] = payload
        return self._copy(payload)

    # ==================== ADDITIONAL METHODS ====================

    def get_leads_for_processing(
        self, limit: Optional[int] = None, niche: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        leads = [
            self._copy(lead)
            for lead in self._leads.values()
            if lead.get("lead_lifecycle_state") in {"NEW", "REACTIVATABLE"}
            and self._matches_lead_filters(lead, niche=niche)
        ]
        return leads[:limit] if limit is not None else leads

    def get_leads_from_run(self, run_id: str) -> List[Dict[str, Any]]:
        lead_ids = []
        for log in self._audit_logs:
            if log.get("action") != "discovery_process":
                continue
            metadata = str(log.get("metadata") or "")
            if run_id in metadata and log.get("resource"):
                lead_ids.append(_normalize_id(log["resource"]))
        return [
            self._copy(self._leads[lead_id])
            for lead_id in lead_ids
            if lead_id in self._leads
        ]

    def get_historical_state(self, lead_id: UUID, run_id: str) -> Optional[Dict[str, Any]]:
        lead_key = _normalize_id(lead_id)
        for log in reversed(self._audit_logs):
            metadata = str(log.get("metadata") or "")
            if log.get("resource") == lead_key and run_id in metadata:
                return self._copy(log)
        return None

    def count_outreach_today(
        self, domain: Optional[str] = None, channel: Optional[str] = None
    ) -> int:
        today = datetime.utcnow().date()
        count = 0
        for outreach in self._outreach_queue.values():
            if outreach.get("status") != "sent":
                continue
            sent_at = _to_datetime(outreach.get("sent_at"))
            if not sent_at or sent_at.date() != today:
                continue
            if channel and outreach.get("channel") != channel:
                continue
            if domain:
                lead = self._get_lead_dict(outreach.get("lead_id"))
                website = str(lead.get("website") or "").lower() if lead else ""
                if domain.lower() not in website:
                    continue
            count += 1
        return count

    def count_outreach_sent(self, date: datetime) -> int:
        day = date.date()
        return sum(
            1
            for outreach in self._outreach_queue.values()
            if outreach.get("status") == "sent"
            and (_to_datetime(outreach.get("sent_at")) or datetime.min).date() == day
        )

    def count_replies(self, date: datetime) -> int:
        day = date.date()
        return sum(
            1
            for conversation in self._conversations.values()
            if (_to_datetime(conversation.get("created_at")) or datetime.min).date() == day
        )

    def count_meetings(self, date: datetime) -> int:
        day = date.date()
        return sum(
            1
            for conversation in self._conversations.values()
            if conversation.get("escalated")
            and (_to_datetime(conversation.get("escalated_at")) or datetime.min).date()
            == day
        )

    def count_qualified(self, date: datetime) -> int:
        day = date.date()
        return sum(
            1
            for lead in self._leads.values()
            if lead.get("lead_lifecycle_state") == "QUALIFIED"
            and (_to_datetime(lead.get("updated_at")) or datetime.min).date() == day
        )

    def count_negative_signals(self, date: datetime) -> int:
        day = date.date()
        return sum(
            1
            for signal in self._negative_signals
            if (_to_datetime(signal.get("created_at")) or datetime.min).date() == day
        )

    def count_human_overrides(self, date: datetime) -> int:
        day = date.date()
        return sum(
            1
            for log in self._audit_logs
            if log.get("action") == "human_override"
            and (_to_datetime(log.get("timestamp")) or datetime.min).date() == day
        )

    def get_usage_metrics(self, date: datetime) -> Dict[str, Any]:
        return self.get_or_create_usage_metrics(date)

    def store_daily_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(metrics)
        metric_date = str(payload.get("metric_date") or datetime.utcnow().date().isoformat())
        self._daily_metrics[metric_date] = payload
        return self._copy(payload)

    def get_lead_counts_by_state(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for lead in self._leads.values():
            state = str(lead.get("lead_lifecycle_state") or "UNKNOWN")
            counts[state] = counts.get(state, 0) + 1
        return counts

    def get_lead_counts_by_status(self) -> Dict[str, int]:
        return self.get_lead_counts_by_state()

    def get_leads(
        self,
        niche: Optional[str] = None,
        geo: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        leads = [
            self._copy(lead)
            for lead in self._leads.values()
            if self._matches_lead_filters(lead, niche=niche, geo=geo, status=status)
        ]

        if min_score is not None:
            filtered = []
            for lead in leads:
                scoring = self._scoring_results.get(_normalize_id(lead.get("lead_id")))
                if scoring and scoring.get("final_score", 0) >= min_score:
                    filtered.append(lead)
            leads = filtered

        return leads[offset : offset + limit]

    def count_leads(
        self,
        niche: Optional[str] = None,
        geo: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> int:
        return len(
            self.get_leads(
                niche=niche,
                geo=geo,
                status=status,
                min_score=min_score,
                limit=10_000,
                offset=0,
            )
        )

    def remove_email_from_lead(self, lead_id: UUID, email: str) -> None:
        key = _normalize_id(lead_id)
        lead = self._leads.get(key)
        if not lead:
            return
        lead["emails_found"] = [item for item in lead.get("emails_found", []) if item != email]
        lead["updated_at"] = datetime.utcnow().isoformat()

    def remove_from_dnc(self, lead_id: UUID) -> None:
        self._do_not_contact.pop(_normalize_id(lead_id), None)

    def create_escalation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._escalations.append(payload)
        return self._copy(payload)

    # ==================== GOLDEN DATASET ====================

    def get_golden_dataset(self) -> List[Dict[str, Any]]:
        return self._copy(self._golden_dataset)

    def add_golden_dataset_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._golden_dataset.append(payload)
        return self._copy(payload)

    # ==================== A/B TESTING ====================

    def create_ab_test(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._ab_tests[str(payload["name"])] = payload
        return self._copy(payload)

    def get_ab_test_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        test = self._ab_tests.get(name)
        return self._copy(test) if test else None

    def update_ab_test(self, name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        test = self._ab_tests.get(name, {}).copy()
        test.update(self._copy(updates))
        self._ab_tests[name] = test
        return self._copy(test)

    def get_active_ab_tests(self) -> List[Dict[str, Any]]:
        return [
            self._copy(test)
            for test in self._ab_tests.values()
            if test.get("status") == "running"
        ]

    def record_ab_metric(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._copy(data)
        self._ab_metrics.append(payload)
        return self._copy(payload)

    def get_ab_test_metrics(self, test_name: str) -> List[Dict[str, Any]]:
        return [
            self._copy(metric)
            for metric in self._ab_metrics
            if metric.get("test_name") == test_name
        ]
