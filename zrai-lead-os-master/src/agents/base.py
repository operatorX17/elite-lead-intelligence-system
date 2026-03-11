"""
Base agent class and utilities for ZRAI Lead OS.
Requirements: 4 (Modularity & Nodes)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypeVar, Generic
from datetime import datetime
import logging
import hashlib
from uuid import uuid4

from src.graph.state import LeadGraphState
from src.db.client import get_supabase_client
from src.config import load_config


logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseAgent(ABC, Generic[T]):
    """
    Base class for all ZRAI agents.
    
    Requirements:
    - 4: Each agent is its own node
    - Nodes take well-typed state object
    - Return updated state (pure function style)
    - Not reach across into other nodes' internals
    """
    
    def __init__(self, name: str):
        self.name = name
        self._db = get_supabase_client()
        self._config = load_config()
        self._logger = logging.getLogger(f"zrai.agents.{name}")
    
    @abstractmethod
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """
        Process the lead state and return updated state.
        
        This is the main entry point for the agent.
        Must be implemented by subclasses.
        """
        pass
    
    def __call__(self, state: LeadGraphState) -> LeadGraphState:
        """Make the agent callable for LangGraph."""
        self._logger.info(f"Processing lead {state.get('lead_id', 'unknown')}")
        
        try:
            # Update state tracking
            state["last_node"] = self.name
            
            # Process
            result = self.process(state)
            
            # Log success
            self._log_audit(
                action=f"{self.name}_process",
                resource=str(state.get("lead_id", "unknown")),
                result="success",
            )
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error in {self.name}: {e}")
            state["last_error"] = str(e)
            state["retry_count"] = state.get("retry_count", 0) + 1
            
            # Log failure
            self._log_audit(
                action=f"{self.name}_process",
                resource=str(state.get("lead_id", "unknown")),
                result="failure",
                error_message=str(e),
            )
            
            raise
    
    def _log_audit(
        self,
        action: str,
        resource: Optional[str] = None,
        result: str = "success",
        error_message: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """
        Log an audit entry.
        Requirements: 13.1
        """
        payload_hash = None
        if payload:
            payload_hash = hashlib.sha256(str(payload).encode()).hexdigest()
        
        self._db.create_audit_log({
            "log_id": str(uuid4()),
            "actor": self.name,
            "action": action,
            "resource": resource,
            "timestamp": datetime.utcnow().isoformat(),
            "payload_hash": payload_hash,
            "idempotency_key": idempotency_key,
            "result": result,
            "error_message": error_message,
        })
    
    def _check_idempotency(self, key: str) -> bool:
        """
        Check if an operation has already been performed.
        Requirements: 1.5
        """
        return self._db.check_idempotency_key(key)
    
    def _generate_idempotency_key(self, *args) -> str:
        """Generate an idempotency key from arguments."""
        data = ":".join(str(arg) for arg in args)
        return hashlib.sha256(data.encode()).hexdigest()
    
    def _check_kill_switch(self) -> bool:
        """
        Check if kill switch is active.
        Requirements: 1.6
        """
        if self._config.kill_switches.global_kill:
            return True
        
        # Check module-specific kill switches
        kill_switch_map = {
            "discovery": self._config.kill_switches.discovery_kill,
            "audit": self._config.kill_switches.audit_kill,
            "outreach": self._config.kill_switches.outreach_kill,
        }
        
        return kill_switch_map.get(self.name, False)
    
    def _check_budget(self, resource_type: str) -> bool:
        """
        Check if budget allows operation.
        Requirements: 23.2-23.7
        """
        today = datetime.utcnow()
        metrics = self._db.get_or_create_usage_metrics(today)
        
        limits = {
            "llm": (metrics.get("llm_tokens_used", 0), self._config.budget.daily_llm_token_limit),
            "browser": (metrics.get("browser_sessions_used", 0), self._config.budget.daily_browser_session_limit),
            "scraper": (metrics.get("scraper_runs_used", 0), self._config.budget.daily_scraper_run_limit),
        }
        
        if resource_type in limits:
            current, limit = limits[resource_type]
            return current < limit
        
        return True
    
    def _increment_usage(self, resource_type: str, amount: int = 1) -> None:
        """
        Increment usage counter.
        Requirements: 23.2-23.7
        """
        field_map = {
            "llm": "llm_tokens_used",
            "browser": "browser_sessions_used",
            "scraper": "scraper_runs_used",
        }
        
        if resource_type in field_map:
            self._db.increment_usage(datetime.utcnow(), field_map[resource_type], amount)


class CircuitBreakerMixin:
    """
    Mixin for circuit breaker functionality.
    Requirements: 1.4, 20.2
    """
    
    def _get_circuit_breaker(self, node_name: str) -> Dict[str, Any]:
        """Get circuit breaker state."""
        db = get_supabase_client()
        cb = db.get_circuit_breaker(node_name)
        if not cb:
            cb = {
                "node_name": node_name,
                "failure_count": 0,
                "failure_threshold": 5,
                "timeout_seconds": 300,
                "state": "CLOSED",
                "last_failure_at": None,
                "last_success_at": None,
            }
            db.save_circuit_breaker(cb)
        return cb
    
    def _is_circuit_open(self, node_name: str) -> bool:
        """Check if circuit breaker is open."""
        cb = self._get_circuit_breaker(node_name)
        
        if cb["state"] == "CLOSED":
            return False
        
        if cb["state"] == "OPEN":
            # Check if timeout has passed
            if cb["last_failure_at"]:
                last_failure = datetime.fromisoformat(cb["last_failure_at"])
                elapsed = (datetime.utcnow() - last_failure).total_seconds()
                if elapsed > cb["timeout_seconds"]:
                    # Move to half-open
                    self._update_circuit_breaker(node_name, state="HALF_OPEN")
                    return False
            return True
        
        # HALF_OPEN - allow one request through
        return False
    
    def _record_success(self, node_name: str) -> None:
        """Record successful operation."""
        db = get_supabase_client()
        cb = self._get_circuit_breaker(node_name)
        
        cb["failure_count"] = 0
        cb["state"] = "CLOSED"
        cb["last_success_at"] = datetime.utcnow().isoformat()
        
        db.save_circuit_breaker(cb)
    
    def _record_failure(self, node_name: str) -> None:
        """Record failed operation."""
        db = get_supabase_client()
        cb = self._get_circuit_breaker(node_name)
        
        cb["failure_count"] += 1
        cb["last_failure_at"] = datetime.utcnow().isoformat()
        
        if cb["failure_count"] >= cb["failure_threshold"]:
            cb["state"] = "OPEN"
        
        db.save_circuit_breaker(cb)
    
    def _update_circuit_breaker(self, node_name: str, **kwargs) -> None:
        """Update circuit breaker state."""
        db = get_supabase_client()
        cb = self._get_circuit_breaker(node_name)
        cb.update(kwargs)
        db.save_circuit_breaker(cb)


class RetryMixin:
    """
    Mixin for retry functionality with exponential backoff.
    Requirements: 1.3, 20.1
    """
    
    def _calculate_backoff(self, retry_count: int, base_delay: float = 1.0, max_delay: float = 300.0) -> float:
        """
        Calculate exponential backoff delay.
        Requirements: 1.3
        """
        delay = base_delay * (2 ** retry_count)
        return min(delay, max_delay)
    
    def _should_retry(self, retry_count: int, max_retries: int = 5) -> bool:
        """Check if should retry based on count."""
        return retry_count < max_retries
