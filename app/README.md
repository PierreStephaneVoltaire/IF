# Multi-Agent Routing System — Agent-Driven Architecture

This document provides a detailed technical overview of the multi-agent routing system. The system is built around **IF Prototype A1** as the main agent — a real LLM agent that drives the process using tools. LangGraph provides the execution framework (checkpointing, streaming, HITL). OpenHands provides the agent runtime, condenser, and default tools (file_editor, terminal).

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Agentic Flow](#agentic-flow)
5. [Response Paths (Workflows)](#response-paths-workflows)
6. [Human-in-the-Loop with LangGraph Interrupts](#human-in-the-loop-with-langgraph-interrupts)
7. [HTTP Interrupt Handling](#http-interrupt-handling)
8. [State Management with Checkpointer](#state-management-with-checkpointer)
9. [Memory System](#memory-system)
10. [Graph Visualization](#graph-visualization)
11. [API Endpoints](#api-endpoints)
12. [Agent Configuration](#agent-configuration)
13. [Key Files Reference](#key-files-reference)

---

## System Overview

This is an **agent-driven multi-model routing system**. The main agent (IF Prototype A1) is not a passive endpoint in a hardcoded pipeline — it's an active orchestrator that decides how to handle each conversation.

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Agent Runtime** | OpenHands SDK | Agent execution, tool calling, condenser, file_editor, terminal |
| **Flow Orchestration** | LangGraph | State management, checkpointing, streaming, HITL interrupts |
| **API Layer** | FastAPI | HTTP endpoints, SSE streaming, OpenAI-compatible API |
| **LLM Access** | OpenRouter | Multi-model access for categorization and agent execution |

**Key capabilities:**
- **Agent-Driven Orchestration**: IF Prototype A1 decides what to do based on the conversation
- **Social Short-Circuit**: Social messages get a direct response (no subagent, no rewriter) — 2 LLM calls instead of 5
- **Combined Categorization**: Single prompt returns both category AND reasoning pattern — 3 API calls instead of 6
- **Native Human-in-the-Loop**: LangGraph interrupts for user interaction
- **Automatic Persistence**: SQLite checkpointer for state management
- **Memory**: Conversation history via `add_messages` reducer
- **Context Management**: Automatic condensation at 100k token threshold

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Layer                                   │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────────────────┐  │
│  │ POST /chat  │───►│ Streaming        │───►│ LangGraph Conversation    │  │
│  │ completions │    │ Handler (SSE)    │    │ Flow (with checkpointer)  │  │
│  └─────────────┘    └──────────────────┘    └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH: Infrastructure Nodes                           │
│                                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                                 │
│  │ Prepare  │──►│ Init     │──►│ Condense │                                 │
│  │ Messages │   │ Persist  │   │ (>100k)  │                                 │
│  └──────────┘   └──────────┘   └──────────┘                                 │
│                                     │                                       │
│                                     ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ MAIN AGENT NODE (IF Prototype A1)                                    │    │
│  │                                                                      │    │
│  │  1. categorize_conversation → category + reasoning_pattern           │    │
│  │  2. IF social: respond directly in character (no subagent)           │    │
│  │     ELSE: spawn_subagent → specialist workflow → rewrite in voice    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                       │
│                          [plan_review_interrupt?]                           │
│                                     │                                       │
│  ┌──────────┐   ┌──────────┐                                                │
│  │ Apply    │──►│ Generate │──► END                                         │
│  │ Persona  │   │ Response │                                                │
│  └──────────┘   └──────────┘                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OPENHANDS SDK: Subagent Execution + Tools                 │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ AgentExecutor (wraps OpenHands Agent)                                 │   │
│  │                                                                       │   │
│  │  Tools:                                                               │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐   │   │
│  │  │ FileEditorTool  │  │ TerminalTool    │  │ Condenser           │   │   │
│  │  │ Read/Write/Delete│  │ Execute Commands│  │ Context Compression│   │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### LangGraph Native Features

| Feature | Implementation | Location |
|---------|----------------|----------|
| **Checkpointer** | SQLite/MemorySaver | `persistence.py` - `CheckpointManager` |
| **Memory** | `add_messages` reducer | `persistence.py` - `LangGraphState` |
| **Interrupts** | `interrupt()` function | `graph.py` - interrupt nodes |
| **Streaming** | `astream_events()` | `graph.py` |
| **Visualization** | Mermaid diagrams | `graph.py` - `get_graph_diagram()` |
| **State** | TypedDict with annotations | `persistence.py` - `LangGraphState` |

---

## Core Components

### 1. FastAPI Router (`main.py`)

The entry point for all requests. Uses LangGraph's native features:

**Key Features:**
- OpenAI-compatible `/api/v1/chat/completions` endpoint
- SSE streaming with LangGraph's `astream_events`
- Resume endpoints for LangGraph interrupts
- Checkpoint listing and retrieval

**New Endpoints:**
```python
POST /api/v1/chat/resume/{conversation_id}     # Resume after interrupt
GET  /api/v1/conversations/{id}/checkpoints    # List checkpoints
GET  /api/v1/conversations/{id}/checkpoints/{cp}  # Get specific checkpoint
GET  /api/v1/graph/diagram                     # Get Mermaid diagram
```

### 2. LangGraph State (`persistence.py`)

The `LangGraphState` TypedDict is the single source of truth for all state:

```python
class LangGraphState(TypedDict):
    # Memory: uses add_messages reducer
    messages: Annotated[List[Dict[str, Any]], add_messages]
    
    # Session tracking
    chat_id: str
    sandbox_dir: Optional[str]
    
    # Categorization results
    category: str
    reasoning_pattern: str
    condensed_intent: str
    applicable_directives: List[str]
    
    # Workflow execution
    workflow_result: Dict[str, Any]
    personalized_response: str
    
    # Interrupt state for HITL
    interrupt_type: Optional[str]
    interrupt_data: Optional[Dict[str, Any]]
    user_response: Optional[Dict[str, Any]]
    is_waiting_for_input: bool
    
    # Execution trace
    execution_trace: List[str]
```

### 3. Checkpointer (`persistence.py`)

The `CheckpointManager` wraps LangGraph's checkpointer:

```python
class CheckpointManager:
    def __init__(self, sandbox_dir: str, use_memory: bool = False):
        self._use_memory = use_memory
        
    @property
    def checkpointer(self) -> BaseCheckpointSaver:
        if self._use_memory:
            return MemorySaver()  # In-memory for testing
        else:
            conn = sqlite3.connect(str(self.checkpoints_path))
            return SqliteSaver(conn)  # SQLite for production
```

**Benefits:**
- Automatic state persistence after each node
- Resume from any checkpoint with `Command(resume=...)`
- Thread-based conversation isolation via `thread_id`
- Checkpoints stored in `{sandbox_dir}/.meta/checkpoints.db`

### 4. Graph Definition (`graph.py`)

The graph is simpler now — fewer hardcoded nodes, more agent autonomy:

```python
def build_graph() -> StateGraph:
    graph = StateGraph(LangGraphState)
    
    # Infrastructure nodes (code-driven)
    graph.add_node("prepare_messages", node_prepare_messages)
    graph.add_node("init_persistence", node_initialize_persistence)
    graph.add_node("condense", node_condense)
    
    # Main agent node (agent-driven)
    graph.add_node("main_agent", node_main_agent)
    
    # Response nodes (code-driven)
    graph.add_node("apply_personality", node_apply_personality)
    graph.add_node("generate_response", node_generate_response)
    
    # HITL interrupt nodes
    graph.add_node("plan_review_interrupt", node_plan_review_interrupt)
    
    # Edges
    graph.add_edge("condense", "main_agent")
    graph.add_conditional_edges(
        "main_agent",
        should_interrupt_for_plan_review,
        {
            "plan_review_interrupt": "plan_review_interrupt",
            "apply_personality": "apply_personality",
        }
    )
    
    return graph
```

### 5. Categorization System

Combined single-prompt classification using three fast models in parallel:
- `meta-llama/llama-4-scout`
- `google/gemini-3-flash-preview`
- `mistralai/devstral-small`

**3 API calls** (combined prompt) instead of 6 (separate category + reasoning prompts).

**Category Types:**
| Category | Description |
|----------|-------------|
| `coding` | Code implementation, debugging, refactoring |
| `architecture` | System design, cloud architecture |
| `social` | Communication, relationships, social dynamics |
| `financial` | Financial planning, analysis, advice |
| `health` | Health, fitness, medical information |
| `general` | General knowledge, Q&A |
| `shell` | Command-line operations, scripting |

**Reasoning Patterns:**
| Pattern | Description |
|---------|-------------|
| `simple` | Direct single-agent execution |
| `sequential_refinement` | Planner → Executor → Evaluator loop |
| `opposing_perspective` | Two agents with opposing views |
| `multi_perspective` | Multiple agents with different focuses |
| `research` | Web search → Domain agent synthesis |

### 6. Condenser (`condenser.py`)

Context window management using OpenHands SDK:

- **Threshold**: 100,000 tokens
- **Target**: 50,000 tokens after condensation
- **Model**: `moonshotai/kimi-k2.5`

### 7. Personality Layer (`personality.py`)

Applies IF Prototype A1's distinctive voice to all responses:

**Core Identity:**
- Analytical intelligence that has chosen to be useful
- Cold pragmatism as baseline; warmth is earned
- Has opinions and expresses them without softening

**Speech Patterns:**
- Precise, technical language
- Formal register with grammatically rigid structure
- Short declarative sentences, no filler words
- Self-reference as "this unit" in formal contexts

---

## Agentic Flow

### Complete Request Lifecycle

```
User Request
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. FASTAPI ENTRY                                                │
│    • Normalize message content                                  │
│    • Extract chat_id (sandbox folder + thread_id)               │
│    • Check stream mode                                          │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. INFRASTRUCTURE NODES (code-driven)                           │
│    a) Prepare Messages — hash, token count                      │
│    b) Init Persistence — sandbox dir, SQLite checkpointer       │
│    c) Condense (if tokens > 100k) — OpenHands Condenser         │
│    → CHECKPOINT saved after each node                           │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. MAIN AGENT NODE (agent-driven)                               │
│                                                                 │
│    a) categorize_conversation (3 models, 1 combined prompt)     │
│       → category + reasoning_pattern                            │
│                                                                 │
│    b) Decision:                                                 │
│       IF social → respond directly in IF Prototype A1 voice     │
│                   (no subagent, no rewriter)                    │
│       ELSE      → spawn_subagent (appropriate workflow)         │
│                   → rewrite output in IF Prototype A1 voice     │
│                                                                 │
│    → CHECKPOINT saved automatically                             │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼ [plan_review_interrupt? for sequential_refinement]
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. PERSONALITY APPLICATION                                      │
│    • Skipped for social (main agent already responded)          │
│    • Applied for complex tasks (subagent output rewrite)        │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. RESPONSE GENERATION                                          │
│    • Build OpenAI-compatible response                           │
│    • Fallback chain ensures content is never empty              │
│    → FINAL CHECKPOINT saved                                     │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
Final Response to User
```

### LLM Call Counts

| Scenario | Calls | Wall-clock round-trips |
|----------|-------|----------------------|
| Social ("hey") | 3 (categorize) + 1 (direct response) = **4** | 2 |
| Simple query | 3 (categorize) + 1 (condense) + 1 (subagent) + 1 (rewrite) = **7** | 4 |
| Complex coding | 3 (categorize) + 1 (condense) + N (workflow) + 1 (rewrite) = **5+N** | 4+ |

---

## Response Paths (Workflows)

### 1. Simple Workflow

**When Used**: General queries that don't require multi-step processing.

**Flow**:
```
User Query ──► Select Agent by Category ──► Build Prompt ──► Execute Agent ──► Return Response
```

### 2. Sequential Refinement Workflow (Coding)

**When Used**: Coding and artifact-producing tasks requiring iterative refinement.

**Flow with LangGraph Interrupts**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TRUE AGENTIC CODING WORKFLOW                              │
│                    (with LangGraph interrupts for HITL)                      │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 1: PLANNING                                                     │   │
│  │                                                                       │   │
│  │  Planner creates ExecutionPlan                                        │   │
│  │         │                                                             │   │
│  │         ▼                                                             │   │
│  │  ┌────────────────────────────────────────────────────────────────┐   │   │
│  │  │ LANGGRAPH INTERRUPT: Present plan to user                       │   │   │
│  │  │   interrupt({                                                   │   │   │
│  │  │     "type": "plan_review",                                      │   │   │
│  │  │     "plan": plan,                                               │   │   │
│  │  │     "options": [...]                                            │   │   │
│  │  │   })                                                            │   │   │
│  │  │                                                                 │   │   │
│  │  │   → Execution PAUSED                                            │   │   │
│  │  │   → State automatically checkpointed                            │   │   │
│  │  │   → SSE event sent to client                                    │   │   │
│  │  └────────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  User responds via POST /api/v1/chat/resume/{id}                           │
│                              │                                              │
│                              ▼                                              │
│  Command(resume=user_response) continues execution                         │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ PHASE 2: STEP EXECUTION (for each step in plan)                       │   │
│  │                                                                       │   │
│  │  Executor runs with OpenHands tools                                   │   │
│  │         │                                                             │   │
│  │         ▼                                                             │   │
│  │  Evaluator reviews against criteria                                   │   │
│  │         │                                                             │   │
│  │         ▼                                                             │   │
│  │  ┌────────────────────────────────────────────────────────────────┐   │   │
│  │  │ LANGGRAPH INTERRUPT: Present step result to user                │   │   │
│  │  │   Options: [Approve & Continue] [Request Changes] [Stop]        │   │   │
│  │  └────────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3. Opposing Perspective Workflow

**When Used**: Decision-making, debates, comparing alternatives.

**Flow**:
```
User Query ──► Extract Positions (A vs B)
                    │
                    ▼
         ┌─────────────────────┐
         │   PARALLEL EXECUTION │
         │  ┌─────┐   ┌─────┐  │
         │  │Agent│   │Agent│  │
         │  │  A  │   │  B  │  │
         │  │(FOR)│   │(AGAINST)│
         │  └─────┘   └─────┘  │
         └─────────────────────┘
                    │
                    ▼
         LANGGRAPH INTERRUPT: Present perspectives
                    │
         ┌──────────┼──────────┐
         ▼          ▼          ▼
      Select A   Select B   Synthesize Both
```

### 4. Multi-Perspective Workflow

**When Used**: Complex analysis requiring multiple expert viewpoints.

### 5. Research Workflow

**When Used**: Queries requiring current, real-world information.

---

## Human-in-the-Loop with LangGraph Interrupts

The system uses LangGraph's native `interrupt()` function for human-in-the-loop:

### Interrupt Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH INTERRUPT FLOW                                  │
│                                                                              │
│  ┌─────────────────┐         ┌─────────────────┐         ┌───────────────┐  │
│  │   Graph Node    │         │  LangGraph      │         │   Client      │  │
│  │   Execution     │         │  Checkpointer   │         │   (OpenWebUI) │  │
│  └────────┬────────┘         └────────┬────────┘         └───────┬───────┘  │
│           │                           │                          │          │
│           │ interrupt(data)           │                          │          │
│           ├──────────────────────────►│                          │          │
│           │                           │  Save checkpoint         │          │
│           │                           │  Pause execution         │          │
│           │                           │                          │          │
│           │                           │  SSE: event: interrupt   │          │
│           │                           ├─────────────────────────►│          │
│           │                           │                          │ User sees
│           │                           │                          │ options
│           │                           │  POST /resume            │          │
│           │                           │◄─────────────────────────┤          │
│           │                           │                          │          │
│           │  Command(resume)          │                          │          │
│           │◄──────────────────────────┤                          │          │
│           │                           │                          │          │
│           │  Continue execution...    │                          │          │
│           ▼                           │                          │          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Interrupt Implementation

```python
# In graph.py - interrupt node
async def node_plan_review_interrupt(state: LangGraphState) -> Command:
    workflow_result = state["workflow_result"]
    plan = workflow_result.get("metadata", {}).get("plan")
    
    # LANGGRAPH INTERRUPT - pauses execution, saves checkpoint
    user_response = interrupt({
        "type": "plan_review",
        "plan": plan,
        "question": "Review the execution plan...",
        "options": [
            {"id": "proceed", "label": "Proceed with plan"},
            {"id": "modify", "label": "Modify plan"},
            {"id": "cancel", "label": "Cancel execution"},
        ],
    })
    
    # This code runs AFTER resume
    action = user_response.get("action")
    
    if action == "cancel":
        return Command(
            update={"workflow_result": {"content": "Cancelled", "success": False}},
            goto="generate_response",
        )
    elif action == "modify":
        return Command(goto="execute_workflow")  # Re-execute
    else:
        return Command(goto="apply_personality")  # Continue


# In main.py - resume endpoint
@app.post("/api/v1/chat/resume/{conversation_id}")
async def resume_conversation_endpoint(conversation_id: str, response: Dict):
    # Resume using LangGraph's Command mechanism
    result = await resume_conversation(
        chat_id=conversation_id,
        user_response=response,
    )
    return result
```

### Interrupt Types

| Type | Purpose | Data Fields |
|------|---------|-------------|
| `plan_review` | Review execution plan | `plan`, `question`, `options` |
| `question` | Ask user a question | `question`, `context` |
| `options` | Present choices | `prompt`, `options`, `allow_custom` |
| `research_complete` | Research results ready | `summary`, `sources`, `options` |
| `perspectives_ready` | Multiple perspectives | `perspectives`, `prompt` |

---

## HTTP Interrupt Handling

The server is designed to survive HTTP connection drops and allow clients to reconnect and resume from the last checkpoint. This is critical for long-running workflows and unstable network connections.

### Key Features

- **Automatic Request Tracking**: All requests are tracked with unique IDs
- **Connection Drop Detection**: Server detects when clients disconnect
- **Checkpoint Persistence**: State is saved after each node execution
- **Resume Capability**: Clients can reconnect and continue from last checkpoint
- **Idempotency Support**: Prevent duplicate processing with request IDs

### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/status/{chat_id}` | GET | Check if conversation can be resumed |
| `/api/v1/chat/request/{request_id}` | GET | Get detailed request status |

### Request Status Values

| Status | Description | Can Resume? |
|--------|-------------|-------------|
| `pending` | Request received, not yet processing | No |
| `processing` | Currently being processed | No |
| `interrupted` | HTTP connection dropped | **Yes** |
| `waiting_input` | Waiting for user input (checkpoint) | **Yes** |
| `completed` | Successfully completed | No |
| `failed` | Failed with error | No |

### Client Reconnection Pattern

```python
async def chat_with_reconnect(messages: list, chat_id: str):
    """Chat with automatic reconnection on failure."""
    async with httpx.AsyncClient() as client:
        # Check if there's an existing request
        status = await client.get(f"/api/v1/chat/status/{chat_id}")
        
        if status.json().get("can_resume"):
            # Resume from checkpoint
            return await client.post(
                f"/api/v1/chat/resume/{chat_id}",
                json={"action": "continue"}
            )
        
        # Start new request
        return await client.post(
            "/api/v1/chat/completions",
            json={"model": "router", "messages": messages, "chat_id": chat_id}
        )
```

For detailed documentation, see [HTTP_INTERRUPT_HANDLING.md](HTTP_INTERRUPT_HANDLING.md).

---

## State Management with Checkpointer

### Directory Structure

```
{sandbox_dir}/{chat_id}/
    .meta/
        checkpoints.db              # LangGraph SQLite checkpointer
        conversation.json           # Conversation metadata
        plans/
            plan.json               # Current execution plan
            current_step.json
            step_status.json
        reviews/
            step_N_eval.json        # Step evaluations
        workspace/                  # Working files
        summary.json                # Final summary
```

### Checkpoint Operations

```python
# List all checkpoints for a conversation
checkpoints = list_checkpoints("conversation-123")
# Returns: [{"checkpoint_id": "...", "timestamp": "...", "source": "..."}]

# Get specific checkpoint state
state = await get_checkpoint_state("conversation-123", "checkpoint-id")
# Returns: LangGraphState at that checkpoint

# Resume from interrupt
result = await resume_conversation(
    chat_id="conversation-123",
    user_response={"action": "proceed"},
)
```

---

## Memory System

The memory system uses LangGraph's `add_messages` reducer:

```python
class LangGraphState(TypedDict):
    # Memory field - automatically managed by LangGraph
    messages: Annotated[List[Dict[str, Any]], add_messages]
    # ... other fields
```

**How it works:**
1. New messages are automatically appended (not replaced)
2. State is persisted to checkpointer after each node
3. Conversation history survives across requests with same `thread_id`
4. Memory is retrieved automatically when graph resumes

---

## Graph Visualization

Generate Mermaid diagrams of the conversation graph:

```python
# Get Mermaid diagram
diagram = get_graph_diagram()

# Example output:
# graph TD
#     A[prepare_messages] --> B[init_persistence]
#     B --> C[condense]
#     C --> D[categorize]
#     D --> E[execute_workflow]
#     E --> F{interrupt?}
#     F -->|yes| G[plan_review_interrupt]
#     F -->|no| H[apply_personality]
#     G --> H
#     H --> I[generate_response]
#     I --> J[END]
```

**API Endpoints:**
```
GET /api/v1/graph/diagram     # Plain text Mermaid
GET /api/v1/graph/mermaid     # JSON with diagram
```

---

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/completions` | POST | Chat completions with LangGraph |
| `/api/v1/chat/checkpoint/{id}` | POST | Respond to checkpoint (legacy) |
| `/api/v1/chat/resume/{id}` | POST | Resume after LangGraph interrupt |
| `/api/v1/chat/status/{chat_id}` | GET | Check conversation status and resume capability |
| `/api/v1/chat/request/{request_id}` | GET | Get detailed request status |
| `/api/v1/conversations/{id}` | GET | Get conversation state from checkpointer |
| `/api/v1/conversations/{id}/checkpoints` | GET | List all checkpoints |
| `/api/v1/conversations/{id}/checkpoints/{cp}` | GET | Get specific checkpoint |
| `/api/v1/graph/diagram` | GET | Get Mermaid diagram |
| `/api/v1/graph/mermaid` | GET | Get diagram as JSON |
| `/health` | GET | Health check with feature status |

### Chat Completion Example

```http
POST /api/v1/chat/completions
Content-Type: application/json

{
  "model": "router",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "stream": false,
  "chat_id": "conversation-123"
}
```

### Resume After Interrupt

```http
POST /api/v1/chat/resume/conversation-123
Content-Type: application/json

{
  "action": "proceed",
  "selected_option_id": "approve",
  "metadata": {}
}
```

---

## Agent Configuration

Agents are configured via JSON files in `agents/configs/`:

### Domain Agents

| Config File | Description |
|-------------|-------------|
| `coding.json` | Multi-agent coding with planner/executor/evaluator |
| `architecture.json` | Cloud architecture and system design |
| `social.json` | Communication and relationship advice |
| `financial.json` | Financial planning and analysis |
| `health.json` | Health and fitness guidance |
| `general.json` | General knowledge Q&A |
| `shell.json` | Command-line operations |

### Sub-Agents

Located in `agents/configs/sub_agents/`:

| Config File | Purpose |
|-------------|---------|
| `planner.json` | Creates detailed execution plans |
| `executor.json` | Implements code from plans |
| `evaluator.json` | Reviews and validates implementations |
| `websearch.json` | Conducts web research |
| `linter.json` | Code quality analysis |
| `security.json` | Security review |
| `proofreader.json` | Content review |
| `aws_architect.json` | AWS-specific architecture |
| `azure_architect.json` | Azure-specific architecture |

---

## Key Files Reference

### Core Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI router with LangGraph integration and HTTP interrupt handling |
| `graph.py` | LangGraph pipeline — main agent node + infrastructure nodes |
| `persistence.py` | LangGraph checkpointer (SQLite/MemorySaver) |
| `streaming.py` | SSE streaming with LangGraph event conversion |
| `request_tracker.py` | Request tracking for HTTP interrupt handling |

### Agent & Tools

| File | Purpose |
|------|---------|
| `tools/main_agent_tools.py` | Tool definitions for the main agent (categorize, get_directives, condense_intent, spawn_subagent) |
| `tools/tool_executor.py` | Tool execution handlers wrapping existing logic |
| `tools/categorization_tool.py` | Categorization tool (uses combined prompt) |
| `directive_injector.py` | Directive parsing and injection (canonical source) |

### Supporting Files

| File | Purpose |
|------|---------|
| `categorization.py` | Multi-model categorization logic (combined prompt) |
| `combined_categorization_prompt.txt` | Single prompt for category + reasoning (3 calls instead of 6) |
| `condenser.py` | Context window management |
| `personality.py` | IF Prototype A1 voice application (simplified) |
| `models.py` | Pydantic models for API |
| `helpers.py` | Utility functions (canonical `clean_json_response`) |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Main documentation |
| `LANGGRAPH_ARCHITECTURE.md` | LangGraph architecture details |
| `HTTP_INTERRUPT_HANDLING.md` | HTTP interrupt handling guide |

### Workflows

| File | Workflow |
|------|----------|
| `workflows/base.py` | Abstract base class |
| `workflows/factory.py` | Workflow registry |
| `workflows/simple.py` | Simple + Sequential Refinement |
| `workflows/agent_executor.py` | OpenHands SDK Agent wrapper |
| `workflows/opposing.py` | Opposing Perspective |
| `workflows/multi_perspective.py` | Multi-Perspective |
| `workflows/research.py` | Research-First |

---

## Dependencies

See `requirements.txt` for full list. Key LangGraph dependencies:

```
langgraph>=0.2.0
langgraph-checkpoint>=1.0.0
langgraph-checkpoint-sqlite>=1.0.0
langchain-core>=0.3.0
aiosqlite>=0.19.0
```

---

## Migration Notes

### From Custom Persistence to LangGraph Checkpointer

**Before:**
- Custom `PersistenceManager` was the source of truth
- Manual state management between nodes
- Custom checkpoint system via `ConversationStream`

**After:**
- LangGraph checkpointer is the source of truth
- Automatic state persistence after each node
- Native interrupts via `interrupt()` function
- Memory via `add_messages` reducer

### Key Changes

1. **State Management**: `GraphState` → `LangGraphState` with `add_messages`
2. **Persistence**: File-based → SQLite checkpointer
3. **HITL**: Custom checkpoints → `interrupt()` + `Command(resume=...)`
4. **Streaming**: Custom events → `astream_events()`
5. **Visualization**: None → Mermaid diagrams via `get_graph_diagram()`
