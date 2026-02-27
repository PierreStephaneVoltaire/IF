# IF Prototype A1 — Agent API

OpenAI-compatible API server in Python exposing a single custom model (`if-prototype`) backed by a routing layer. Incoming chat completions are analyzed, scored against dynamically loaded OpenRouter presets, and dispatched to the best-fit preset model. The agent runs on the OpenHands SDK with access to MCP servers, a persistent RAG-backed memory store, human-in-the-loop interaction, conversation persistence, and a file-based attachment system.

The API is designed as a platform-agnostic backend. Platform-specific adapters (Discord, OpenWebUI, etc.) connect to it via the standard OpenAI chat completions interface.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  Client (OpenWebUI / Discord / etc.)             │
└──────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OpenAI-Compatible API (FastAPI)               │
│                                                                 │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │  /v1/models  │   │  /v1/chat/   │   │  Attachment Serving │  │
│  │             │   │  completions │   │  /files/sandbox/*   │  │
│  └─────────────┘   └──────┬───────┘   └─────────────────────┘  │
│                           │                                     │
│            ┌──────────────┴──────────────┐                      │
│            │     Request Interceptor      │                     │
│            │  (OpenWebUI suggestion check)│                     │
│            └──────────┬──────────┬───────┘                      │
│              suggestion│          │ normal                       │
│                   ▼    │          ▼                              │
│  ┌────────────────┐   │   ┌──────────────────┐                 │
│  │  Mistral Nemo  │   │   │ Context Condenser │                 │
│  │  (quick reply) │   │   │  (if > 250k tok)  │                 │
│  └────────────────┘   │   └────────┬─────────┘                 │
│                       │            ▼                            │
│                       │   ┌─────────────────┐                  │
│                       │   │ Routing Pipeline │                  │
│                       │   │  ┌───────────┐  │                  │
│                       │   │  │ Scorer(s)  │  │                  │
│                       │   │  │ (parallel) │  │                  │
│                       │   │  └─────┬─────┘  │                  │
│                       │   │        ▼        │                  │
│                       │   │  ┌───────────┐  │                  │
│                       │   │  │ Decision   │  │                  │
│                       │   │  │ Logic      │  │                  │
│                       │   │  └─────┬─────┘  │                  │
│                       │   │        ▼        │                  │
│                       │   │  ┌───────────┐  │                  │
│                       │   │  │ State      │  │                  │
│                       │   │  │ Cache      │  │                  │
│                       │   │  └─────┬─────┘  │                  │
│                       │   └────────┼────────┘                  │
│                       │            │                            │
│                       │            ▼ selected preset            │
│                       │   ┌──────────────────────────┐         │
│                       │   │    OpenHands Agent        │         │
│                       │   │    (Persistent Session)   │         │
│                       │   │                          │         │
│                       │   │  ┌────────┐ ┌─────────┐ │         │
│                       │   │  │  MCP   │ │ Memory  │ │         │
│                       │   │  │ Servers│ │  (RAG)  │ │         │
│                       │   │  └────────┘ └─────────┘ │         │
│                       │   │  ┌────────┐ ┌─────────┐ │         │
│                       │   │  │Sandbox │ │ Human   │ │         │
│                       │   │  │ (files)│ │ in Loop │ │         │
│                       │   │  └────────┘ └─────────┘ │         │
│                       │   └───────────┬──────────────┘         │
│                       │               │                        │
│                       ▼               ▼                        │
│               ┌─────────────────────────┐                      │
│               │   Response Assembler     │                      │
│               │  (text + attachments)    │                      │
│               └─────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                          OpenRouter API
                     (@preset/{name} routing)
```

---

## API Specification

### GET /v1/models

Returns the model list with a single entry.

```json
{
  "object": "list",
  "data": [
    {
      "id": "if-prototype",
      "object": "model",
      "created": 1700000000,
      "owned_by": "if-prototype"
    }
  ]
}
```

### POST /v1/chat/completions

Standard OpenAI chat completions interface. Accepts `model: "if-prototype"` (any other model value is rejected).

Request body follows the OpenAI chat completions schema: `messages`, `stream`, `temperature`, etc. All parameters are forwarded to the downstream preset model after routing.

Response follows the OpenAI chat completions schema. When the agent produces file artifacts (code files, diagrams), they are returned as attachments in the response.

Streaming is supported. When `stream: true`, the response is an SSE stream of `chat.completion.chunk` objects. Attachments are delivered as a final non-streamed payload after the stream completes, or as tool-call artifacts within the stream depending on client capabilities.

Concurrent messages are supported for non-blocking clients. While an agent session is running, additional messages can be sent to the same conversation. These are delivered to the running agent via OpenHands' send-message-while-running capability. OpenWebUI is sequential and blocking, but other clients (Discord adapter, custom frontends) can take advantage of this.

---

## Startup & Configuration

### Preset Loading

On server startup:

1. Call the OpenRouter API to fetch all presets associated with the configured API key.
2. Build an in-memory map:

```python
presets = {
    "preset-slug-1": {
        "name": "preset-slug-1",
        "description": "Description from OpenRouter preset config...",
        "model": "@preset/preset-slug-1"
    },
    # ... one entry per preset
}
```

3. Validate that at least one preset loaded successfully. Fail startup if zero presets are available.
4. Log the loaded preset names and their descriptions for debugging.

The preset descriptions are the source of truth for the routing pipeline. The scoring models use them to determine which preset fits a conversation. Preset descriptions on OpenRouter must be written to clearly differentiate their domains. The quality of routing is directly proportional to the quality of these descriptions. The scoring prompt injects these descriptions dynamically, so adding, removing, or modifying presets on OpenRouter automatically updates routing behavior on the next server restart with zero code changes.

---

## Context Condensation

When the total token count of the incoming conversation exceeds `CONTEXT_CONDENSE_THRESHOLD` (default 250k tokens), the conversation is condensed before any further processing.

Use OpenHands' built-in context condenser to produce a summary that preserves:

- The core topic and intent
- Key decisions and outcomes
- Recent messages verbatim (the last `MESSAGE_WINDOW` messages are kept intact)
- Any operator-disclosed personal context

The condensed conversation replaces the original in all downstream steps: routing scorer receives the condensed version, and the agent session receives it as its conversation history.

---

## Routing Pipeline

### Step 1: Request Interception

Before routing, check if the incoming request is an OpenWebUI suggestion or title generation request.

Detection heuristics:
- The `messages` array contains a single message with content matching OpenWebUI's suggestion prompt patterns
- The message array is very short (1-2 messages) and the content asks for title suggestions or conversation summaries

If detected: Call `SUGGESTION_MODEL` directly via OpenRouter. Skip the entire routing pipeline. Return the response immediately.

### Step 2: Parallel Scoring

Extract the last `MESSAGE_WINDOW` messages from the conversation. Send them to all `SCORING_MODELS` in parallel with the following scoring prompt:

```
You are a conversation classifier. Given the following conversation
and a set of preset descriptions, score how well the conversation
matches each preset.

Return a JSON object where each key is the preset slug and the
value is a confidence score from 0.0 to 1.0.

Additionally, include a "crisis" key scored 0.0 to 1.0 indicating
whether the conversation contains signals of genuine distress,
hopelessness, self-harm ideation, or mental health crisis.

Focus on the overall conversation topic but weight the most recent
messages more heavily.

## PRESETS

{dynamically_generated_preset_descriptions}

## CONVERSATION

{last_n_messages}

Return ONLY valid JSON.
```

Preset descriptions are injected dynamically from the map built at startup.

Parallel execution: All scoring model calls fire concurrently using asyncio.gather. The pipeline waits for all to complete or times out after a configurable duration.

Response validation for each scoring model:
1. Parse the response as JSON. If parsing fails, discard.
2. Verify all preset slugs from the preset map are present as keys. If any are missing, discard.
3. Verify a `crisis` key is present. If missing, discard.
4. Verify all values are floats between 0.0 and 1.0. If any are out of range, discard.
5. If all scoring models are discarded, fall back to a default preset.

Score aggregation:
1. Each valid scoring model nominates a top preset and reports the gap between its top and second score.
2. If all models agree on the same top preset, use that preset.
3. If models disagree, use the scores from the model with the largest gap between top and second.
4. For the crisis score, take the maximum across all models. If any model detects crisis, treat it as detected.

### Step 3: Decision Logic

Once aggregated scores are resolved:

```
1. CRISIS CHECK
   If crisis score > CRISIS_THRESHOLD:
     Route to MENTAL_HEALTH_PRESET.
     Skip all other logic.

2. CONFIDENT ROUTE
   If top_score > CONFIDENCE_THRESHOLD
   AND (top_score - second_score) > CONFIDENCE_GAP:
     Route to the top-scoring preset.

3. AMBIGUOUS ROUTE
   If multiple presets score above CONFIDENCE_THRESHOLD
   and the gap is within CONFIDENCE_GAP:
     Route to the preset backed by the MORE CAPABLE model.

4. LOW CONFIDENCE FALLBACK
   If no preset scores above CONFIDENCE_THRESHOLD:
     Route to the most capable general-purpose preset.
```

### Step 4: Conversation State Cache

Maintain a per-conversation cache that stores:
- The currently active preset for this conversation
- The scores from the last routing decision
- A message counter since the last reclassification

Cache logic:
- First message in a conversation: Always run the full routing pipeline
- Subsequent messages: Check if reclassification is needed
- If fewer than N messages since last classification, reuse cached route
- If the new message is short and matches social patterns (greetings, acknowledgments), reuse cached route

---

## OpenHands Agent Sessions

### Session Creation

Each conversation maps to a persistent OpenHands agent session. When a routed request reaches the agent layer, the API either creates a new session or restores an existing one.

```python
from pydantic import SecretStr
from openhands.sdk import LLM, Agent, Conversation

llm = LLM(
    usage_id="agent",
    model=f"openrouter/@preset/{selected_preset_slug}",
    base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=SecretStr(os.getenv("LLM_API_KEY")),
)

agent = Agent(
    llm=llm,
    tools=tools,
    mcp_config=resolved_mcp_config,
)
```

### Conversation Persistence

All conversations use OpenHands' persistence system to save and restore state across sessions. Each conversation is created with a unique ID and a persistence directory.

On subsequent requests for the same conversation, the session is restored from disk and continues from saved state.

What gets persisted:
- Agent state and configuration
- Message history (complete event log)
- Tool outputs from previous turns
- Execution state (iteration count, status)
- Activated skills and MCP connections
- LLM usage statistics

### Human-in-the-Loop

The agent asks for more information or presents choices before proceeding with ambiguous or high-impact actions. This is handled natively by OpenHands' conversation model.

Trigger conditions:
- Ambiguous requests where multiple valid interpretations exist
- High-impact actions: destructive operations, infrastructure changes, bulk memory modifications
- Multi-step plans requiring confirmation
- Any action gated by memory deletion or security override

### Concurrent Messages

For non-blocking clients, messages can be sent to a conversation while the agent is already running via OpenHands' send-message-while-running support.

---

## MCP Server Configuration

MCP servers are configured using the standard MCP config format and passed to the OpenHands Agent constructor. All MCP servers in this project use uvx-based command execution.

### MCP Server Definitions

```python
MCP_SERVERS = {
    "time": {
        "command": "uvx",
        "args": ["mcp-server-time@latest"],
    },
    "aws_docs": {
        "command": "uvx",
        "args": ["awslabs.aws-documentation-mcp-server@latest"],
    },
    "google_sheets": {
        "command": "uvx",
        "args": ["mcp-server-google-sheets@latest"],
    },
    "yahoo_finance": {
        "command": "uvx",
        "args": ["mcp-yahoo-finance"],
    },
    "alpha_vantage": {
        "command": "uvx",
        "args": ["alphavantage-mcp"],
    },
    "sandbox": {
        "command": "uvx",
        "args": ["mcp-server-filesystem@latest", "--root", os.getenv("SANDBOX_PATH", "./sandbox")],
    }
}
```

### Preset-to-MCP Mapping

Each preset can have zero or more MCP servers attached. Some MCP servers are shared across all presets via the `__all__` key.

```python
PRESET_MCP_MAP = {
    "__all__": ["time"],
    "architecture": ["aws_docs", "sandbox"],
    "coding": ["sandbox"],
    "health": ["google_sheets"],
}
```

### Sandbox Behavior

The sandbox MCP server provides file system access scoped to SANDBOX_PATH. Presets with sandbox access are instructed via a system message injected by the API before dispatching:

> If your response includes code exceeding 5 lines, do not embed it in the message body. Write it to a file in the sandbox and reference the file path. The file will be delivered as an attachment.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

### 3. Run the Server

```bash
# From the app directory
python -m src.main

# Or with uvicorn directly
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Test the API

```bash
# List models
curl http://localhost:8000/v1/models

# Chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "if-prototype",
    "messages": [
      {
        "role": "user",
        "content": "Hello"
      }
    ]
  }'
```

---

## Project Structure

```
if-prototype-a1/
├── README.md
├── requirements.txt
├── .env.example
├── main_system_prompt.txt
├── plan.md
├── data/
│   ├── memory.json
│   └── conversations/
├── sandbox/
└── src/
    ├── main.py
    ├── config.py
    │
    ├── api/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── completions.py
    │   ├── files.py
    │   └── schemas.py
    │
    ├── routing/
    │   ├── __init__.py
    │   ├── interceptor.py
    │   ├── scorer.py
    │   ├── decision.py
    │   └── cache.py
    │
    ├── agent/
    │   ├── __init__.py
    │   ├── session.py
    │   ├── tools.py
    │   ├── condenser.py
    │   └── prompts/
    │       └── system_prompt.j2
    │
    ├── memory/
    │   ├── __init__.py
    │   └── store.py
    │
    ├── mcp_servers/
    │   ├── __init__.py
    │   └── config.py
    │
    └── presets/
        ├── __init__.py
        └── loader.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key |
| `LLM_API_KEY` | No | `OPENROUTER_API_KEY` | LLM API key |
| `LLM_BASE_URL` | No | `https://openrouter.ai/api/v1` | LLM base URL |
| `MESSAGE_WINDOW` | No | `8` | Recent messages for routing |
| `CRISIS_THRESHOLD` | No | `0.3` | Crisis score threshold |
| `CONFIDENCE_THRESHOLD` | No | `0.6` | Minimum score for confident routing |
| `CONFIDENCE_GAP` | No | `0.2` | Minimum gap for confident decision |
| `SUGGESTION_MODEL` | No | `mistralai/mistral-nemo` | Model for suggestions |
| `SCORING_MODELS` | No | (see .env.example) | Models for scoring |
| `MENTAL_HEALTH_PRESET` | No | `general` | Crisis preset slug |
| `SANDBOX_PATH` | No | `./sandbox` | File output directory |
| `MEMORY_DB_PATH` | No | `./data/memory.json` | Memory store path |
| `PERSISTENCE_DIR` | No | `./data/conversations` | Conversation persistence |
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `8000` | Server bind port |

---

## Memory Store

The memory store uses ChromaDB for semantic search over operator context. Memory categories:

- **preference**: Language/framework preferences, communication style
- **personal**: Birthday, location, profession, roles, relationships
- **skill_level**: Self-reported or demonstrated understanding
- **opinion**: Strong stances on technologies, approaches, topics
- **life_event**: Job changes, moves, competitions, milestones
- **future_plan**: Goals, timelines, aspirations
- **mental_state**: Noted shifts in mood, stress, outlook

### Memory Tools

- `memory_search`: Semantic search across stored memories
- `memory_add`: Store new memories about the operator
- `memory_remove`: Delete memories (requires operator confirmation)
- `memory_list`: List all stored memories

---

## MCP Servers

MCP servers are configured per preset:

- **time**: Available to all presets
- **aws_docs**: Available to architecture preset
- **sandbox**: Available to coding and architecture presets
- **google_sheets**: Available to health preset

---

## License

MIT
