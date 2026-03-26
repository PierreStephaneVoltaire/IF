# Storage Layer

Abstract interface for persistence with pluggable backends.

## Architecture

### Protocol

**File:** `src/storage/protocol.py`

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

**File:** `src/storage/models.py`

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

## Backends

### SQLite Backend

**File:** `src/storage/sqlite_backend.py`

- Uses SQLModel ORM over SQLite
- WAL mode for concurrent read/write safety
- Thread-safe for listener + API access

### DynamoDB Backend

**File:** `src/storage/dynamodb_backend.py`

> **Note:** The DynamoDB webhook backend is a stub. Use SQLite for webhooks. DynamoDB is used for the directive store.

## Factory

**File:** `src/storage/factory.py`

```python
def init_store() -> None              # Called at startup
def init_directive_store() -> None    # Initialize DynamoDB directive store
def get_webhook_store() -> WebhookStore
def close_store() -> None             # Called at shutdown
```

## Directive Store

**File:** `src/storage/directive_store.py`

Uses DynamoDB for behavioral directive persistence:

```python
class DirectiveStore:
    def load() -> List[Directive]         # Load and cache all active directives
    def get(alpha: int, beta: int)        # Get specific directive
    def get_all(alpha: int = None)        # Get all (optionally filtered)
    def add(alpha, label, content, ...)   # Add new directive
    def revise(alpha, beta, content)      # Create new version
    def deactivate(alpha, beta)           # Soft-delete
    def format_for_prompt(alpha=None)     # Format for system prompt
```

**DynamoDB Table Schema:**

```sql
CREATE TABLE if-core (
    PK STRING,          -- Always "DIR"
    SK STRING,          -- "{alpha}-{beta}-{version}"
    label STRING,
    content STRING,
    active BOOLEAN,
    created_by STRING,
    created_at STRING,
    PRIMARY KEY (PK, SK)
);
```

## Activity Log

**Used by:** Heartbeat system

```sql
CREATE TABLE activity_log (
    cache_key TEXT PRIMARY KEY,       -- channel_id or chat_id
    webhook_id TEXT,                  -- nullable (HTTP chats have no webhook)
    last_message_at TEXT NOT NULL,    -- ISO timestamp
    last_heartbeat_at TEXT            -- ISO timestamp
);
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `STORE_BACKEND` | `sqlite` | Storage backend type |
| `STORAGE_DB_PATH` | `./data/store.db` | SQLite database path |
| `DIRECTIVE_STORE_ENABLED` | `true` | Enable directive store |
| `DYNAMODB_DIRECTIVES_TABLE` | `if-core` | DynamoDB table for directives |
| `AWS_REGION` | `us-east-1` | AWS region for DynamoDB |

## How to Add a New Backend

1. Create `src/storage/{name}_backend.py`:

```python
class {Name}Store:
    def create(self, record: WebhookRecord) -> WebhookRecord: ...
    def get(self, webhook_id: str) -> WebhookRecord | None: ...
    def list_all(self) -> list[WebhookRecord]: ...
    def list_active(self) -> list[WebhookRecord]: ...
    def deactivate(self, webhook_id: str) -> bool: ...
```

2. Add to factory in `src/storage/factory.py`:

```python
def init_store() -> None:
    backend = config.STORE_BACKEND
    if backend == "your_backend":
        _store = YourBackendStore()
```

## Gotchas

- SQLite uses WAL mode for concurrency
- DynamoDB webhook backend is a stub — use SQLite
- Directive store is separate from webhook store
- Factory pattern allows easy backend switching
