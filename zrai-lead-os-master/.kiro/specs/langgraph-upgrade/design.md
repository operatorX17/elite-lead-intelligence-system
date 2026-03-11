# Design Document: LangGraph Professional Upgrade

## Overview

This design document outlines the professional-grade upgrade of the ZRAI Lead OS LangGraph orchestrator. The upgrade implements the latest 2025 LangGraph patterns including TypedDict state management, Command-based routing, Send primitives for parallel processing, proper checkpointing, human-in-the-loop interrupts, streaming support, and retry policies.

**Research Sources (January 2025):**
- LangChain Official Docs: https://docs.langchain.com/oss/python/langgraph/
- LangGraph GitHub: https://github.com/langchain-ai/langgraph
- LangGraph How-To Guides: https://langchain-ai.github.io/langgraph/how-tos/

### Core Design Principles

1. **Explicit State Management**: TypedDict with Annotated reducers (operator.add, custom merge functions)
2. **Command-Based Routing**: Combined state updates and routing decisions via `Command(update={...}, goto="node")`
3. **Durable Checkpointing**: SqliteSaver for production, InMemorySaver for testing
4. **Human-in-the-Loop**: `interrupt()` function pauses execution, `Command(resume=...)` resumes
5. **Streaming First**: `astream()` with `stream_mode="updates"` for real-time events
6. **Explicit Retry Logic**: Stateful retry counters with exponential backoff
7. **Modular Composition**: Subgraphs for reusable agent workflows
8. **Thread Isolation**: Each lead gets unique `thread_id` for checkpoint isolation

### Technology Stack

- **LangGraph**: Latest version (v0.2+) with StateGraph, Command, Send, checkpointers
- **Python**: 3.11+ with TypedDict and Annotated types
- **Checkpointing**: SqliteSaver (production), InMemorySaver (testing) - NOT MemorySaver
- **Database**: Supabase/Postgres for lead data, SQLite for checkpoints
- **Packages**: `langgraph`, `langgraph-checkpoint`, `langgraph-checkpoint-sqlite`

## Architecture

### High-Level Graph Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH ORCHESTRATOR                        │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   StateGraph │───▶│  Checkpointer│───▶│   Executor   │       │
│  │   (TypedDict)│    │  (SqliteSaver)│    │  (Streaming) │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     NODE LAYER                            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │   │
│  │  │Discovery│─▶│Enrichment│─▶│ Intent  │─▶│Governance│     │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │   │
│  │       │                                       │           │   │
│  │       ▼                                       ▼           │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐      │   │
│  │  │  Audit  │─▶│ Scoring │─▶│Outreach │─▶│Conversation│   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘      │   │
│  │                    │              │           │           │   │
│  │                    ▼              ▼           ▼           │   │
│  │              [INTERRUPT]    [INTERRUPT]  [ESCALATE]       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   CONTROL LAYER                           │   │
│  │  ├─ Command (state + routing)                            │   │
│  │  ├─ Send (parallel fan-out)                              │   │
│  │  ├─ Interrupt (human-in-the-loop)                        │   │
│  │  └─ RetryPolicy (exponential backoff)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Graph Flow with Commands

```
START
  │
  ▼
[Discovery] ──Command──▶ [Enrichment]
  │                           │
  │                           ▼
  │                      [Intent]
  │                           │
  │                      Command
  │                      ┌────┴────┐
  │                      ▼         ▼
  │               [Audit]    [Scoring] (skip audit)
  │                   │           │
  │                   └─────┬─────┘
  │                         ▼
  │                    [Scoring]
  │                         │
  │                    Command
  │               ┌────────┼────────┐
  │               ▼        ▼        ▼
  │           [End]   [Outreach]  [End]
  │          (Tier C)     │      (DNC)
  │                       │
  │                  INTERRUPT
  │                  (approval)
  │                       │
  │                       ▼
  │               [Conversation]
  │                       │
  │                  Command
  │               ┌───────┴───────┐
  │               ▼               ▼
  │           [End]          [Escalate]
  │        (not qualified)        │
  │                          INTERRUPT
  │                          (handoff)
  │                               │
  │                               ▼
  └──────────────────────────▶ [End]
```

