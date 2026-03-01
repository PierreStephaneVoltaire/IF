# IF — Intelligent Routing Agent API

An OpenAI-compatible API server in Python that provides intelligent routing to specialized AI presets based on conversation analysis. Incoming chat completions are analyzed by parallel scoring models, classified against preset definitions, and dispatched to the best-fit specialist model via OpenRouter presets.

The agent runs on the OpenHands SDK with access to MCP servers for extended capabilities (AWS docs, financial data, file system), a persistent RAG-backed memory store, conversation persistence, and a file-based attachment system.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Request Flow Diagram](#request-flow-diagram)
- [API Endpoints](#api-endpoints)
- [Routing Pipeline](#routing-pipeline)
- [Channel System](#channel-system)
- [Storage Layer](#storage-layer)
- [MCP Server Configuration](#mcp-server-configuration)
- [Preset System](#preset-system)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Startup Sequence](#startup-sequence)
- [Quick Start](#quick-start)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Client Layer                                       │
│                                                                              │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐            │
│  │   OpenWebUI    │    │    Discord     │    │   HTTP Client  │            │
│  │   (polling)    │    │    (bot)       │    │   (curl/SDK)   │            │
│  └───────┬────────┘    └───────┬────────┘    └───────┬────────┘            │
└──────────┼─────────────────────┼─────────────────────┼──────────────────────┘
           │                     │                     │
           ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Channel System (src/channels/)                        │
│                                                                              │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐            │
│  │ OpenWebUI      │    │ Discord        │    │ HTTP API       │            │
│  │ Listener       │    │ Listener       │    │ (FastAPI)      │            │
│  └───────┬────────┘    └───────┬────────┘    └───────┬────────┘            │
│          │                     │                     │                      │
│          ▼                     ▼                     │                      │
│  ┌────────────────┐    ┌────────────────┐           │                      │
│  │ Translator     │    │ Translator     │           │                      │
│  └───────┬────────┘    └───────┬────────┘           │                      │
│          │                     │                     │                      │
│          ▼                     ▼                     │                      │
│  ┌────────────────┐    ┌────────────────┐           │                      │
│  │ Debounce Queue │    │ Debounce Queue │           │                      │
│  └───────┬────────┘    └───────┬────────┘           │                      │
│          │                     │                     │                      │
│          └──────────┬──────────┘                     │                      │
│                     ▼                                │                      │
│          ┌────────────────┐                          │                      │
│          │ Dispatcher     │                          │                      │
│          └───────┬────────┘                          │                      │
│                  │                                   │                      │
└──────────────────┼───────────────────────────────────┼──────────────────────┘
                   │                                   │
                   ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Core Pipeline (src/api/completions.py)                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    process_chat_completion_internal()                │   │
│  │                                                                      │   │
│  │  Step 1: Request Interceptor (OpenWebUI task detection)             │   │
│  │          ┌────────────────────────────────────────────────┐          │   │
│  │          │ intercept_request() → SUGGESTION_MODEL         │          │   │
│  │          │ (bypass routing for title/suggestion tasks)    │          │   │
│  │          └────────────────────────────────────────────────┘          │   │
│  │                           │                                          │   │
│  │  Step 2: Parallel Scoring (preset classification)                   │   │
│  │          ┌────────────────────────────────────────────────┐          │   │
│  │          │ score_conversation() → SCORING_MODELS (3x)     │          │   │
│  │          │ (gemini-flash, gpt-oss, claude-haiku)          │          │   │
│  │          └────────────────────────────────────────────────┘          │   │
│  │                           │                                          │   │
│  │  Step 3: Decision Logic (preset selection)                          │   │
│  │          ┌────────────────────────────────────────────────┐          │   │
│  │          │ select_preset() → Crisis/Confident/Ambiguous   │          │   │
│  │          └────────────────────────────────────────────────┘          │   │
│  │                           │                                          │   │
│  │  Step 4: Conversation Cache (routing state)                         │   │
│  │          ┌────────────────────────────────────────────────┐          │   │
│  │          │ ConversationCache → Topic Shift Detection      │          │   │
│  │          └────────────────────────────────────────────────┘          │   │
│  │                           │                                          │   │
│  │  Step 5: Agent Execution (OpenHands SDK)                            │   │
│  │          ┌────────────────────────────────────────────────┐          │   │
│  │          │ execute_agent() → @preset/{selected_preset}    │          │   │
│  │          └────────────────────────────────────────────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     OpenHands Agent (src/agent/)                            │
│                                                                              │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐            │
│  │  LLM Config    │    │  MCP Servers   │    │ Memory Tools   │            │
│  │  @preset/slug  │    │  (uvx-based)   │    │  (ChromaDB)    │            │
│  └────────────────┘    └────────────────┘    └────────────────┘            │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────┐            │
│  │                    Conversation Persistence                 │            │
│  │                 (src/data/conversations/{id}/)             │            │
│  └────────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
            OpenRouter API
         (@preset/{name} routing)
```

---

## Request Flow Diagram

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Endpoint
    participant Interceptor
    participant Scorer
    participant Decision
    participant Cache
    participant Agent as OpenHands Agent
    participant OR as OpenRouter

    Client->>API: POST /v1/chat/completions

    Note over API: Extract conversation_id

    API->>Interceptor: intercept_request messages

    alt Is OpenWebUI Task
        Interceptor->>OR: Call SUGGESTION_MODEL
        OR-->>Interceptor: Quick response
        Interceptor-->>API: Bypass routing
        API-->>Client: Return response
    else Normal Request
        Interceptor-->>API: Continue to routing

        API->>Cache: get conversation_id

        alt Cache Hit and No Topic Shift
            Cache-->>API: Return cached preset
        else Cache Miss or Topic Shift
            API->>Scorer: score_conversation messages

            par Parallel Scoring
                Scorer->>OR: Model 1: gemini-2.5-flash-lite
                Scorer->>OR: Model 2: gpt-oss-120b
                Scorer->>OR: Model 3: claude-haiku-4.5
            end

            OR-->>Scorer: Scores from all models
            Scorer->>Scorer: Aggregate scores
            Scorer-->>API: AggregatedScores

            API->>Decision: select_preset scores

            alt Crisis Detected
                Decision-->>API: Route to mental_health preset
            else Confident Match
                Decision-->>API: Route to top preset
            else Ambiguous
                Decision-->>API: Route to most capable
            else Low Confidence
                Decision-->>API: Route to fallback
            end

            API->>Cache: Update conversation state
        end

        API->>Agent: execute_agent preset messages

        Agent->>Agent: Assemble system prompt
        Agent->>Agent: Resolve MCP servers
        Agent->>OR: Call @preset/selected_preset

        OR-->>Agent: Stream response
        Agent->>Agent: Scan for attachments
        Agent-->>API: AgentResponse

        API-->>Client: ChatCompletionResponse
    end
```

---

## API Endpoints

### Core Endpoints

#### `GET /v1/models`

Returns the model list with a single entry for `if-prototype`.

**Response:**
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

#### `POST /v1/chat/completions`

Standard OpenAI chat completions interface. Accepts `model: "if-prototype"` only.

**Request Body:**
```json
{
  "model": "if-prototype",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "stream": false
}
```

**Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "if-prototype",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Response text here..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

#### `POST /api/v1/chat/completions`

Alias for `/v1/chat/completions` for OpenWebUI compatibility.

---

### Webhook Management Endpoints

#### `POST /v1/webhooks/register`

Register a new channel webhook and start listening immediately.

**Request Body (Discord):**
```json
{
  "platform": "discord",
  "label": "My Discord Channel",
  "discord": {
    "bot_token": "your-bot-token",
    "channel_id": "123456789"
  }
}
```

**Request Body (OpenWebUI):**
```json
{
  "platform": "openwebui",
  "label": "My OpenWebUI Channel",
  "openwebui": {
    "base_url": "https://openwebui.example.com",
    "channel_id": "channel-uuid",
    "api_key": "your-api-key"
  }
}
```

**Response:**
```json
{
  "webhook_id": "wh_abc123def456",
  "conversation_id": "conv_xyz789",
  "platform": "discord",
  "label": "My Discord Channel",
  "status": "listening"
}
```

#### `GET /v1/webhooks/`

List all registered webhooks (active and inactive).

**Response:**
```json
{
  "webhooks": [
    {
      "webhook_id": "wh_abc123",
      "conversation_id": "conv_xyz",
      "platform": "discord",
      "label": "My Channel",
      "status": "active"
    }
  ],
  "total": 1
}
```

#### `GET /v1/webhooks/active`

List only active webhooks.

#### `GET /v1/webhooks/{webhook_id}`

Get a specific webhook by ID.

#### `DELETE /v1/webhooks/{webhook_id}`

Deactivate a webhook (stops listener, marks as inactive).

#### `POST /v1/webhooks/{webhook_id}/restart`

Restart a deactivated webhook.

---

### File Serving Endpoints

#### `GET /files/sandbox/{conversation_id}/{filepath:path}`

Serve files from a conversation's sandbox directory.

**Features:**
- Path traversal protection
- Automatic MIME type detection
- Scoped to conversation-specific directory

---

### Health Check

#### `GET /health`

Returns system health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "if-prototype-a1",
  "features": {
    "routing": "partial",
    "interceptor": "active",
    "attachments": "active",
    "memory_store": "active",
    "memory_count": 42,
    "presets_loaded": true,
    "preset_count": 8,
    "channel_system": "active",
    "active_listeners": 2,
    "pending_messages": 3
  }
}
```

---

## Routing Pipeline

The routing pipeline in [`src/api/completions.py`](src/api/completions.py:74) (`process_chat_completion_internal()`) consists of 5 steps:

### Step 1: Request Interception

**Module:** [`src/routing/interceptor.py`](src/routing/interceptor.py)

Detects OpenWebUI suggestion/title generation requests and bypasses the full routing pipeline.

- Checks for known OpenWebUI task markers in message content
- Calls `SUGGESTION_MODEL` (default: `mistralai/mistral-nemo`) directly
- Returns immediately without running scoring

**Detection Markers:**
- `"### Task:\nSuggest 3-5 relevant follow-up"`
- `"### Task:\nGenerate a concise, 3-5 word title"`
- `"### Task:\nGenerate 1-3 broad tags"`

### Step 2: Parallel Scoring

**Module:** [`src/routing/scorer.py`](src/routing/scorer.py)

Sends the last `MESSAGE_WINDOW` messages to all scoring models in parallel.

**Default Scoring Models:**
1. `google/gemini-2.5-flash-lite`
2. `openai/gpt-oss-120b`
3. `anthropic/claude-haiku-4.5`

**Scoring Prompt Structure:**
```
You are a conversation classifier. Given the following conversation
and a set of preset descriptions, score how well the conversation
matches each preset.

Return a JSON object where each key is the preset slug and the
value is a confidence score from 0.0 to 1.0.

Additionally, include a "crisis" key scored 0.0 to 1.0 indicating
whether the conversation contains signals of genuine distress.
```

**Response Validation:**
1. Parse response as JSON
2. Verify all preset slugs are present
3. Verify `crisis` key exists
4. Verify all values are floats between 0.0 and 1.0
5. Discard invalid responses

**Score Aggregation:**
- Each model nominates a top preset with confidence gap
- If all models agree → use that preset
- If models disagree → use scores from model with largest gap
- Crisis score = maximum across all models

### Step 3: Decision Logic

**Module:** [`src/routing/decision.py`](src/routing/decision.py)

Selects the final preset based on aggregated scores.

**Decision Tree:**

```
1. CRISIS CHECK
   If crisis_score > CRISIS_THRESHOLD (0.3):
     → Route to MENTAL_HEALTH_PRESET
     → Skip all other logic

2. CONFIDENT ROUTE
   If top_score > CONFIDENCE_THRESHOLD (0.6)
   AND (top_score - second_score) > CONFIDENCE_GAP (0.2):
     → Route to top-scoring preset

3. AMBIGUOUS ROUTE
   If multiple presets score above CONFIDENCE_THRESHOLD
   and gap is within CONFIDENCE_GAP:
     → Route to most capable preset among candidates

4. LOW CONFIDENCE FALLBACK
   If no preset scores above CONFIDENCE_THRESHOLD:
     → Route to most capable general preset
```

**Capability Ranking:**
```python
capability_ranking = {
    "architecture": 100,  # Claude 3.5 Sonnet
    "coding": 95,         # Claude 3.5 Sonnet
    "reasoning": 90,      # o1-preview
    "general": 50,
    "social": 40,
    "health": 30,
}
```

### Step 4: Conversation State Cache

**Module:** [`src/routing/cache.py`](src/routing/cache.py)

Caches routing decisions per conversation to avoid reclassifying on every message.

**Cache Entry:**
```python
@dataclass
class ConversationState:
    conversation_id: str
    active_preset: str
    anchor_window: List[str]      # Messages at last classification
    last_scores: AggregatedScores
    last_decision: RoutingDecision
    last_updated: datetime
```

**Topic Shift Detection:**

**Module:** [`src/routing/topic_shift.py`](src/routing/topic_shift.py)

When cache is warm (preset already assigned), uses LLM to detect topic shifts:

```python
async def topic_has_shifted(
    anchor_messages: List[str],  # From cache
    current_messages: List[str], # Current window
    http_client: httpx.AsyncClient,
) -> bool:
```

- Uses `TOPIC_SHIFT_MODEL` (default: `z-ai/glm-4.7-flash`)
- 5-second timeout, defaults to `False` on failure
- Returns `True` only for major domain shifts (coding → finance)
- Ignores sub-topic shifts (Python → Terraform)
- Ignores social noise ("thanks", "ok")

### Step 5: Agent Execution

**Module:** [`src/agent/session.py`](src/agent/session.py)

Executes the conversation with the selected preset via OpenHands SDK.

**Process:**
1. Get or create agent session for conversation
2. Assemble system prompt (base + memory + preset-specific)
3. Resolve MCP servers for preset
4. Execute agent with messages
5. Scan for new file attachments
6. Return response with attachments

---

## Channel System

The channel system enables multi-platform integration with Discord and OpenWebUI.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Channel System Flow                           │
│                                                                  │
│  Discord Bot              OpenWebUI Poller                      │
│      │                         │                                │
│      ▼                         ▼                                │
│  discord_listener.py     openwebui_listener.py                  │
│      │                         │                                │
│      │    push_message()       │                                │
│      └─────────┬───────────────┘                                │
│                ▼                                                 │
│         debounce.py                                             │
│    (30s batching window)                                        │
│                │                                                 │
│                ▼                                                 │
│         dispatcher.py                                           │
│                │                                                 │
│      ┌─────────┴─────────┐                                      │
│      ▼                   ▼                                      │
│  discord_translator  openwebui_translator                       │
│      │                   │                                      │
│      └─────────┬─────────┘                                      │
│                ▼                                                 │
│    process_chat_completion_internal()                           │
│                │                                                 │
│                ▼                                                 │
│         chunker.py                                              │
│    (1500 char chunks)                                           │
│                │                                                 │
│                ▼                                                 │
│         delivery.py                                             │
│      ┌─────────┴─────────┐                                      │
│      ▼                   ▼                                      │
│  Discord Channel    OpenWebUI Channel                           │
└─────────────────────────────────────────────────────────────────┘
```

### Components

#### Listener Manager

**File:** [`src/channels/manager.py`](src/channels/manager.py)

Manages listener lifecycle in background daemon threads.

```python
def start_listener(record: WebhookRecord) -> None
def stop_listener(webhook_id: str) -> None
def start_all_active(records: list[WebhookRecord]) -> None  # Called at startup
def stop_all() -> None  # Called at shutdown
```

#### Discord Listener

**File:** [`src/channels/listeners/discord_listener.py`](src/channels/listeners/discord_listener.py)

- Uses `discord.py` client in a dedicated thread
- Listens to a single registered channel
- Ignores bot messages and own messages
- Pushes messages to debounce queue with attachments

#### OpenWebUI Listener

**File:** [`src/channels/listeners/openwebui_listener.py`](src/channels/listeners/openwebui_listener.py)

- Polling-based listener (default: 5-second interval)
- Tracks last-seen message ID for incremental updates
- Extracts files and attachments from messages

#### Debounce System

**File:** [`src/channels/debounce.py`](src/channels/debounce.py)

Thread-safe message batching with configurable window.

**Configuration:**
- `CHANNEL_DEBOUNCE_SECONDS`: Inactivity window (default: 30s)
- Messages are accumulated and flushed after silence period

**Threading Model:**
- Listener threads call `push_message()` from their own event loops
- Uses `threading.Lock` for buffer access
- Schedules timers on main asyncio event loop via `call_soon_threadsafe`

#### Translators

**Files:**
- [`src/channels/translators/discord_translator.py`](src/channels/translators/discord_translator.py)
- [`src/channels/translators/openwebui_translator.py`](src/channels/translators/openwebui_translator.py)

Convert platform messages to `ChatCompletionRequest` format:

```python
def translate_discord_batch(messages: list[dict], conversation_id: str) -> dict:
    # Returns:
    # {
    #     "model": "if-prototype",
    #     "stream": True,
    #     "messages": [{"role": "user", "content": content_parts}],
    #     "_conversation_id": conversation_id,
    # }
```

- Prepends sender attribution: `[Alice]: message text`
- Converts image attachments to `image_url` content parts
- References non-image attachments as text with URL

#### Response Chunker

**File:** [`src/channels/chunker.py`](src/channels/chunker.py)

Splits long responses for platform limits.

**Configuration:**
- `CHANNEL_MAX_CHUNK_CHARS`: Max chars per chunk (default: 1500)

**Split Priority:**
1. Paragraph break (`\n\n`)
2. Sentence break (`.\n` or `.`)
3. Newline (`\n`)
4. Space (` `)
5. Hard cut

#### Delivery

**File:** [`src/channels/delivery.py`](src/channels/delivery.py)

Platform-specific response delivery.

**Discord:**
- Sequential chunk delivery with 0.5s delay
- Files attached to last chunk
- Typing indicator during processing

**OpenWebUI:**
- Single combined message
- Attachments as markdown links

---

## Storage Layer

The storage layer provides an abstract interface for webhook persistence with pluggable backends.

### Architecture

**Protocol:** [`src/storage/protocol.py`](src/storage/protocol.py)

```python
@runtime_checkable
class WebhookStore(Protocol):
    def create(self, record: WebhookRecord) -> WebhookRecord: ...
    def get(self, webhook_id: str) -> WebhookRecord | None: ...
    def list_all(self) -> list[WebhookRecord]: ...
    def list_active(self) -> list[WebhookRecord]: ...
    def deactivate(self, webhook_id: str) -> bool: ...
```

### Data Model

**File:** [`src/storage/models.py`](src/storage/models.py)

```python
class WebhookRecord(SQLModel, table=True):
    __tablename__ = "webhooks"

    webhook_id: str        # Primary key, auto-generated: wh_{uuid12}
    conversation_id: str   # Index, auto-generated: conv_{uuid12}
    platform: str          # "discord" | "openwebui"
    label: str             # Human-readable name
    status: str            # "active" | "inactive"
    created_at: str        # ISO timestamp
    config_json: str       # JSON-serialized platform config
```

### SQLite Backend

**File:** [`src/storage/sqlite_backend.py`](src/storage/sqlite_backend.py)

- Uses SQLModel ORM over SQLite
- WAL mode for concurrent read/write safety
- Thread-safe for listener + API access

### Factory

**File:** [`src/storage/factory.py`](src/storage/factory.py)

```python
def init_store() -> None       # Called at startup
def get_webhook_store() -> WebhookStore
def close_store() -> None      # Called at shutdown
```

**Configuration:**
- `STORE_BACKEND`: Backend type (default: `sqlite`)
- `STORAGE_DB_PATH`: SQLite file path (default: `./data/store.db`)

**Future:** DynamoDB backend planned for AWS deployment.

---

## MCP Server Configuration

MCP servers provide extended capabilities to the agent.

### Available Servers

**File:** [`src/mcp_servers/config.py`](src/mcp_servers/config.py)

| Server | Package | Purpose |
|--------|---------|---------|
| `time` | `mcp-server-time@latest` | Current date/time |
| `aws_docs` | `awslabs.aws-documentation-mcp-server@latest` | AWS documentation lookup |
| `google_sheets` | `mcp-server-google-sheets@latest` | Spreadsheet access |
| `yahoo_finance` | `mcp-yahoo-finance` | Stock quotes and data |
| `alpha_vantage` | `alphavantage-mcp` | Financial indicators |
| `sandbox` | `mcp-server-filesystem@latest` | File system access |

### Preset Mapping

```python
PRESET_MCP_MAP = {
    "__all__": ["time"],
    "architecture": ["aws_docs", "sandbox"],
    "coding": ["sandbox"],
    "health": ["google_sheets"],
    "mental_health": [],
    "social": [],
    "finance": ["yahoo_finance", "alpha_vantage"],
}
```

### Sandbox Scoping

The sandbox server is scoped per-conversation:

```python
def resolve_mcp_config(preset_slug: str, conversation_id: str) -> Dict[str, Any]:
    # Sandbox root becomes: {SANDBOX_PATH}/{conversation_id}/
```

This prevents file cross-contamination between parallel sessions.

---

## Preset System

Presets are static definitions that define routing targets.

### Available Presets

**File:** [`src/presets/loader.py`](src/presets/loader.py)

| Preset | Model | Description |
|--------|-------|-------------|
| `architecture` | `@preset/architecture` | System design, infrastructure planning |
| `code` | `@preset/code` | Writing, modifying, debugging code |
| `shell` | `@preset/shell` | CLI commands, one-liners |
| `security` | `@preset/security` | Threat modeling, compliance |
| `health` | `@preset/health` | Fitness, nutrition, sports |
| `mental_health` | `@preset/mental_health` | Emotional support, crisis routing |
| `finance` | `@preset/finance` | Market data, investing |
| `social` | `@preset/social` | Casual conversation |
| `general` | `@preset/general` | General-purpose fallback |

### Preset Structure

```python
@dataclass
class Preset:
    slug: str           # URL-safe identifier
    name: str           # Display name
    description: str    # Used for scoring classification
    model: str          # OpenRouter model: @preset/{slug}
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `OPENROUTER_API_KEY` | OpenRouter API key for model access |

### Routing Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MESSAGE_WINDOW` | `8` | Recent messages for routing |
| `CRISIS_THRESHOLD` | `0.3` | Crisis score threshold |
| `CONFIDENCE_THRESHOLD` | `0.6` | Minimum score for confident routing |
| `CONFIDENCE_GAP` | `0.2` | Minimum gap for confident decision |
| `RECLASSIFY_MESSAGE_COUNT` | `4` | Messages before reclassification check |

### Model Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SUGGESTION_MODEL` | `mistralai/mistral-nemo` | Quick reply model |
| `SCORING_MODELS` | *(see below)* | Comma-separated scoring models |
| `TOPIC_SHIFT_MODEL` | `z-ai/glm-4.7-flash` | Topic shift detection |
| `MENTAL_HEALTH_PRESET` | `mental-health` | Crisis routing target |

**Default SCORING_MODELS:**
```
google/gemini-2.5-flash-lite,openai/gpt-oss-120b,anthropic/claude-haiku-4.5
```

### Storage Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `STORE_BACKEND` | `sqlite` | Storage backend type |
| `STORAGE_DB_PATH` | `./data/store.db` | SQLite database path |
| `SANDBOX_PATH` | `./sandbox` | File output directory |
| `MEMORY_DB_PATH` | `./data/memory_db` | ChromaDB path |
| `PERSISTENCE_DIR` | `./data/conversations` | Conversation persistence |

### Channel Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHANNEL_DEBOUNCE_SECONDS` | `30` | Message batching window |
| `CHANNEL_MAX_CHUNK_CHARS` | `1500` | Max chars per response chunk |
| `OPENWEBUI_POLL_INTERVAL` | `5.0` | OpenWebUI polling interval |

### MCP Server Keys

| Variable | Description |
|----------|-------------|
| `GOOGLE_SHEETS_CREDENTIALS` | Base64-encoded JSON credentials |
| `ALPHAVANTAGE_API_KEY` | Alpha Vantage API key |

### Server Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server bind port |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | LLM API base URL |

---

## Project Structure

```
if-prototype-a1/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment template
├── main_system_prompt.txt       # Base system prompt for agent
├── plan.md                      # Implementation plan
│
├── data/                        # Runtime data directory
│   ├── memory_db/               # ChromaDB vector storage
│   ├── conversations/           # OpenHands persistence
│   │   └── {conversation_id}/
│   │       ├── base_state.json
│   │       └── events/
│   └── store.db                 # SQLite webhook storage
│
├── sandbox/                     # File output directory
│   └── {conversation_id}/       # Per-conversation isolation
│
├── plans/                       # Implementation phase docs
│   ├── phase1-2-implementation.md
│   ├── phase3-4-implementation.md
│   ├── phase5-implementation.md
│   └── phase6-implementation.md
│
└── src/                         # Source code
    ├── main.py                  # FastAPI app entry point
    ├── config.py                # Environment configuration
    │
    ├── api/                     # HTTP API layer
    │   ├── __init__.py
    │   ├── models.py            # /v1/models endpoint
    │   ├── completions.py       # /v1/chat/completions endpoint
    │   ├── files.py             # /files/sandbox/* endpoint
    │   ├── webhooks.py          # /v1/webhooks/* endpoints
    │   └── schemas.py           # Pydantic request/response models
    │
    ├── routing/                 # Routing pipeline
    │   ├── __init__.py
    │   ├── interceptor.py       # Step 1: OpenWebUI task detection
    │   ├── scorer.py            # Step 2: Parallel scoring
    │   ├── decision.py          # Step 3: Preset selection
    │   ├── cache.py             # Step 4: Conversation state
    │   └── topic_shift.py       # Topic shift detection
    │
    ├── agent/                   # OpenHands agent integration
    │   ├── __init__.py
    │   ├── session.py           # Session management
    │   ├── tools.py             # Memory tools
    │   ├── sandbox.py           # Sandbox path resolution
    │   ├── condenser.py         # Context condensation
    │   └── prompts/
    │       └── system_prompt.j2
    │
    ├── channels/                # Channel system
    │   ├── __init__.py
    │   ├── manager.py           # Listener lifecycle
    │   ├── debounce.py          # Message batching
    │   ├── dispatcher.py        # Pipeline bridge
    │   ├── chunker.py           # Response chunking
    │   ├── delivery.py          # Platform delivery
    │   ├── listeners/
    │   │   ├── __init__.py
    │   │   ├── discord_listener.py
    │   │   └── openwebui_listener.py
    │   └── translators/
    │       ├── __init__.py
    │       ├── discord_translator.py
    │       └── openwebui_translator.py
    │
    ├── storage/                 # Persistence layer
    │   ├── __init__.py
    │   ├── protocol.py          # WebhookStore protocol
    │   ├── models.py            # WebhookRecord model
    │   ├── factory.py           # Backend factory
    │   ├── sqlite_backend.py    # SQLite implementation
    │   └── dynamodb_backend.py  # Future AWS implementation
    │
    ├── memory/                  # Memory store
    │   ├── __init__.py
    │   └── store.py             # ChromaDB integration
    │
    ├── mcp_servers/             # MCP configuration
    │   ├── __init__.py
    │   └── config.py            # Server definitions and mapping
    │
    └── presets/                 # Preset definitions
        ├── __init__.py
        └── loader.py            # Static preset loading
```

---

## Startup Sequence

The application startup in [`src/main.py`](src/main.py:34) follows this sequence:

```mermaid
sequenceDiagram
    participant App as FastAPI App
    participant HTTP as HTTP Client
    participant Presets as PresetManager
    participant Memory as MemoryStore
    participant Storage as SQLite Store
    participant Debounce as Debounce System
    participant Channels as Channel Manager

    App->>HTTP: Initialize HTTP client
    App->>HTTP: Configure connection pooling

    App->>Presets: load_presets
    Presets-->>App: Static presets loaded

    App->>App: Create directories
    Note over App: sandbox, memory_db, conversations

    App->>App: validate_mcp_config

    App->>Memory: get_memory_store
    Memory->>Memory: Initialize ChromaDB
    Memory-->>App: Store ready

    App->>Storage: init_store
    Storage->>Storage: Create SQLite with WAL
    Storage-->>App: Store initialized

    App->>Debounce: init_debounce
    Debounce-->>App: Main loop registered

    App->>Storage: get_webhook_store
    Storage-->>App: WebhookStore instance

    App->>Channels: start_all_active
    Channels->>Channels: Resume listeners from DB
    Channels-->>App: Listeners started

    App-->>App: Server ready
```

**Startup Log Output:**
```
[Startup] Initializing IF Prototype A1...
[Startup] HTTP client initialized
[Startup] Loading presets...
[Startup] Sandbox directory: /path/to/sandbox
[Startup] Memory database directory: /path/to/data/memory_db
[Startup] Conversation persistence directory: /path/to/data/conversations
[Startup] MCP configuration validated
[Startup] Memory store initialized (0 memories)
[Startup] Storage backend initialized at ./data/store.db
[Startup] Debounce system initialized (window=30.0s)
[Startup] Resumed 0 active channel listeners
[Startup] Server ready on 0.0.0.0:8000
```

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
      {"role": "user", "content": "Hello"}
    ]
  }'

# Health check
curl http://localhost:8000/health
```

### 5. Register a Discord Channel

```bash
curl -X POST http://localhost:8000/v1/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "discord",
    "label": "My Channel",
    "discord": {
      "bot_token": "your-bot-token",
      "channel_id": "123456789"
    }
  }'
```

---

## Memory Store

The memory store uses ChromaDB for semantic search over operator context.

**Memory Categories:**
- **preference**: Language/framework preferences, communication style
- **personal**: Birthday, location, profession, relationships
- **skill_level**: Self-reported or demonstrated understanding
- **opinion**: Strong stances on technologies, approaches
- **life_event**: Job changes, moves, competitions, milestones
- **future_plan**: Goals, timelines, aspirations
- **mental_state**: Noted shifts in mood, stress, outlook

**Memory Tools:**
- `memory_search`: Semantic search across stored memories
- `memory_add`: Store new memories about the operator
- `memory_remove`: Delete memories (requires confirmation)
- `memory_list`: List all stored memories

---

## License

MIT
