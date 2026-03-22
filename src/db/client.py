"""
Supabase client wrapper for database operations.
Requirements: 18.1, 18.2, 18.3

Note: Uses HTTP/1.1 instead of HTTP/2 to avoid Windows socket errors (WinError 10035)
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID
import json
import logging
import os
import socket
from urllib.parse import urlparse
import httpx

from supabase import create_client, Client

from src.config import load_config
from src.db.memory_client import MemorySupabaseClient


logger = logging.getLogger(__name__)


def _create_http1_client(timeout: float = 30.0) -> httpx.Client:
    """Create an httpx client forced to use HTTP/1.1 instead of HTTP/2.
    
    This fixes Windows socket errors (WinError 10035) that occur with HTTP/2.
    """
    transport = httpx.HTTPTransport(http2=False)
    return httpx.Client(transport=transport, timeout=timeout)


class SupabaseClient:
    """
    Supabase client wrapper providing typed database operations.
    
    Uses HTTP/1.1 to avoid Windows HTTP/2 socket errors.
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        if url is None or key is None:
            config = load_config()
            url = url or config.database.supabase_url
            key = key or config.database.supabase_service_role_key
        
        self._client: Client = create_client(url, key)
        
        # Force HTTP/1.1 to avoid Windows socket errors (WinError 10035)
        self._patch_http_client()
    
    def _patch_http_client(self) -> None:
        """Patch the internal httpx client to use HTTP/1.1 instead of HTTP/2.
        
        This fixes Windows socket errors that occur with HTTP/2 connections.
        The supabase-py library uses httpx internally which defaults to HTTP/2.
        """
        try:
            # Create HTTP/1.1 transport
            http1_transport = httpx.HTTPTransport(http2=False)
            
            # Patch PostgREST client (main database operations)
            if hasattr(self._client, 'postgrest'):
                postgrest = self._client.postgrest
                if hasattr(postgrest, 'session') and isinstance(postgrest.session, httpx.Client):
                    # Replace the transport on the existing httpx.Client
                    postgrest.session._transport = http1_transport
                    # Also update the mounts dict which contains the default transport
                    if hasattr(postgrest.session, '_mounts'):
                        for key in postgrest.session._mounts:
                            if isinstance(postgrest.session._mounts[key], httpx.HTTPTransport):
                                postgrest.session._mounts[key] = http1_transport
            
            # Patch storage client if present
            if hasattr(self._client, 'storage'):
                storage = self._client.storage
                if hasattr(storage, '_client') and hasattr(storage._client, 'session'):
                    if isinstance(storage._client.session, httpx.Client):
                        storage._client.session._transport = http1_transport
            
            # Patch functions client if present
            if hasattr(self._client, 'functions'):
                functions = self._client.functions
                if hasattr(functions, '_client') and isinstance(functions._client, httpx.Client):
                    functions._client._transport = http1_transport
                    
        except Exception as e:
            # If patching fails, continue with default HTTP/2
            # The error will be logged but won't prevent client creation
            import logging
            logging.getLogger(__name__).warning(
                f"Could not patch httpx client to HTTP/1.1: {e}. "
                "Continuing with default HTTP/2 (may cause socket errors on Windows)."
            )
    
    @property
    def client(self) -> Client:
        """Get the underlying Supabase client."""
        return self._client

    def upload_artifact_bytes(
        self,
        path: str,
        data: bytes,
        content_type: str = "image/png",
        bucket_name: Optional[str] = None,
    ) -> str:
        """Upload artifact bytes to Supabase Storage and return a public URL."""
        if not data:
            raise ValueError("Artifact upload requires non-empty bytes")

        config = load_config()
        bucket = bucket_name or config.s3.bucket_name

        existing_buckets = self._client.storage.list_buckets()
        if not any(getattr(item, "id", None) == bucket for item in existing_buckets):
            self._client.storage.create_bucket(
                bucket,
                options={"public": True},
            )

        bucket_client = self._client.storage.from_(bucket)
        bucket_client.upload(
            path,
            data,
            {"content-type": content_type, "upsert": "true"},
        )
        return bucket_client.get_public_url(path)
    
    # ==================== LEADS ====================
    
    def create_lead(self, lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new lead record."""
        result = self._client.table("leads").insert(lead_data).execute()
        return result.data[0] if result.data else {}
    
    def get_lead(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a lead by ID."""
        result = self._client.table("leads").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else None
    
    def update_lead(self, lead_id: UUID, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a lead record."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("leads").update(updates).eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else {}
    
    def get_leads_by_state(self, state: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leads by lifecycle state."""
        result = self._client.table("leads").select("*").eq("lead_lifecycle_state", state).limit(limit).execute()
        return result.data or []
    
    def check_lead_exists(self, business_name: str, location: str, website: Optional[str]) -> bool:
        """Check if a lead already exists (deduplication)."""
        query = self._client.table("leads").select("lead_id").eq("business_name", business_name).eq("location", location)
        if website:
            query = query.eq("website", website)
        result = query.execute()
        return len(result.data) > 0
    
    # ==================== LEAD STATE ====================
    
    def save_lead_state(self, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update lead state (checkpointer)."""
        state_data["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("lead_state").upsert(state_data).execute()
        return result.data[0] if result.data else {}
    
    def get_lead_state(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get lead state by lead ID."""
        result = self._client.table("lead_state").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else None
    
    def get_failed_leads(self, since: datetime) -> List[Dict[str, Any]]:
        """Get failed lead states since timestamp."""
        result = self._client.table("lead_state").select("*").not_.is_("last_error", "null").gte("updated_at", since.isoformat()).execute()
        return result.data or []
    
    def get_leads_to_process(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leads ready for processing."""
        now = datetime.utcnow().isoformat()
        result = self._client.table("lead_state").select("*").or_(f"next_run_at.is.null,next_run_at.lte.{now}").limit(limit).execute()
        return result.data or []
    
    # ==================== ENRICHMENT DATA ====================
    
    def save_enrichment_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save enrichment data."""
        result = self._client.table("enrichment_data").upsert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_enrichment_data(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get enrichment data for a lead."""
        result = self._client.table("enrichment_data").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else None
    
    # ==================== INTENT DATA ====================
    
    def save_intent_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save intent data."""
        result = self._client.table("intent_data").upsert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_intent_data(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get intent data for a lead."""
        result = self._client.table("intent_data").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else None
    
    # ==================== PROOF ARTIFACTS ====================
    
    def save_proof_artifact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save proof artifact."""
        result = self._client.table("proof_artifacts").upsert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_proof_artifact(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get proof artifact for a lead."""
        result = self._client.table("proof_artifacts").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else None
    
    # ==================== SCORING RESULTS ====================
    
    def save_scoring_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save scoring result."""
        result = self._client.table("scoring_results").upsert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_scoring_result(self, lead_id: UUID) -> Optional[Dict[str, Any]]:
        """Get scoring result for a lead."""
        result = self._client.table("scoring_results").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data[0] if result.data else None
    
    def get_leads_by_tier(self, tier: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get leads by tier."""
        result = self._client.table("scoring_results").select("*").eq("lead_tier", tier).eq("do_not_contact", False).limit(limit).execute()
        return result.data or []
    
    # ==================== OUTREACH QUEUE ====================
    
    def create_outreach(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create outreach queue entry."""
        result = self._client.table("outreach_queue").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_pending_outreach(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending outreach messages."""
        result = self._client.table("outreach_queue").select("*").eq("status", "pending").limit(limit).execute()
        return result.data or []

    def get_outreach_for_lead(self, lead_id: UUID, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent outreach entries for a lead."""
        result = (
            self._client.table("outreach_queue")
            .select("*")
            .eq("lead_id", str(lead_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    
    def update_outreach_status(self, outreach_id: UUID, status: str, sent_at: Optional[datetime] = None) -> Dict[str, Any]:
        """Update outreach status."""
        updates = {"status": status}
        if sent_at:
            updates["sent_at"] = sent_at.isoformat()
        result = self._client.table("outreach_queue").update(updates).eq("outreach_id", str(outreach_id)).execute()
        return result.data[0] if result.data else {}
    
    # ==================== CONVERSATIONS ====================
    
    def create_conversation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create conversation record."""
        result = self._client.table("conversations").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def update_conversation(self, conversation_id: UUID, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update conversation record."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self._client.table("conversations").update(updates).eq("conversation_id", str(conversation_id)).execute()
        return result.data[0] if result.data else {}
    
    def get_conversation(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        """Get conversation by ID."""
        result = self._client.table("conversations").select("*").eq("conversation_id", str(conversation_id)).execute()
        return result.data[0] if result.data else None
    
    def get_conversations_for_lead(self, lead_id: UUID) -> List[Dict[str, Any]]:
        """Get all conversations for a lead."""
        result = self._client.table("conversations").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data or []
    
    # ==================== NEGATIVE SIGNALS ====================
    
    def create_negative_signal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create negative signal record."""
        result = self._client.table("negative_signals").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_negative_signals(self, lead_id: UUID) -> List[Dict[str, Any]]:
        """Get negative signals for a lead."""
        result = self._client.table("negative_signals").select("*").eq("lead_id", str(lead_id)).execute()
        return result.data or []
    
    def count_negative_signals_by_domain(self, domain: str) -> int:
        """Count negative signals for a domain."""
        result = self._client.table("negative_signals").select("signal_id", count="exact").like("lead_id", f"%{domain}%").execute()
        return result.count or 0
    
    # ==================== DO NOT CONTACT ====================
    
    def add_to_dnc(self, lead_id: UUID, reason: str, expires_at: Optional[datetime] = None) -> Dict[str, Any]:
        """Add lead to do not contact list."""
        data = {
            "lead_id": str(lead_id),
            "reason": reason,
            "added_at": datetime.utcnow().isoformat(),
        }
        if expires_at:
            data["expires_at"] = expires_at.isoformat()
        result = self._client.table("do_not_contact").upsert(data).execute()
        return result.data[0] if result.data else {}
    
    def is_on_dnc(self, lead_id: UUID) -> bool:
        """Check if lead is on do not contact list."""
        now = datetime.utcnow().isoformat()
        result = self._client.table("do_not_contact").select("lead_id").eq("lead_id", str(lead_id)).or_(f"expires_at.is.null,expires_at.gt.{now}").execute()
        return len(result.data) > 0
    
    # ==================== AUDIT LOG ====================
    
    def create_audit_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create audit log entry (append-only)."""
        result = self._client.table("audit_log").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def check_idempotency_key(self, key: str) -> bool:
        """Check if idempotency key exists."""
        result = self._client.table("audit_log").select("log_id").eq("idempotency_key", key).execute()
        return len(result.data) > 0
    
    def get_audit_logs(self, actor: Optional[str] = None, since: Optional[datetime] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit logs with optional filters."""
        query = self._client.table("audit_log").select("*")
        if actor:
            query = query.eq("actor", actor)
        if since:
            query = query.gte("timestamp", since.isoformat())
        result = query.order("timestamp", desc=True).limit(limit).execute()
        return result.data or []
    
    # ==================== USAGE METRICS ====================
    
    def get_or_create_usage_metrics(self, date: datetime) -> Dict[str, Any]:
        """Get or create usage metrics for a date."""
        date_str = date.date().isoformat()
        result = self._client.table("usage_metrics").select("*").eq("metric_date", date_str).execute()
        if result.data:
            return result.data[0]
        
        # Create new record
        data = {
            "metric_date": date_str,
            "llm_tokens_used": 0,
            "browser_sessions_used": 0,
            "scraper_runs_used": 0,
            "llm_cost_usd": 0.0,
            "browser_cost_usd": 0.0,
            "scraper_cost_usd": 0.0,
        }
        result = self._client.table("usage_metrics").insert(data).execute()
        return result.data[0] if result.data else data
    
    def increment_usage(self, date: datetime, field: str, amount: int = 1) -> Dict[str, Any]:
        """Increment a usage metric."""
        metrics = self.get_or_create_usage_metrics(date)
        date_str = date.date().isoformat()
        new_value = metrics.get(field, 0) + amount
        result = self._client.table("usage_metrics").update({field: new_value, "updated_at": datetime.utcnow().isoformat()}).eq("metric_date", date_str).execute()
        return result.data[0] if result.data else {}
    
    # ==================== PLAYBOOKS ====================
    
    def create_playbook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create playbook entry."""
        result = self._client.table("playbooks").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_playbooks(self, niche: Optional[str] = None, tier: Optional[str] = None, channel: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get playbooks with optional filters."""
        query = self._client.table("playbooks").select("*")
        if niche:
            query = query.eq("niche", niche)
        if tier:
            query = query.eq("tier", tier)
        if channel:
            query = query.eq("channel", channel)
        result = query.execute()
        return result.data or []
    
    # ==================== CIRCUIT BREAKERS ====================
    
    def get_circuit_breaker(self, node_name: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker state."""
        result = self._client.table("circuit_breakers").select("*").eq("node_name", node_name).execute()
        return result.data[0] if result.data else None
    
    def save_circuit_breaker(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save circuit breaker state."""
        result = self._client.table("circuit_breakers").upsert(data).execute()
        return result.data[0] if result.data else {}
    
    # ==================== ADDITIONAL METHODS ====================
    
    def get_leads_for_processing(self, limit: Optional[int] = None, niche: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get leads ready for processing."""
        query = self._client.table("leads").select("*").in_("lead_lifecycle_state", ["NEW", "REACTIVATABLE"])
        if niche:
            query = query.contains("geo_tags", [niche])
        if limit:
            query = query.limit(limit)
        result = query.execute()
        return result.data or []
    
    def get_leads_from_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Get leads from a specific run."""
        result = self._client.table("audit_log").select("resource").eq("action", "discovery_process").like("metadata", f"%{run_id}%").execute()
        lead_ids = [r["resource"] for r in result.data if r.get("resource")]
        if not lead_ids:
            return []
        result = self._client.table("leads").select("*").in_("lead_id", lead_ids).execute()
        return result.data or []
    
    def get_failed_leads(self, since: datetime, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get failed lead states since timestamp."""
        query = self._client.table("lead_state").select("*").not_.is_("last_error", "null").gte("updated_at", since.isoformat())
        if limit:
            query = query.limit(limit)
        result = query.execute()
        return result.data or []
    
    def get_historical_state(self, lead_id: UUID, run_id: str) -> Optional[Dict[str, Any]]:
        """Get historical state for replay."""
        result = self._client.table("audit_log").select("*").eq("resource", str(lead_id)).like("metadata", f"%{run_id}%").order("timestamp", desc=True).limit(1).execute()
        return result.data[0] if result.data else None
    
    def count_outreach_today(self, domain: Optional[str] = None, channel: Optional[str] = None) -> int:
        """Count outreach sent today."""
        today = datetime.utcnow().date().isoformat()
        query = self._client.table("outreach_queue").select("outreach_id", count="exact").eq("status", "sent").gte("sent_at", today)
        if channel:
            query = query.eq("channel", channel)
        result = query.execute()
        return result.count or 0
    
    def count_outreach_sent(self, date: datetime) -> int:
        """Count outreach sent on a specific date."""
        date_str = date.date().isoformat()
        next_day = (date.date().replace(day=date.day + 1)).isoformat()
        result = self._client.table("outreach_queue").select("outreach_id", count="exact").eq("status", "sent").gte("sent_at", date_str).lt("sent_at", next_day).execute()
        return result.count or 0
    
    def count_replies(self, date: datetime) -> int:
        """Count replies received on a specific date."""
        date_str = date.date().isoformat()
        result = self._client.table("conversations").select("conversation_id", count="exact").gte("created_at", date_str).execute()
        return result.count or 0
    
    def count_meetings(self, date: datetime) -> int:
        """Count meetings booked on a specific date."""
        date_str = date.date().isoformat()
        result = self._client.table("conversations").select("conversation_id", count="exact").eq("escalated", True).gte("escalated_at", date_str).execute()
        return result.count or 0
    
    def count_qualified(self, date: datetime) -> int:
        """Count qualified leads on a specific date."""
        date_str = date.date().isoformat()
        result = self._client.table("leads").select("lead_id", count="exact").eq("lead_lifecycle_state", "QUALIFIED").gte("updated_at", date_str).execute()
        return result.count or 0
    
    def count_negative_signals(self, date: datetime) -> int:
        """Count negative signals on a specific date."""
        date_str = date.date().isoformat()
        result = self._client.table("negative_signals").select("signal_id", count="exact").gte("created_at", date_str).execute()
        return result.count or 0
    
    def count_human_overrides(self, date: datetime) -> int:
        """Count human overrides on a specific date."""
        date_str = date.date().isoformat()
        result = self._client.table("audit_log").select("log_id", count="exact").eq("action", "human_override").gte("timestamp", date_str).execute()
        return result.count or 0
    
    def get_usage_metrics(self, date: datetime) -> Dict[str, Any]:
        """Get usage metrics for a date."""
        return self.get_or_create_usage_metrics(date)
    
    def store_daily_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Store daily metrics."""
        result = self._client.table("daily_metrics").upsert(metrics).execute()
        return result.data[0] if result.data else {}
    
    def get_lead_counts_by_state(self) -> Dict[str, int]:
        """Get lead counts grouped by lifecycle state."""
        states = ["NEW", "STALE", "REACTIVATABLE", "ENGAGED", "QUALIFIED", "CLOSED_WON", "CLOSED_LOST"]
        counts = {}
        for state in states:
            result = self._client.table("leads").select("lead_id", count="exact").eq("lead_lifecycle_state", state).execute()
            counts[state] = result.count or 0
        return counts
    
    def get_lead_counts_by_status(self) -> Dict[str, int]:
        """Alias for get_lead_counts_by_state."""
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
        """Get leads with optional filters."""
        query = self._client.table("leads").select("*")
        
        if status:
            query = query.eq("lead_lifecycle_state", status.upper())
        if niche:
            query = query.contains("geo_tags", [niche])
        if geo:
            query = query.ilike("location", f"%{geo}%")
        
        # Apply pagination
        query = query.range(offset, offset + limit - 1)
        
        result = query.execute()
        leads = result.data or []
        
        # Filter by min_score if needed (requires join with scoring_results)
        if min_score is not None:
            filtered = []
            for lead in leads:
                scoring = self.get_scoring_result(lead.get("lead_id"))
                if scoring and scoring.get("total_score", 0) >= min_score:
                    filtered.append(lead)
            return filtered
        
        return leads
    
    def count_leads(
        self,
        niche: Optional[str] = None,
        geo: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
    ) -> int:
        """Count leads with optional filters."""
        query = self._client.table("leads").select("lead_id", count="exact")
        
        if status:
            query = query.eq("lead_lifecycle_state", status.upper())
        if niche:
            query = query.contains("geo_tags", [niche])
        if geo:
            query = query.ilike("location", f"%{geo}%")
        
        result = query.execute()
        return result.count or 0
    
    def remove_email_from_lead(self, lead_id: UUID, email: str) -> None:
        """Remove an email from a lead's emails_found list."""
        lead = self.get_lead(lead_id)
        if lead and lead.get("emails_found"):
            emails = [e for e in lead["emails_found"] if e != email]
            self.update_lead(lead_id, {"emails_found": emails})
    
    def remove_from_dnc(self, lead_id: UUID) -> None:
        """Remove lead from DNC list."""
        self._client.table("do_not_contact").delete().eq("lead_id", str(lead_id)).execute()
    
    def create_escalation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create escalation record."""
        result = self._client.table("escalations").insert(data).execute()
        return result.data[0] if result.data else {}
    
    # ==================== GOLDEN DATASET ====================
    
    def get_golden_dataset(self) -> List[Dict[str, Any]]:
        """Get golden dataset entries."""
        result = self._client.table("golden_dataset").select("*").execute()
        return result.data or []
    
    def add_golden_dataset_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add entry to golden dataset."""
        result = self._client.table("golden_dataset").insert(data).execute()
        return result.data[0] if result.data else {}
    
    # ==================== A/B TESTING ====================
    
    def create_ab_test(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create A/B test."""
        result = self._client.table("ab_tests").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_ab_test_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get A/B test by name."""
        result = self._client.table("ab_tests").select("*").eq("name", name).execute()
        return result.data[0] if result.data else None
    
    def update_ab_test(self, name: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update A/B test."""
        result = self._client.table("ab_tests").update(updates).eq("name", name).execute()
        return result.data[0] if result.data else {}
    
    def get_active_ab_tests(self) -> List[Dict[str, Any]]:
        """Get active A/B tests."""
        result = self._client.table("ab_tests").select("*").eq("status", "running").execute()
        return result.data or []
    
    def record_ab_metric(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Record A/B test metric."""
        result = self._client.table("ab_metrics").insert(data).execute()
        return result.data[0] if result.data else {}
    
    def get_ab_test_metrics(self, test_name: str) -> List[Dict[str, Any]]:
        """Get metrics for an A/B test."""
        result = self._client.table("ab_metrics").select("*").eq("test_name", test_name).execute()
        return result.data or []


# Global client instance
DatabaseClient = Union[SupabaseClient, MemorySupabaseClient]
_supabase_client: Optional[DatabaseClient] = None


def _should_use_memory_fallback(url: str) -> bool:
    """Decide whether to use the in-memory fallback backend."""
    if os.getenv("ZRAI_IN_MEMORY_BACKEND_DB", "").lower() == "true":
        return True

    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False

    if host in {"your-project.supabase.co", "localhost"}:
        return False

    try:
        socket.getaddrinfo(host, parsed.port or 443)
        return False
    except socket.gaierror:
        logger.warning(
            "Supabase host %s could not be resolved. Falling back to in-memory backend storage.",
            host,
        )
        return True


def _create_database_client() -> DatabaseClient:
    config = load_config()
    if _should_use_memory_fallback(config.database.supabase_url):
        return MemorySupabaseClient()
    return SupabaseClient(
        url=config.database.supabase_url,
        key=config.database.supabase_service_role_key,
    )


def get_supabase_client() -> DatabaseClient:
    """Get the global Supabase client instance."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = _create_database_client()
    return _supabase_client
