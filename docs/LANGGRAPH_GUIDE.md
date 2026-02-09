# LangGraph Professional Implementation Guide

## Overview

This guide documents all LangGraph features and best practices for the ZRAI Lead OS system. It serves as a reference for maintaining and extending the graph-based orchestration.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [State Management](#state-management)
3. [Checkpointing & Persistence](#checkpointing--persistence)
4. [Streaming](#streaming)
5. [Parallel Execution](#parallel-execution)
6. [Error Handling & Retry Policies](#error-handling--retry-policies)
7. [Human-in-the-Loop](#human-in-the-loop)
8. [Subgraphs](#subgraphs)
9. [Time Travel & Debugging](#time-travel--debugging)
10. [Best Practices](#best-practices)

---

## Core Concepts

### StateGraph

The `StateGraph` is the foundation of LangGraph. It manages state transitions through nodes connected by edges.

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

class State(TypedDict):
    value: str
    count: int

graph = StateGraph(State)
graph.add_node("process", process_node)
graph.add_edge(START, "process")
graph.add_edge("process", END)
compiled = graph.compile()
```

### Nodes

Nodes are functions that receive state and return state updates:

```python
def my_node(state: State) -> dict:
    # Process state
    return {"value": state["value"] + "_processed"}
```

### Edges

- **Static edges**: Always follow the same path
- **Conditional edges**: Route based on state

```python
# Static edge
graph.add_edge("node_a", "node_b")

# Conditional edge
def router(state: State) -> Literal["path_a", "path_b"]:
    if state["condition"]:
        return "path_a"
    return "path_b"

graph.add_conditional_edges(
    "decision_node",
    router,
    {"path_a": "node_a", "path_b": "node_b"}
)
```

---

## State Management

### State Schema with TypedDict

```python
from typing import TypedDict, Annotated, List
from langgraph.graph.message import add_messages

class LeadState(TypedDict):
    lead_id: str
    stage: str
    # Use Annotated for reducer functions
    messages: Annotated[List[dict], add_messages]
    score: int
```

### State Reducers

Reducers define how state updates are merged:

```python
import operator

class State(TypedDict):
    # Append to list
    items: Annotated[List[str], operator.add]
    # Replace value (default behavior)
    current: str
```

### Pydantic Models for Complex State

```python
from pydantic import BaseModel, Field

class LeadGraphState(BaseModel):
    lead_id: UUID
    lead: Optional[Lead] = None
    current_stage: str = "discovery"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
```

---

## Checkpointing & Persistence

### Built-in Checkpointers

LangGraph provides several checkpointer implementations:

```python
# In-memory (development)
from langgraph.checkpoint.memory import InMemorySaver
checkpointer = InMemorySaver()

# PostgreSQL (production)
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(DB_URI)

# Redis
from langgraph.checkpoint.redis import RedisSaver
checkpointer = RedisSaver.from_conn_string(REDIS_URI)

# MongoDB
from langgraph.checkpoint.mongodb import MongoDBSaver
checkpointer = MongoDBSaver.from_conn_string(MONGO_URI)
```

### Custom Checkpointer (Supabase)

For custom storage backends, implement `BaseCheckpointSaver`:

```python
from langgraph.checkpoint.base import (
    BaseCheckpointSaver, 
    Checkpoint, 
    CheckpointMetadata, 
    CheckpointTuple
)

class SupabaseCheckpointer(BaseCheckpointSaver):
    def put(self, config, checkpoint, metadata, new_versions=None):
        # Save checkpoint to Supabase
        pass
    
    def get_tuple(self, config) -> Optional[CheckpointTuple]:
        # Retrieve checkpoint
        pass
    
    def list(self, config=None, *, filter=None, before=None, limit=None):
        # List checkpoints for time travel
        pass
```

### Thread-based Execution

```python
config = {
    "configurable": {
        "thread_id": str(lead_id)  # Unique per conversation/lead
    }
}

result = graph.invoke(initial_state, config)
```

---

## Streaming

### Stream Modes

LangGraph supports multiple streaming modes:

```python
# Stream complete state after each step
for chunk in graph.stream(inputs, stream_mode="values"):
    print(f"State: {chunk}")

# Stream only state updates
for chunk in graph.stream(inputs, stream_mode="updates"):
    for node_name, update in chunk.items():
        print(f"{node_name}: {update}")

# Stream debug information
for chunk in graph.stream(inputs, stream_mode="debug"):
    print(f"Debug: {chunk}")

# Stream LLM tokens
async for chunk in graph.astream(inputs, stream_mode="messages"):
    print(chunk)
```

### Async Streaming

```python
async for chunk in graph.astream(inputs, stream_mode="updates"):
    await process_chunk(chunk)
```

### Multiple Stream Modes

```python
async for mode, chunk in graph.astream(
    inputs, 
    stream_mode=["updates", "custom"]
):
    if mode == "updates":
        handle_update(chunk)
    elif mode == "custom":
        handle_custom(chunk)
```

---

## Parallel Execution

### Static Fan-out

Multiple nodes can execute in parallel when they share the same source:

```python
# All three nodes run in parallel
graph.add_edge(START, "node_a")
graph.add_edge(START, "node_b")
graph.add_edge(START, "node_c")

# Fan-in: all converge to aggregator
graph.add_edge("node_a", "aggregator")
graph.add_edge("node_b", "aggregator")
graph.add_edge("node_c", "aggregator")
```

### Dynamic Fan-out with Send API

For dynamic parallel execution based on runtime data:

```python
from langgraph.types import Send

def fan_out_to_workers(state: State) -> list[Send]:
    """Create parallel tasks dynamically."""
    return [
        Send("worker", {"task_id": task["id"], "data": task})
        for task in state["tasks"]
    ]

graph.add_conditional_edges(
    "splitter",
    fan_out_to_workers,
    ["worker"]  # Target node for all Send objects
)
graph.add_edge("worker", "aggregator")
```

### Map-Reduce Pattern

```python
class MapReduceState(TypedDict):
    documents: list[str]
    summaries: Annotated[list[str], operator.add]
    final_summary: str

def split_documents(state: MapReduceState) -> list[Send]:
    return [
        Send("summarize", {"doc_id": i, "content": doc})
        for i, doc in enumerate(state["documents"])
    ]

def reduce_summaries(state: MapReduceState) -> dict:
    combined = "\n".join(state["summaries"])
    return {"final_summary": llm.invoke(f"Summarize: {combined}")}

graph.add_conditional_edges("split", split_documents, ["summarize"])
graph.add_edge("summarize", "reduce")
```

---

## Error Handling & Retry Policies

### RetryPolicy Configuration

```python
from langgraph.types import RetryPolicy

# Default retry policy (retries on network errors)
graph.add_node("api_call", api_node, retry_policy=RetryPolicy())

# Custom retry policy
graph.add_node(
    "database_query",
    db_node,
    retry_policy=RetryPolicy(
        max_attempts=5,
        retry_on=sqlite3.OperationalError
    )
)

# Retry on specific exceptions
retry_policy = RetryPolicy(
    retry_on=lambda e: isinstance(e, (ConnectionError, TimeoutError))
)
```

### Default Retry Behavior

By default, `RetryPolicy` does NOT retry on:
- `ValueError`, `TypeError`, `ArithmeticError`
- `ImportError`, `LookupError`, `NameError`
- `SyntaxError`, `RuntimeError`, `ReferenceError`
- `StopIteration`, `StopAsyncIteration`, `OSError`

For HTTP libraries, only retries on 5xx status codes.

### Functional API with Retry

```python
from langgraph.func import entrypoint, task
from langgraph.types import RetryPolicy

@task(retry_policy=RetryPolicy(retry_on=ValueError))
def get_info():
    # Task with retry
    return api_call()

@entrypoint(checkpointer=checkpointer)
def main(inputs, writer):
    return get_info().result()
```

---

## Human-in-the-Loop

### Interrupt Function

Pause execution and wait for human input:

```python
from langgraph.types import interrupt, Command

def human_review_node(state: State):
    # Pause and request human input
    human_response = interrupt({
        "question": "Please review this data",
        "data": state["data_to_review"]
    })
    return {"approved": human_response["approved"]}
```

### Resuming Execution

```python
# Initial run - will pause at interrupt
config = {"configurable": {"thread_id": "123"}}
result = graph.invoke(initial_state, config)

# Check for interrupt
if result.get("__interrupt__"):
    print("Waiting for human input...")
    
# Resume with human input
from langgraph.types import Command
result = graph.invoke(
    Command(resume={"approved": True}),
    config
)
```

### Human Approval for Tool Calls

```python
@tool
def human_assistance(query: str) -> str:
    """Request assistance from a human."""
    human_response = interrupt({"query": query})
    return human_response["data"]

# Resume with approval
graph.invoke(
    Command(resume={"type": "accept"}),
    config
)

# Resume with edits
graph.invoke(
    Command(resume={"type": "edit", "args": {"value": "new_value"}}),
    config
)
```

---

## Subgraphs

### Same State Schema

When parent and child share the same schema:

```python
# Child graph
child_builder = StateGraph(State)
child_builder.add_node("child_node", child_fn)
child_builder.add_edge(START, "child_node")
child_graph = child_builder.compile()

# Parent graph - add compiled graph as node
parent_builder = StateGraph(State)
parent_builder.add_node("child", child_graph)
parent_builder.add_edge(START, "child")
```

### Different State Schemas

When schemas differ, transform state explicitly:

```python
class ParentState(TypedDict):
    my_key: str

class ChildState(TypedDict):
    child_key: str

def call_child_graph(state: ParentState) -> ParentState:
    # Transform to child schema
    child_input = {"child_key": state["my_key"]}
    child_output = child_graph.invoke(child_input)
    # Transform back to parent schema
    return {"my_key": child_output["child_key"]}

parent.add_node("child", call_child_graph)
```

### Checkpointer Propagation

When compiling with a checkpointer, it automatically propagates to subgraphs:

```python
checkpointer = InMemorySaver()
parent_graph = parent_builder.compile(checkpointer=checkpointer)
# Child graphs automatically use the same checkpointer
```

---

## Time Travel & Debugging

### Get State History

```python
# Get all checkpoints for a thread
history = graph.get_state_history(config)
for state in history:
    print(f"Checkpoint: {state.config['checkpoint_id']}")
    print(f"State: {state.values}")
```

### Resume from Checkpoint

```python
# Get specific checkpoint
checkpoint_config = {
    "configurable": {
        "thread_id": "123",
        "checkpoint_id": "abc123"
    }
}

# Resume from that checkpoint
result = graph.invoke(None, checkpoint_config)
```

### Update State at Checkpoint

```python
# Modify state at a specific checkpoint
new_config = graph.update_state(
    config,
    {"topic": "new_topic"},
    checkpoint_id=checkpoint_id
)

# Resume from modified state
result = graph.invoke(None, new_config)
```

### Debug Streaming

```python
for event in graph.stream(inputs, stream_mode="debug"):
    print(f"Event type: {event.get('type')}")
    print(f"Node: {event.get('node')}")
    print(f"Data: {event.get('data')}")
```

---

## Best Practices

### 1. State Design

- Use `TypedDict` or Pydantic for type safety
- Keep state flat when possible
- Use reducers for list accumulation
- Include metadata for debugging

### 2. Node Design

- Keep nodes focused on single responsibility
- Return only changed state keys
- Handle errors gracefully
- Log important transitions

### 3. Checkpointing

- Always use checkpointer in production
- Use thread_id for multi-tenant isolation
- Implement proper cleanup for old checkpoints
- Test checkpoint/resume flows

### 4. Error Handling

- Configure retry policies for external calls
- Use circuit breakers for failing services
- Log errors with context
- Implement graceful degradation

### 5. Testing

- Test individual nodes in isolation
- Test graph flows end-to-end
- Test checkpoint/resume scenarios
- Test error recovery paths

### 6. Performance

- Use parallel execution where possible
- Stream results for long-running operations
- Implement caching where appropriate
- Monitor execution times

### 7. Human-in-the-Loop

- Design clear interrupt points
- Provide context in interrupt payloads
- Handle timeout scenarios
- Log human decisions for audit

---

## ZRAI Lead OS Implementation

### Current Architecture

```
Discovery → Enrichment → Intent → Governance → Audit → Scoring → Outreach → Conversation → Escalation
                                      ↓
                                  (skip audit)
                                      ↓
                                   Scoring
```

### Recommended Improvements

1. **Add RetryPolicy to external API nodes**
2. **Implement parallel enrichment** (tech signals + contacts)
3. **Add streaming support** for real-time updates
4. **Implement proper human-in-the-loop** for escalations
5. **Add time travel** for debugging failed leads
6. **Use Send API** for batch lead processing

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [Checkpointing Guide](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [Human-in-the-Loop Guide](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/)