## Components and Interfaces

### 1. State Schema (TypedDict)

**Key Pattern**: Use `TypedDict` with `Annotated` types and reducer functions for proper state aggregation.

```python
from typing import Annotated, TypedDict, Optional, List, Dict, Any, Literal
from operator import add
from langgraph.graph.message import add_messages
from uuid import UUID
from datetime import datetime

def merge_dict(left: Dict, right: Dict) -> Dict:
    """Reducer for merging dictionaries - combines keys from both."""
    if left is None:
        left = {}
    if right is None:
        right = {}
    return {**left, **right}

class LeadGraphState(TypedDict):
    """
    Main state object for lead processing graph.
    Uses TypedDict with Annotated reducers for proper state management.
    
    IMPORTANT: Reducers tell LangGraph how to combine updates from parallel nodes.
    - operator.add: Concatenates lists
    - merge_dict: Merges dictionaries
    - No reducer: Overwrites value
    """
    # Core identifiers (no reducer - overwrites)
    lead_id: UUID
    thread_id: str
    
    # Lead data (loaded from DB, no reducer)
    lead: Optional[Dict[str, Any]]
    
    # Stage tracking (no reducer - overwrites)
    current_stage: str
    last_node: str
    
    # Accumulated data from agents (merge_dict reducer)
    enrichment: Annotated[Dict[str, Any], merge_dict]
    intent: Annotated[Dict[str, Any], merge_dict]
    scoring: Annotated[Dict[str, Any], merge_dict]
    proof: Annotated[Dict[str, Any], merge_dict]
    
    # Outreach messages (operator.add reducer - appends)
    outreach_messages: Annotated[List[Dict], add]
    
    # Conversation (accumulative)
    conversation_transcript: Annotated[List[Dict], add]
    conversation_entities: Annotated[Dict[str, Any], merge_dict]
    
    # Error tracking (accumulative)
    errors: Annotated[List[Dict], add]
    retry_count: int  # No reducer - managed explicitly
    
    # Flags (no reducer - overwrites)
    should_skip_audit: bool
    should_skip_outreach: bool
    is_disqualified: bool
    is_escalated: bool
    is_complete: bool
    requires_approval: bool
    
    # Human-in-the-loop (no reducer)
    approval_status: Optional[str]  # 'pending', 'approved', 'rejected'
    approval_notes: Optional[str]
    
    # Metadata (merge_dict reducer)
    metadata: Annotated[Dict[str, Any], merge_dict]
    
    # Messages for debugging/logging (add_messages reducer)
    messages: Annotated[List[Dict], add_messages]
```

### 2. Checkpointer Configuration

**Key Pattern**: Use `InMemorySaver` for testing, `SqliteSaver` for production. Always use context manager for SqliteSaver.

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
import os

