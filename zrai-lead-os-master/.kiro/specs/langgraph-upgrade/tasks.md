# Implementation Tasks: LangGraph Professional Upgrade

## Task 1: Fix Syntax Errors and Update Imports

### Description
Fix the syntax error in `src/graph/orchestrator.py` (line 36 has corrupted code) and update all imports to use the latest LangGraph API.

### Requirements Addressed
- Requirement 1: Fix Syntax Errors and Core Graph Structure

### Acceptance Criteria
- [ ] Orchestrator module imports without syntax errors
- [ ] All LangGraph imports use latest API (langgraph.types, langgraph.checkpoint.memory, etc.)
- [ ] Graph compiles successfully

### Files to Modify
- `src/graph/orchestrator.py`
- `src/graph/state.py`
- `src/graph/checkpointer.py`

### Dependencies
None

---

## Task 2: Implement TypedDict State with Reducers

### Description
Update `LeadGraphState` to use proper TypedDict with Annotated reducers for list aggregation and dictionary merging.

### Requirements Addressed
- Requirement 2: Modern State Management with TypedDict

### Acceptance Criteria
- [ ] LeadGraphState uses TypedDict (not Pydantic BaseModel)
- [ ] List fields use `Annotated[List[...], operator.add]` reducer
- [ ] Dict fields use `Annotated[Dict[...], merge_dict]` reducer
- [ ] All state fields have proper type annotations

### Files to Modify
- `src/graph/state.py`

### Dependencies
- Task 1

---

## Task 3: Implement Standard Checkpointer

### Description
Replace custom SupabaseCheckpointer with standard LangGraph checkpointers (InMemorySaver for testing, SqliteSaver for production).

### Requirements Addressed
- Requirement 3: Proper Checkpointing with SqliteSaver/MemorySaver

### Acceptance Criteria
- [ ] InMemorySaver used for testing mode
- [ ] SqliteSaver used for production mode
- [ ] Checkpointer factory function created
- [ ] Thread isolation works correctly
- [ ] State persists across restarts (SqliteSaver)

### Files to Modify
- `src/graph/checkpointer.py`
- `src/graph/orchestrator.py`

### Dependencies
- Task 1, Task 2

---

## Task 4: Implement Command-Based Routing

### Description
Refactor node functions to return Command objects for combined state updates and routing decisions.

### Requirements Addressed
- Requirement 4: Command-Based Routing

### Acceptance Criteria
- [ ] Scoring node returns Command with goto="outreach" or goto="end"
- [ ] Intent node returns Command with goto="audit" or goto="scoring"
- [ ] All routing nodes have Literal type hints for destinations
- [ ] Conditional edge functions replaced with Command returns where appropriate

### Files to Modify
- `src/graph/orchestrator.py`
- `src/agents/scoring.py`
- `src/agents/intent.py`

### Dependencies
- Task 1, Task 2, Task 3

---

## Task 5: Implement Human-in-the-Loop with Interrupt

### Description
Add interrupt() function for human approval workflows in outreach and escalation nodes.

### Requirements Addressed
- Requirement 6: Human-in-the-Loop with Interrupt

### Acceptance Criteria
- [ ] Approval node uses interrupt() to pause execution
- [ ] Graph compiled with interrupt_before for approval points
- [ ] Command(resume=...) resumes execution with user input
- [ ] Rejection routes to alternative path

### Files to Modify
- `src/graph/orchestrator.py`
- `src/agents/outreach.py`

### Dependencies
- Task 1, Task 2, Task 3, Task 4

---

## Task 6: Implement Streaming Support

### Description
Add streaming support for real-time execution events using astream() with stream_mode.

### Requirements Addressed
- Requirement 7: Streaming Support

### Acceptance Criteria
- [ ] process_lead_with_streaming() async generator implemented
- [ ] stream_mode="updates" emits node updates
- [ ] Events include node name, timestamp, and state changes
- [ ] Error events emitted on failures

### Files to Modify
- `src/graph/orchestrator.py`
- `src/api/server.py` (if streaming endpoint needed)

### Dependencies
- Task 1, Task 2, Task 3, Task 4

---

## Task 7: Implement Retry Policies

### Description
Add retry decorator with exponential backoff for nodes that call external services.

### Requirements Addressed
- Requirement 8: Retry Policies for External Services

### Acceptance Criteria
- [ ] with_retry decorator implemented
- [ ] Exponential backoff with configurable base delay
- [ ] Per-service retry configuration (Apify, Steel, LLM)
- [ ] Max retries exceeded routes to error handler
- [ ] Retry attempts logged with delay information

### Files to Modify
- `src/graph/orchestrator.py`
- `src/agents/audit.py`
- `src/agents/enrichment.py`

### Dependencies
- Task 1, Task 2, Task 3, Task 4

---

## Task 8: Add Graph Visualization

### Description
Add methods for generating Mermaid diagrams and execution traces.

### Requirements Addressed
- Requirement 10: Graph Visualization and Debugging

### Acceptance Criteria
- [ ] get_graph_mermaid() returns valid Mermaid diagram
- [ ] get_execution_trace() returns checkpoint history
- [ ] get_current_state() returns current thread state
- [ ] Error context includes node name and state snapshot

### Files to Modify
- `src/graph/orchestrator.py`

### Dependencies
- Task 1, Task 2, Task 3

---

## Task 9: Update Tests

### Description
Update existing tests and add new property-based tests for LangGraph features.

### Requirements Addressed
- All requirements (testing)

### Acceptance Criteria
- [ ] Existing tests pass with new implementation
- [ ] Property tests for reducer aggregation
- [ ] Property tests for checkpoint round-trip
- [ ] Property tests for thread isolation
- [ ] Property tests for Command routing

### Files to Modify
- `tests/test_property_state.py`
- `tests/test_property_lifecycle.py`
- New: `tests/test_langgraph_upgrade.py`

### Dependencies
- Task 1-8

---

## Task 10: Documentation and Cleanup

### Description
Update documentation, remove deprecated code, and ensure backward compatibility.

### Requirements Addressed
- Requirement 11: Extensibility for Future Stages

### Acceptance Criteria
- [ ] LANGGRAPH_GUIDE.md updated with new patterns
- [ ] Deprecated SupabaseCheckpointer code removed or marked
- [ ] Migration guide for existing checkpoints
- [ ] README updated with new features

### Files to Modify
- `docs/LANGGRAPH_GUIDE.md`
- `README.md`
- `src/graph/checkpointer.py`

### Dependencies
- Task 1-9
