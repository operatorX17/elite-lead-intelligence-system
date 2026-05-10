# Requirements Document: LangGraph Professional Upgrade

## Introduction

This spec covers upgrading the ZRAI Lead OS LangGraph orchestrator to use the latest professional-grade patterns and features. The goal is to make the system rock-solid, production-ready, and easily extensible for future stages/steps. This includes implementing proper checkpointing, streaming, parallel execution, human-in-the-loop patterns, and comprehensive error handling.

## Glossary

- **Graph_Orchestrator**: The LangGraph-based state machine runtime managing multi-agent workflow execution
- **StateGraph**: LangGraph's core graph builder for defining nodes and edges
- **Checkpointer**: Persistence layer for saving/restoring graph state (enables resume-anywhere)
- **Command**: LangGraph primitive combining state updates with routing decisions
- **Send**: LangGraph primitive for fan-out parallel processing
- **Interrupt**: LangGraph mechanism for human-in-the-loop approval flows
- **Subgraph**: Nested graph for modular agent composition
- **Reducer**: Function for aggregating parallel branch results
- **RetryPolicy**: Configuration for automatic retry with backoff on failures
- **StreamMode**: Configuration for real-time streaming of graph execution events

## Requirements

### Requirement 1: Fix Syntax Errors and Core Graph Structure

**User Story:** As a developer, I want the orchestrator to compile without errors, so that the system can execute lead processing workflows.

#### Acceptance Criteria

1. WHEN the orchestrator module is imported, THE Graph_Orchestrator SHALL compile without syntax errors
2. WHEN the graph is built, THE Graph_Orchestrator SHALL define all nodes with proper type annotations
3. WHEN the graph is compiled, THE Graph_Orchestrator SHALL validate all edges and conditional routing

### Requirement 2: Modern State Management with TypedDict

**User Story:** As a developer, I want state management using TypedDict patterns, so that the graph has proper type safety and IDE support.

#### Acceptance Criteria

1. WHEN defining graph state, THE Graph_Orchestrator SHALL use TypedDict or Pydantic models with proper annotations
2. WHEN state is updated, THE Graph_Orchestrator SHALL use Annotated types with reducers for list aggregation
3. WHEN state flows between nodes, THE Graph_Orchestrator SHALL preserve type safety throughout the pipeline

### Requirement 3: Proper Checkpointing with SqliteSaver/MemorySaver

**User Story:** As a system operator, I want reliable checkpointing, so that failed executions can resume from the last successful state.

#### Acceptance Criteria

1. WHEN the Graph_Orchestrator initializes, THE Lead_OS SHALL configure a checkpointer (SqliteSaver for production, MemorySaver for testing)
2. WHEN a node completes execution, THE Checkpointer SHALL persist the current state automatically
3. WHEN resuming a failed execution, THE Graph_Orchestrator SHALL restore state from the last checkpoint
4. WHEN using thread_id configuration, THE Checkpointer SHALL isolate state per lead execution

### Requirement 4: Command-Based Routing

**User Story:** As a developer, I want combined state updates and routing using Commands, so that the graph logic is cleaner and more maintainable.

#### Acceptance Criteria

1. WHEN a node needs to update state AND route, THE Graph_Orchestrator SHALL use Command objects
2. WHEN the Scoring_Agent assigns tier C, THE Graph_Orchestrator SHALL return a Command routing to end node
3. WHEN the Intent_Agent detects high leak_score, THE Graph_Orchestrator SHALL return a Command routing to audit node
4. WHEN using Commands, THE Graph_Orchestrator SHALL eliminate separate conditional edge functions where possible

### Requirement 5: Parallel Lead Processing with Send

**User Story:** As a system operator, I want discovered leads processed in parallel, so that pipeline throughput is maximized.

#### Acceptance Criteria

1. WHEN the Discovery_Agent returns multiple leads, THE Graph_Orchestrator SHALL use Send primitives for fan-out
2. WHEN parallel branches complete, THE Graph_Orchestrator SHALL use reducers to aggregate results
3. WHEN configuring parallelism, THE Lead_OS SHALL respect max_parallel_leads configuration
4. WHEN a parallel branch fails, THE Graph_Orchestrator SHALL isolate the failure and continue other branches

### Requirement 6: Human-in-the-Loop with Interrupt

**User Story:** As a sales operator, I want approval workflows for outreach messages, so that I can review before sending.

#### Acceptance Criteria

1. WHEN outreach requires approval, THE Graph_Orchestrator SHALL use interrupt_before to pause execution
2. WHEN a human approves, THE Graph_Orchestrator SHALL resume from the interrupt point
3. WHEN a human rejects, THE Graph_Orchestrator SHALL route to an alternative path or end
4. WHEN escalation is triggered, THE Graph_Orchestrator SHALL interrupt for human handoff

### Requirement 7: Streaming Support

**User Story:** As a frontend developer, I want real-time updates during lead processing, so that users can see progress.

#### Acceptance Criteria

1. WHEN processing a lead, THE Graph_Orchestrator SHALL support streaming mode for real-time events
2. WHEN a node starts/completes, THE Graph_Orchestrator SHALL emit stream events with node name and timing
3. WHEN state is updated, THE Graph_Orchestrator SHALL emit stream events with state changes
4. WHEN errors occur, THE Graph_Orchestrator SHALL emit stream events with error details

### Requirement 8: Retry Policies for External Services

**User Story:** As a system operator, I want automatic retries with backoff for external API calls, so that transient failures don't cause pipeline failures.

#### Acceptance Criteria

1. WHEN an external API call fails, THE Graph_Orchestrator SHALL retry with exponential backoff
2. WHEN configuring retries, THE Lead_OS SHALL support per-service retry policies (Apify, Steel, LLM)
3. WHEN max retries are exceeded, THE Graph_Orchestrator SHALL activate circuit breaker and route around
4. WHEN retrying, THE Graph_Orchestrator SHALL log retry attempts with delay information

### Requirement 9: Subgraph Composition

**User Story:** As a developer, I want modular agent composition using subgraphs, so that complex agents can be developed and tested independently.

#### Acceptance Criteria

1. WHEN an agent has complex internal logic, THE Graph_Orchestrator SHALL support subgraph composition
2. WHEN a subgraph completes, THE Graph_Orchestrator SHALL merge subgraph state back to parent state
3. WHEN testing agents, THE Lead_OS SHALL support running subgraphs in isolation

### Requirement 10: Graph Visualization and Debugging

**User Story:** As a developer, I want to visualize the graph structure, so that I can understand and debug the workflow.

#### Acceptance Criteria

1. WHEN requested, THE Graph_Orchestrator SHALL generate a Mermaid diagram of the graph structure
2. WHEN debugging, THE Graph_Orchestrator SHALL provide execution trace with node timings
3. WHEN errors occur, THE Graph_Orchestrator SHALL provide clear error context with node and state info

### Requirement 11: Extensibility for Future Stages

**User Story:** As a system architect, I want the graph to be easily extensible, so that new stages can be added without major refactoring.

#### Acceptance Criteria

1. WHEN adding a new node, THE Graph_Orchestrator SHALL support dynamic node registration
2. WHEN adding new conditional routing, THE Graph_Orchestrator SHALL support pluggable routing functions
3. WHEN extending state, THE Graph_Orchestrator SHALL support backward-compatible state schema evolution