def create_checkpointer(mode: str = "production"):
    """
    Create appropriate checkpointer based on environment.
    
    IMPORTANT: 
    - InMemorySaver: For testing, data lost on restart
    - SqliteSaver: For production, persists to disk
    - Use context manager with SqliteSaver for proper cleanup
    
    Args:
        mode: "production" for SqliteSaver, "testing" for InMemorySaver
    
    Returns:
        Configured checkpointer instance
    """
    if mode == "testing":
        return InMemorySaver()
    
    # Production: Use SQLite with configurable path
    db_path = os.getenv("LANGGRAPH_CHECKPOINT_DB", "checkpoints/langgraph.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # SqliteSaver can be used with context manager or directly
    # For long-running apps, use from_conn_string
    return SqliteSaver.from_conn_string(db_path)


# Usage with context manager (recommended for scripts):
# with SqliteSaver.from_conn_string("checkpoints/langgraph.db") as checkpointer:
#     graph = builder.compile(checkpointer=checkpointer)
#     result = graph.invoke(state, config)

# Usage for long-running apps:
# checkpointer = SqliteSaver.from_conn_string("checkpoints/langgraph.db")
# graph = builder.compile(checkpointer=checkpointer)
```

### 3. Command-Based Node Functions

**Key Pattern**: Return `Command` objects to combine state updates with routing decisions. Use `Literal` type hints for graph visualization.

```python
from langgraph.types import Command
from typing import Literal

def scoring_node(state: LeadGraphState) -> Command[Literal["outreach", "end"]]:
    """
    Scoring node using Command for combined state update and routing.
    
    IMPORTANT: The Literal type hint tells LangGraph which nodes this can route to.
    This is required for proper graph rendering and validation.
    """
    # Compute scores
    final_score = compute_final_score(state)
    tier = assign_tier(final_score)
    is_disqualified = check_disqualification(state)
    
    # Build state update
    update = {
        "scoring": {
            "final_score": final_score,
            "lead_tier": tier,
            "do_not_contact": is_disqualified,
        },
        "is_disqualified": is_disqualified,
        "current_stage": "scoring",
        "last_node": "scoring",
    }
    
    # Determine routing based on results
    if is_disqualified:
        return Command(update=update, goto="end")
    elif tier == "C":
        update["should_skip_outreach"] = True
        return Command(update=update, goto="end")
    else:
        return Command(update=update, goto="outreach")


def intent_node(state: LeadGraphState) -> Command[Literal["audit", "scoring"]]:
    """
    Intent node with conditional routing to audit or scoring.
    
    Uses Command to combine state update with routing decision.
    """
    # Compute intent and leak scores
    intent_score = compute_intent_score(state)
    leak_score = compute_leak_score(state)
    
    update = {
        "intent": {
            "intent_score": intent_score,
            "leak_score": leak_score,
        },
        "current_stage": "intent",
        "last_node": "intent",
    }
    
    # Route to audit if high leak score, otherwise skip to scoring
    if leak_score >= 70 and not state.get("should_skip_audit"):
        return Command(update=update, goto="audit")
    else:
        update["should_skip_audit"] = True
        return Command(update=update, goto="scoring")
```

### 4. Parallel Processing with Send

**Key Pattern**: Use `Send` objects from conditional edges for dynamic fan-out. Reducers automatically aggregate parallel results.

```python
from langgraph.types import Send, Command
from typing import Literal

def discovery_router(state: LeadGraphState) -> list[Send] | Command[Literal["enrichment", "end"]]:
    """
    Discovery router that fans out to parallel enrichment.
    
    IMPORTANT: Send is returned from conditional edges, not regular nodes.
    Each Send creates a parallel branch with its own state.
    """
    discovered_leads = state.get("metadata", {}).get("discovered_leads", [])
    
    if len(discovered_leads) > 1:
        # Fan out to parallel enrichment - each lead gets its own branch
        return [
            Send("enrichment", {
                "lead_id": lead["lead_id"],
                "lead": lead,
                "thread_id": f"{state['thread_id']}_lead_{i}",
            })
            for i, lead in enumerate(discovered_leads)
        ]
    elif len(discovered_leads) == 1:
        # Single lead, proceed normally
        return Command(
            update={"lead": discovered_leads[0]},
            goto="enrichment",
        )
    else:
        # No leads found
        return Command(
            update={"is_complete": True},
            goto="end",
        )


def aggregate_enrichment(state: LeadGraphState) -> dict:
    """
    Aggregate results from parallel enrichment branches.
    
    IMPORTANT: Reducers (operator.add, merge_dict) automatically 
    combine results from parallel branches. This node just marks completion.
    """
    return {
        "current_stage": "aggregation",
        "last_node": "aggregate_enrichment",
    }


# Graph setup for parallel processing:
# builder.add_conditional_edges(
#     "discovery",
#     discovery_router,
#     ["enrichment", "end"],  # Possible destinations
# )
```

### 5. Human-in-the-Loop with Interrupt

**Key Pattern**: Use `interrupt()` function to pause execution, `Command(resume=...)` to resume with user input.

```python
from langgraph.types import interrupt, Command
from langchain_core.messages import ToolMessage

def outreach_node(state: LeadGraphState) -> dict:
    """
    Outreach generation node.
    
    IMPORTANT: Graph will interrupt AFTER this node if configured with
    interrupt_after=["outreach"] during compilation.
    """
    # Generate outreach messages
    messages = generate_outreach_messages(state)
    
    return {
        "outreach_messages": messages,
        "requires_approval": True,
        "approval_status": "pending",
        "current_stage": "outreach",
        "last_node": "outreach",
    }


def approval_node(state: LeadGraphState) -> dict:
    """
    Human approval node using interrupt().
    
    IMPORTANT: interrupt() pauses the graph and saves state.
    The graph resumes when invoked with Command(resume=...).
    """
    # This will pause execution and wait for human input
    approval_response = interrupt({
        "question": "Please review the outreach messages and approve/reject",
        "messages": state.get("outreach_messages", []),
        "lead_id": str(state["lead_id"]),
    })
    
    # When resumed, approval_response contains the human's decision
    return {
        "approval_status": approval_response.get("status", "rejected"),
        "approval_notes": approval_response.get("notes", ""),
    }


def send_outreach_node(state: LeadGraphState) -> Command[Literal["conversation", "end"]]:
    """
    Send outreach after approval.
    Only executes if approval_status == 'approved'.
    """
    if state.get("approval_status") != "approved":
        return Command(
            update={"errors": [{"node": "send_outreach", "error": "Not approved"}]},
            goto="end",
        )
    
    # Send the approved messages
    send_results = send_messages(state["outreach_messages"])
    
    return Command(
        update={
            "metadata": {"send_results": send_results},
            "current_stage": "sent",
        },
        goto="conversation",
    )


# Resuming from interrupt:
# config = {"configurable": {"thread_id": str(lead_id)}}
# result = graph.invoke(
#     Command(resume={"status": "approved", "notes": "Looks good!"}),
#     config
# )
```

### 6. Retry Policy Implementation

**Key Pattern**: Use explicit retry counters in state with exponential backoff. LangGraph doesn't have built-in RetryPolicy for nodes.

```python
from typing import Callable, TypeVar
from datetime import datetime, timedelta
import functools
import logging

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY_MS = 1000

T = TypeVar('T')

def with_retry(max_retries: int = MAX_RETRIES, base_delay_ms: int = BASE_DELAY_MS):
    """
    Decorator for adding retry logic to nodes.
    
    IMPORTANT: LangGraph doesn't have built-in RetryPolicy for nodes.
    We implement retry by catching exceptions and routing back to the same node.
    """
    def decorator(node_func: Callable) -> Callable:
        @functools.wraps(node_func)
        def wrapper(state: LeadGraphState) -> Command:
            node_name = node_func.__name__
            retry_key = f"{node_name}_retry_count"
            retry_count = state.get("metadata", {}).get(retry_key, 0)
            
            try:
                result = node_func(state)
                # Reset retry count on success
                if isinstance(result, Command):
                    if "metadata" not in result.update:
                        result.update["metadata"] = {}
                    result.update["metadata"][retry_key] = 0
                return result
                
            except Exception as e:
                logger.warning(f"Node {node_name} failed (attempt {retry_count + 1}): {e}")
                
                if retry_count < max_retries:
                    # Calculate backoff delay
                    delay_ms = base_delay_ms * (2 ** retry_count)
                    
                    return Command(
                        update={
                            "metadata": {
                                retry_key: retry_count + 1,
                                "last_error": str(e),
                                "backoff_until": (datetime.utcnow() + timedelta(milliseconds=delay_ms)).isoformat(),
                            },
                            "errors": [{
                                "node": node_name,
                                "error": str(e),
                                "retry_count": retry_count + 1,
                                "timestamp": datetime.utcnow().isoformat(),
                            }],
                        },
                        goto=node_name,  # Retry same node
                    )
                else:
                    # Max retries exceeded, route to error handler
                    logger.error(f"Node {node_name} failed after {max_retries} retries")
                    return Command(
                        update={
                            "errors": [{
                                "node": node_name,
                                "error": str(e),
                                "retry_count": retry_count,
                                "fatal": True,
                            }],
                        },
                        goto="handle_error",
                    )
        
        return wrapper
    return decorator


@with_retry(max_retries=2, base_delay_ms=5000)
def audit_node(state: LeadGraphState) -> Command[Literal["scoring"]]:
    """
    Audit node with automatic retry on failure.
    Uses Steel.dev for browser automation.
    """
    # Call Steel.dev for browser automation
    proof_pack = run_steel_audit(state["lead"])
    
    return Command(
        update={
            "proof": proof_pack,
            "current_stage": "audit",
            "last_node": "audit",
        },
        goto="scoring",
    )
```

### 7. Streaming Configuration

**Key Pattern**: Use `astream()` with `stream_mode` parameter for real-time updates.

```python
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import InMemorySaver
from typing import AsyncIterator

def build_graph_with_streaming():
    """
    Build graph with streaming support.
    
    IMPORTANT: Streaming modes:
    - "values": Full state after each step
    - "updates": Only the updates from each node
    - "messages": Stream LLM tokens (if using chat models)
    - "custom": Custom stream events via get_stream_writer()
    """
    graph = StateGraph(LeadGraphState)
    
    # Add nodes
    graph.add_node("discovery", discovery_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("intent", intent_node)
    graph.add_node("governance", governance_node)
    graph.add_node("audit", audit_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("approval", approval_node)
    graph.add_node("send_outreach", send_outreach_node)
    graph.add_node("conversation", conversation_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("handle_error", error_handler_node)
    graph.add_node("end", end_node)
    
    # Set entry point
    graph.add_edge(START, "discovery")
    
    # Add edges - Commands handle most routing
    graph.add_edge("discovery", "enrichment")
    graph.add_edge("enrichment", "intent")
    # intent uses Command to route to audit or scoring
    graph.add_edge("intent", "governance")
    graph.add_edge("governance", "audit")
    graph.add_edge("audit", "scoring")
    # scoring uses Command to route to outreach or end
    graph.add_edge("outreach", "approval")
    graph.add_edge("approval", "send_outreach")
    graph.add_edge("send_outreach", "conversation")
    graph.add_edge("conversation", "escalate")
    graph.add_edge("escalate", "end")
    graph.add_edge("handle_error", "end")
    graph.add_edge("end", END)
    
    # Compile with checkpointer and interrupts
    checkpointer = InMemorySaver()  # Use SqliteSaver for production
    
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["approval"],  # Pause before approval node
        interrupt_after=["escalate"],   # Pause after escalation
    )


# Usage with streaming
async def process_lead_with_streaming(lead_id: UUID) -> AsyncIterator[dict]:
    """
    Process a lead with real-time streaming events.
    
    stream_mode options:
    - "updates": Emits state updates from each node (recommended)
    - "values": Emits full state after each node
    - ["updates", "custom"]: Multiple modes
    """
    app = build_graph_with_streaming()
    
    initial_state = {
        "lead_id": lead_id,
        "thread_id": str(lead_id),
        "current_stage": "start",
        "last_node": "start",
        "enrichment": {},
        "intent": {},
        "scoring": {},
        "proof": {},
        "outreach_messages": [],
        "conversation_transcript": [],
        "conversation_entities": {},
        "errors": [],
        "retry_count": 0,
        "should_skip_audit": False,
        "should_skip_outreach": False,
        "is_disqualified": False,
        "is_escalated": False,
        "is_complete": False,
        "requires_approval": False,
        "metadata": {},
        "messages": [],
    }
    
    config = {"configurable": {"thread_id": str(lead_id)}}
    
    # Stream updates from each node
    async for event in app.astream(initial_state, config, stream_mode="updates"):
        yield {
            "type": "state_update",
            "node": list(event.keys())[0] if event else None,
            "data": event,
            "timestamp": datetime.utcnow().isoformat(),
        }
```

### 8. Graph Visualization

**Key Pattern**: Use `get_graph().draw_mermaid()` for visualization. Requires proper type hints on Command returns.

```python
def get_graph_mermaid() -> str:
    """
    Generate Mermaid diagram of the graph structure.
    
    IMPORTANT: For proper visualization, nodes returning Command must have
    Literal type hints specifying possible destinations:
    
    def my_node(state) -> Command[Literal["node_a", "node_b"]]:
        ...
    """
    app = build_graph_with_streaming()
    return app.get_graph().draw_mermaid()


def get_graph_png() -> bytes:
    """Generate PNG image of the graph (requires graphviz)."""
    app = build_graph_with_streaming()
    return app.get_graph().draw_mermaid_png()


def get_execution_trace(thread_id: str) -> list[dict]:
    """
    Get execution trace for debugging.
    
    Uses get_state_history() to retrieve all checkpoints for a thread.
    """
    app = build_graph_with_streaming()
    config = {"configurable": {"thread_id": thread_id}}
    
    traces = []
    for state_snapshot in app.get_state_history(config):
        traces.append({
            "checkpoint_id": state_snapshot.config["configurable"].get("checkpoint_id"),
            "node": state_snapshot.metadata.get("source"),
            "step": state_snapshot.metadata.get("step"),
            "next_nodes": state_snapshot.next,
            "created_at": state_snapshot.created_at,
            "state_keys": list(state_snapshot.values.keys()),
        })
    
    return traces


def get_current_state(thread_id: str) -> dict:
    """Get the current state for a thread."""
    app = build_graph_with_streaming()
    config = {"configurable": {"thread_id": thread_id}}
    
    state_snapshot = app.get_state(config)
    return {
        "values": state_snapshot.values,
        "next": state_snapshot.next,
        "config": state_snapshot.config,
        "metadata": state_snapshot.metadata,
    }
```

## Data Models

### State Persistence Schema

```sql
-- LangGraph checkpoints (managed by SqliteSaver)
-- This is automatically created by SqliteSaver

-- Additional metadata table for ZRAI-specific tracking
CREATE TABLE lead_execution_metadata (
    lead_id UUID PRIMARY KEY,
    thread_id TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    last_node TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    is_complete BOOLEAN DEFAULT FALSE,
    requires_approval BOOLEAN DEFAULT FALSE,
    approval_status TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_execution_thread (thread_id),
    INDEX idx_execution_stage (current_stage),
    INDEX idx_execution_approval (requires_approval, approval_status)
);
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: State Reducer Aggregation

*For any* list field in LeadGraphState with an `add` reducer, updating that field multiple times should result in all values being aggregated (concatenated) rather than replaced.

**Validates: Requirements 2.2**

### Property 2: Checkpoint Round-Trip Persistence

*For any* graph execution that is interrupted and resumed, the state restored from the checkpoint should be equivalent to the state at the time of interruption.

**Validates: Requirements 3.2, 3.3**

### Property 3: Thread Isolation

*For any* two different thread_ids, their checkpoint states should be completely independent—updating state for one thread should not affect the other.

**Validates: Requirements 3.4**

### Property 4: Command Routing Correctness

*For any* node that returns a Command object, the graph should route to the node specified in the Command's `goto` field and apply the state updates in the Command's `update` field.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 5: Parallel Fan-Out and Aggregation

*For any* discovery that returns N leads (N > 1), the graph should fan out to N parallel enrichment branches and aggregate all results using the configured reducers.

**Validates: Requirements 5.1, 5.2**

### Property 6: Parallelism Limit Enforcement

*For any* batch of leads being processed, the number of concurrently executing branches should never exceed the configured max_parallel_leads limit.

**Validates: Requirements 5.3**

### Property 7: Parallel Failure Isolation

*For any* parallel branch that fails, other parallel branches should continue execution unaffected, and the failure should be recorded in the errors list.

**Validates: Requirements 5.4**

### Property 8: Interrupt Pause and Resume

*For any* node configured with interrupt_before, execution should pause before that node, and calling resume should continue from exactly that point.

**Validates: Requirements 6.1, 6.2**

### Property 9: Rejection Routing

*For any* interrupted execution where approval_status is set to 'rejected', the graph should route to the end node or an alternative error handling path.

**Validates: Requirements 6.3**

### Property 10: Stream Event Completeness

*For any* graph execution in streaming mode, stream events should be emitted for: node start/complete with timing, state updates with changed fields, and errors with details.

**Validates: Requirements 7.2, 7.3, 7.4**

### Property 11: Exponential Backoff Pattern

*For any* node failure that triggers retry, the delay between retries should follow exponential backoff: delay = base_delay * (2 ^ retry_count).

**Validates: Requirements 8.1**

### Property 12: Circuit Breaker Activation

*For any* node that fails more than max_retries times, the circuit breaker should transition to OPEN state and subsequent requests should be routed around the failing node.

**Validates: Requirements 8.3**

### Property 13: Retry Logging Completeness

*For any* retry attempt, the log entry should contain: node name, retry count, delay duration, and error message.

**Validates: Requirements 8.4**

### Property 14: Subgraph State Merge

*For any* subgraph execution, the subgraph's output state should be properly merged back into the parent graph's state according to the defined field mappings.

**Validates: Requirements 9.2**

### Property 15: Execution Trace Completeness

*For any* completed graph execution, the execution trace should contain entries for every node visited, with node name, start time, end time, and duration.

**Validates: Requirements 10.2**

### Property 16: Error Context Completeness

*For any* error that occurs during graph execution, the error context should include: node name where error occurred, current state snapshot, and stack trace.

**Validates: Requirements 10.3**

### Property 17: Backward-Compatible State Evolution

*For any* checkpoint created with an older state schema, loading it with a newer schema (with additional optional fields) should succeed without data loss.

**Validates: Requirements 11.3**


## Error Handling

### Error Classification

**Transient Errors** (retry with backoff):
- Network timeouts
- API rate limits (429)
- Temporary service unavailability (503)
- Database connection failures

**Permanent Errors** (fail fast, no retry):
- Invalid configuration
- Missing required fields
- Schema validation failures
- Authentication failures (401)

**Partial Failures** (isolate and continue):
- Single parallel branch failure
- Optional node failure (e.g., audit)
- Non-critical enrichment failure

### Retry Configuration

```python
RETRY_CONFIG = {
    "default": {
        "max_attempts": 3,
        "base_delay_ms": 1000,
        "max_delay_ms": 60000,
        "exponential_base": 2,
    },
    "apify": {
        "max_attempts": 5,
        "base_delay_ms": 2000,
        "max_delay_ms": 120000,
    },
    "steel": {
        "max_attempts": 2,
        "base_delay_ms": 5000,
        "max_delay_ms": 30000,
    },
    "llm": {
        "max_attempts": 3,
        "base_delay_ms": 1000,
        "max_delay_ms": 30000,
    },
}
```

### Circuit Breaker States

```
CLOSED → OPEN: failure_count >= failure_threshold
OPEN → HALF_OPEN: timeout_seconds elapsed
HALF_OPEN → CLOSED: successful request
HALF_OPEN → OPEN: failed request
```


## Testing Strategy

### Property-Based Testing

**Framework**: Use `hypothesis` for Python property-based testing.

**Configuration**: Each property test must run minimum **100 iterations**.

**Test Tagging**: Each test must reference the design property:
```python
# Feature: langgraph-upgrade, Property 2: Checkpoint Round-Trip Persistence
@given(state=st.builds(LeadGraphState, ...))
def test_checkpoint_round_trip(state):
    ...
```

### Unit Testing Focus Areas

1. **Graph Compilation**: Verify graph compiles without errors
2. **Node Functions**: Test each node function in isolation
3. **Command Routing**: Test Command objects route correctly
4. **Interrupt Behavior**: Test pause/resume functionality
5. **Error Handling**: Test retry and circuit breaker logic

### Integration Testing

1. **End-to-End Flow**: Test complete lead processing pipeline
2. **Checkpoint Persistence**: Test state survives process restart
3. **Streaming Events**: Test real-time event emission
4. **Parallel Processing**: Test fan-out/fan-in with multiple leads

