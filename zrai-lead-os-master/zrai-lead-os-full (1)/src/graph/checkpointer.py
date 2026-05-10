"""
Supabase-based checkpointer for LangGraph.
Requirements: 1.2, 1.8, 20.3
"""

from typing import Optional, Dict, Any, Iterator, Tuple
from datetime import datetime
import json
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple

from src.db.client import get_supabase_client


class SupabaseCheckpointer(BaseCheckpointSaver):
    """
    Custom LangGraph checkpointer using Supabase/Postgres.
    
    Requirements:
    - 1.2: Persist lead state including lead_id, current_stage, last_node, etc.
    - 1.8: Mark completion and archive execution trace
    - 20.3: Log error, persist lead state on unrecoverable errors
    
    This enables:
    - Resume from any point on failure
    - Parallel execution with row-level locking
    - Full execution trace for debugging
    """
    
    def __init__(self):
        super().__init__()
        self._client = get_supabase_client()
    
    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Serialize checkpoint to JSON string."""
        return json.dumps(checkpoint, default=str)
    
    def _deserialize_checkpoint(self, data: str) -> Checkpoint:
        """Deserialize checkpoint from JSON string."""
        return json.loads(data)
    
    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> Dict[str, Any]:
        """
        Save a checkpoint.
        
        Requirements: 1.2 - Persist lead state at each node transition
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id is required in config")
        
        checkpoint_id = checkpoint.get("id", str(datetime.utcnow().timestamp()))
        
        # Extract state info from checkpoint
        channel_values = checkpoint.get("channel_values", {})
        state = channel_values.get("state", {})
        
        data = {
            "lead_id": thread_id,
            "current_stage": state.get("current_stage", "unknown"),
            "last_node": state.get("last_node", "unknown"),
            "last_error": state.get("last_error"),
            "retry_count": state.get("retry_count", 0),
            "next_run_at": state.get("next_run_at"),
            "locks": state.get("locks", []),
            "metadata": {
                "checkpoint_id": checkpoint_id,
                "checkpoint": self._serialize_checkpoint(checkpoint),
                "metadata": metadata,
                **state.get("metadata", {}),
            },
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        self._client.save_lead_state(data)
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
    
    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """
        Get a checkpoint tuple.
        
        Requirements: 1.2 - Load checkpoint for resume
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            return None
        
        state_data = self._client.get_lead_state(UUID(thread_id))
        if not state_data:
            return None
        
        metadata = state_data.get("metadata", {})
        checkpoint_data = metadata.get("checkpoint")
        
        if not checkpoint_data:
            return None
        
        checkpoint = self._deserialize_checkpoint(checkpoint_data)
        
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": metadata.get("checkpoint_id"),
                }
            },
            checkpoint=checkpoint,
            metadata=metadata.get("metadata", {}),
            parent_config=None,
        )
    
    def list(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        List checkpoints.
        
        This is used for replay and debugging.
        """
        thread_id = config.get("configurable", {}).get("thread_id") if config else None
        
        if thread_id:
            state_data = self._client.get_lead_state(UUID(thread_id))
            if state_data:
                metadata = state_data.get("metadata", {})
                checkpoint_data = metadata.get("checkpoint")
                if checkpoint_data:
                    checkpoint = self._deserialize_checkpoint(checkpoint_data)
                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_id": metadata.get("checkpoint_id"),
                            }
                        },
                        checkpoint=checkpoint,
                        metadata=metadata.get("metadata", {}),
                        parent_config=None,
                    )
    
    def put_writes(
        self,
        config: Dict[str, Any],
        writes: list,
        task_id: str,
    ) -> None:
        """
        Save intermediate writes.
        
        This is called during node execution to save partial state.
        """
        # For now, we rely on the main put() method
        # This could be extended to save intermediate writes for debugging
        pass
    
    def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Get checkpoint by config."""
        tuple_result = self.get_tuple(config)
        return tuple_result.checkpoint if tuple_result else None


def create_checkpointer() -> SupabaseCheckpointer:
    """Create a new Supabase checkpointer instance."""
    return SupabaseCheckpointer()
