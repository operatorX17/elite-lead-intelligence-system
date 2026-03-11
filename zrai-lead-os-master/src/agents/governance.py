"""
Governance Agent for ZRAI Lead OS.
Requirements: 11 (RBAC), 12 (Rate Limiting), 13 (Audit Logging)
"""

from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from uuid import UUID, uuid4
import logging
import hashlib

from src.graph.state import LeadGraphState
from src.db.client import get_supabase_client
from src.db.models import (
    AuditLog,
    NegativeSignal,
    NegativeSignalType,
    DoNotContact,
)
from src.config import load_config


logger = logging.getLogger(__name__)


class RBACManager:
    """
    Role-Based Access Control manager.
    Requirements: 11.1, 11.2, 11.3
    """
    
    # Permission matrix per design.md
    PERMISSIONS: Dict[str, Set[str]] = {
        "discovery_agent": {
            "read_config",
            "write_leads",
            "call_apify",
        },
        "enrichment_agent": {
            "read_leads",
            "write_enrichment",
            "call_external_apis",
        },
        "intent_agent": {
            "read_leads",
            "read_enrichment",
            "write_intent",
        },
        "audit_agent": {
            "read_leads",
            "write_proof_artifacts",
            "call_steel",
            "write_s3",
        },
        "scoring_agent": {
            "read_leads",
            "read_enrichment",
            "read_intent",
            "write_scoring",
        },
        "outreach_agent": {
            "read_leads",
            "read_proof_artifacts",
            "write_outreach_queue",
            "call_llm",
        },
        "conversation_agent": {
            "read_outreach_queue",
            "write_conversations",
            "call_llm",
            "send_messages",
        },
        "governance_agent": {
            "read_all",
            "write_audit_log",
            "enforce_rate_limits",
            "manage_kill_switches",
        },
        "eval_agent": {
            "read_all",
            "write_metrics",
            "run_replay",
        },
    }
    
    def __init__(self):
        self._db = get_supabase_client()
        self._logger = logging.getLogger("zrai.governance.rbac")
    
    def has_permission(self, agent: str, action: str) -> bool:
        """
        Check if agent has permission for action.
        Requirements: 11.1
        """
        agent_permissions = self.PERMISSIONS.get(agent, set())
        
        # Check for wildcard permission
        if "read_all" in agent_permissions and action.startswith("read_"):
            return True
        
        return action in agent_permissions
    
    def verify_and_log(
        self,
        agent: str,
        action: str,
        resource: Optional[str] = None,
    ) -> bool:
        """
        Verify permission and log the attempt.
        Requirements: 11.1, 11.3
        """
        has_perm = self.has_permission(agent, action)
        
        if not has_perm:
            self._logger.warning(
                f"Permission denied: {agent} attempted {action} on {resource}"
            )
            # Log violation
            self._db.create_audit_log({
                "log_id": str(uuid4()),
                "actor": agent,
                "action": action,
                "resource": resource,
                "timestamp": datetime.utcnow().isoformat(),
                "result": "failure",
                "error_message": "Permission denied",
            })
        
        return has_perm


