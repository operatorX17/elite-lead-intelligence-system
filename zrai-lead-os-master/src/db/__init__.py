"""Database module for ZRAI Lead OS."""

from .client import get_supabase_client, SupabaseClient
from .models import (
    Lead,
    LeadState,
    EnrichmentData,
    IntentData,
    ProofArtifact,
    ScoringResult,
    OutreachQueue,
    Conversation,
    NegativeSignal,
    DoNotContact,
    AuditLog,
    UsageMetrics,
    Playbook,
    CircuitBreaker,
)

__all__ = [
    "get_supabase_client",
    "SupabaseClient",
    "Lead",
    "LeadState",
    "EnrichmentData",
    "IntentData",
    "ProofArtifact",
    "ScoringResult",
    "OutreachQueue",
    "Conversation",
    "NegativeSignal",
    "DoNotContact",
    "AuditLog",
    "UsageMetrics",
    "Playbook",
    "CircuitBreaker",
]