class RateLimiter:
    """
    Rate limiting manager.
    Requirements: 12.1, 12.2, 12.3
    """
    
    def __init__(self):
        self._db = get_supabase_client()
        self._config = load_config()
        self._logger = logging.getLogger("zrai.governance.rate_limiter")
    
    def check_rate_limit(
        self,
        domain: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> bool:
        """
        Check if rate limit allows operation.
        Requirements: 12.1
        """
        limits = self._config.rate_limits
        today = datetime.utcnow().date()
        
        # Check per-domain limit
        if domain:
            domain_count = self._db.count_outreach_today(domain=domain)
            if channel == "email":
                if domain_count >= limits.per_domain_email_per_day:
                    self._logger.warning(f"Domain rate limit reached: {domain}")
                    return False
            elif channel == "dm":
                if domain_count >= limits.per_domain_dm_per_day:
                    self._logger.warning(f"Domain DM rate limit reached: {domain}")
                    return False
        
        # Check per-channel limit
        if channel:
            channel_count = self._db.count_outreach_today(channel=channel)
            if channel == "email":
                if channel_count >= limits.email_per_day:
                    self._logger.warning("Email daily limit reached")
                    return False
            elif channel == "dm":
                if channel_count >= limits.dm_per_day:
                    self._logger.warning("DM daily limit reached")
                    return False
        
        return True
    
    def check_cool_down(self, lead_id: UUID) -> Optional[str]:
        """
        Check if lead is in cool-down period.
        Requirements: 12.2
        """
        signals = self._db.get_negative_signals(lead_id)
        
        if not signals:
            return None
        
        cool_downs = self._config.rate_limits.cool_downs
        now = datetime.utcnow()
        
        for signal in signals:
            signal_time = datetime.fromisoformat(signal["created_at"])
            signal_type = signal["signal_type"]
            
            cool_down_days = {
                "bounce": cool_downs.after_bounce_days,
                "spam_complaint": cool_downs.after_spam_complaint_days,
                "angry_reply": cool_downs.after_angry_reply_days,
                "opt_out": 36500,  # Effectively permanent
            }.get(signal_type, 7)
            
            if (now - signal_time).days < cool_down_days:
                return f"Cool-down active: {signal_type} on {signal_time.date()}"
        
        return None


class NegativeSignalDetector:
    """
    Detect and record negative signals.
    Requirements: 22.1, 22.3, 22.4, 22.7, 22.8
    """
    
    OPT_OUT_KEYWORDS = [
        "stop", "unsubscribe", "remove me", "opt out", "opt-out",
        "don't contact", "do not contact", "leave me alone",
        "take me off", "remove from list",
    ]
    
    ANGRY_KEYWORDS = [
        "spam", "scam", "reported", "lawsuit", "lawyer",
        "harassment", "stop emailing", "never contact",
        "how did you get", "where did you get",
    ]
    
    def __init__(self):
        self._db = get_supabase_client()
        self._logger = logging.getLogger("zrai.governance.negative_signals")
    
    def detect_opt_out(self, message: str) -> bool:
        """
        Detect opt-out intent in message.
        Requirements: 22.1
        """
        message_lower = message.lower()
        return any(kw in message_lower for kw in self.OPT_OUT_KEYWORDS)
    
    def detect_angry_reply(self, message: str) -> bool:
        """
        Detect angry/negative reply.
        Requirements: 22.3
        """
        message_lower = message.lower()
        return any(kw in message_lower for kw in self.ANGRY_KEYWORDS)
    
    def analyze_sentiment(self, message: str) -> float:
        """
        Simple sentiment analysis (-1 to 1).
        Returns negative score for negative sentiment.
        """
        # Simple keyword-based sentiment
        negative_words = [
            "angry", "upset", "annoyed", "frustrated", "spam",
            "scam", "terrible", "awful", "worst", "hate",
        ]
        positive_words = [
            "thanks", "interested", "great", "good", "helpful",
            "appreciate", "yes", "sure", "sounds good",
        ]
        
        message_lower = message.lower()
        neg_count = sum(1 for w in negative_words if w in message_lower)
        pos_count = sum(1 for w in positive_words if w in message_lower)
        
        total = neg_count + pos_count
        if total == 0:
            return 0.0
        
        return (pos_count - neg_count) / total
    
    def record_signal(
        self,
        lead_id: UUID,
        signal_type: NegativeSignalType,
        channel: Optional[str] = None,
        message_content: Optional[str] = None,
    ) -> NegativeSignal:
        """
        Record a negative signal.
        Requirements: 22.4
        """
        sentiment = None
        if message_content:
            sentiment = self.analyze_sentiment(message_content)
        
        signal = NegativeSignal(
            signal_id=uuid4(),
            lead_id=lead_id,
            signal_type=signal_type,
            channel=channel,
            sentiment_score=sentiment,
            message_content=message_content,
        )
        
        self._db.create_negative_signal(signal.model_dump())
        self._logger.info(f"Recorded {signal_type} signal for lead {lead_id}")
        
        return signal
    
    def process_reply(
        self,
        lead_id: UUID,
        message: str,
        channel: str,
    ) -> Optional[NegativeSignalType]:
        """
        Process a reply and detect/record any negative signals.
        Requirements: 22.1, 22.3
        """
        if self.detect_opt_out(message):
            self.record_signal(
                lead_id=lead_id,
                signal_type=NegativeSignalType.OPT_OUT,
                channel=channel,
                message_content=message,
            )
            # Add to DNC list
            self._db.add_to_dnc(lead_id, "OPT_OUT")
            return NegativeSignalType.OPT_OUT
        
        if self.detect_angry_reply(message):
            self.record_signal(
                lead_id=lead_id,
                signal_type=NegativeSignalType.ANGRY_REPLY,
                channel=channel,
                message_content=message,
            )
            return NegativeSignalType.ANGRY_REPLY
        
        return None
    
    def record_bounce(
        self,
        lead_id: UUID,
        bounce_type: str,  # 'hard' or 'soft'
        email: str,
    ) -> None:
        """
        Record email bounce.
        Requirements: 22.7
        """
        self.record_signal(
            lead_id=lead_id,
            signal_type=NegativeSignalType.BOUNCE,
            channel="email",
            message_content=f"{bounce_type} bounce: {email}",
        )
        
        if bounce_type == "hard":
            # Remove email from lead
            self._db.remove_email_from_lead(lead_id, email)
    
    def record_spam_complaint(
        self,
        lead_id: UUID,
        channel: str,
    ) -> None:
        """
        Record spam complaint.
        Requirements: 22.8
        """
        self.record_signal(
            lead_id=lead_id,
            signal_type=NegativeSignalType.SPAM_COMPLAINT,
            channel=channel,
        )
        # Immediately add to DNC
        self._db.add_to_dnc(lead_id, "SPAM_COMPLAINT")


class AuditLogger:
    """
    Append-only audit logging.
    Requirements: 13.1, 13.2, 13.4
    """
    
    # Patterns to redact from logs
    SECRET_PATTERNS = [
        "api_key", "apikey", "api-key",
        "secret", "password", "token",
        "authorization", "auth",
    ]
    
    def __init__(self):
        self._db = get_supabase_client()
        self._logger = logging.getLogger("zrai.governance.audit")
    
    def _redact_secrets(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact secret values from data.
        Requirements: 13.4
        """
        redacted = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in self.SECRET_PATTERNS):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_secrets(value)
            elif isinstance(value, str) and len(value) > 20:
                # Check if value looks like a secret
                if any(pattern in value.lower() for pattern in self.SECRET_PATTERNS):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = value
            else:
                redacted[key] = value
        return redacted
    
    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        """Generate hash of payload for integrity."""
        return hashlib.sha256(str(payload).encode()).hexdigest()
    
    def log(
        self,
        actor: str,
        action: str,
        resource: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        result: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """
        Create audit log entry.
        Requirements: 13.1
        """
        payload_hash = None
        if payload:
            # Redact secrets before hashing
            redacted = self._redact_secrets(payload)
            payload_hash = self._hash_payload(redacted)
        
        entry = AuditLog(
            log_id=uuid4(),
            actor=actor,
            action=action,
            resource=resource,
            timestamp=datetime.utcnow(),
            payload_hash=payload_hash,
            idempotency_key=idempotency_key,
            result=result,
            error_message=error_message,
        )
        
        self._db.create_audit_log(entry.model_dump())
        return entry


class DNCManager:
    """
    Do Not Contact list manager.
    Requirements: 22.2, 22.9
    """
    
    def __init__(self):
        self._db = get_supabase_client()
        self._logger = logging.getLogger("zrai.governance.dnc")
    
    def is_on_dnc(self, lead_id: UUID) -> bool:
        """
        Check if lead is on DNC list.
        Requirements: 22.9
        """
        return self._db.is_on_dnc(lead_id)
    
    def add_to_dnc(
        self,
        lead_id: UUID,
        reason: str,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """
        Add lead to DNC list.
        Requirements: 22.2
        """
        self._db.add_to_dnc(lead_id, reason, expires_at)
        self._logger.info(f"Added lead {lead_id} to DNC: {reason}")
    
    def remove_from_dnc(self, lead_id: UUID) -> None:
        """Remove lead from DNC list (for expired entries)."""
        self._db.remove_from_dnc(lead_id)


class GovernanceAgent:
    """
    Main Governance Agent combining all governance functions.
    Requirements: 11, 12, 13
    """
    
    def __init__(self):
        self.rbac = RBACManager()
        self.rate_limiter = RateLimiter()
        self.signal_detector = NegativeSignalDetector()
        self.audit_logger = AuditLogger()
        self.dnc_manager = DNCManager()
        self._logger = logging.getLogger("zrai.agents.governance")
    
    def can_contact(self, lead_id: UUID, channel: str, domain: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        Check if lead can be contacted.
        Returns (can_contact, reason_if_not)
        """
        # Check DNC list
        if self.dnc_manager.is_on_dnc(lead_id):
            return False, "Lead is on Do Not Contact list"
        
        # Check cool-down
        cool_down_reason = self.rate_limiter.check_cool_down(lead_id)
        if cool_down_reason:
            return False, cool_down_reason
        
        # Check rate limits
        if not self.rate_limiter.check_rate_limit(domain=domain, channel=channel):
            return False, "Rate limit exceeded"
        
        return True, None
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """
        Process governance checks for a lead.
        This is called as a node in the graph.
        """
        lead_id = state.get("lead_id")
        self._logger.info(f"Governance check for lead {lead_id}")
        
        # Check if lead should be skipped
        if lead_id and self.dnc_manager.is_on_dnc(lead_id):
            state["should_skip_outreach"] = True
            metadata = state.get("metadata", {})
            metadata["skip_reason"] = "DNC"
            state["metadata"] = metadata
        
        # Check cool-down
        if lead_id:
            cool_down = self.rate_limiter.check_cool_down(lead_id)
            if cool_down:
                state["should_skip_outreach"] = True
                metadata = state.get("metadata", {})
                metadata["skip_reason"] = cool_down
                state["metadata"] = metadata
        
        return state


def governance_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for governance."""
    agent = GovernanceAgent()
    return agent.process(state)
