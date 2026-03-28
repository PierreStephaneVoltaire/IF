# Channel System

Multi-platform integration with Discord and OpenWebUI.

## Architecture

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
│    (configurable batching window)                               │
│                │                                                 │
│                ▼                                                 │
│         dispatcher.py                                           │
│                │                                                 │
│      ┌─────────┴─────────┐                                      │
│      ▼                   ▼                                      │
│  discord_translator  openwebui_translator                       │
│      │                   │                                      │
│      └─────────┬─────────┘                                      │
│                │  (text refs + _pending_uploads)                │
│                ▼                                                 │
│    _upload_attachments()  ──► terminal /uploads/                │
│                │                                                 │
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

## Components

### Listener Manager

**File:** `src/channels/manager.py`

```python
def start_listener(record: WebhookRecord) -> None
def stop_listener(webhook_id: str) -> None
def start_all_active(records: list[WebhookRecord]) -> None  # Called at startup
def stop_all() -> None  # Called at shutdown
```

### Discord Listener

**File:** `src/channels/listeners/discord_listener.py`

- Uses `discord.py` client in a dedicated thread
- Listens to a single registered channel
- Ignores bot messages and own messages
- Pushes messages to debounce queue with attachments

### OpenWebUI Listener

**File:** `src/channels/listeners/openwebui_listener.py`

- Polling-based listener (default: 5-second interval)
- Tracks last-seen message ID for incremental updates
- Extracts files and attachments from messages

### Debounce System

**File:** `src/channels/debounce.py`

Thread-safe message batching with configurable window.

**Configuration:**
- `CHANNEL_DEBOUNCE_SECONDS`: Inactivity window (default: 5s)
- Messages are accumulated and flushed after silence period

**Threading Model:**
- Listener threads call `push_message()` from their own event loops
- Uses `threading.Lock` for buffer access
- Schedules timers on main asyncio event loop via `call_soon_threadsafe`

### Translators

**Files:**
- `src/channels/translators/discord_translator.py`
- `src/channels/translators/openwebui_translator.py`

Convert platform messages to `ChatCompletionRequest` format:

```python
def translate_discord_batch(messages: list[dict], conversation_id: str) -> dict:
    # Returns:
    # {
    #     "model": "if-prototype",
    #     "stream": True,
    #     "messages": [{"role": "user", "content": content_parts}],
    #     "_conversation_id": conversation_id,
    #     "_pending_uploads": [{"filename": str, "url": str, "content_type": str}, ...],
    # }
```

- Prepends sender attribution: `[Alice]: message text`
- All attachments (images and non-images) become text references: `[Attachment: filename — uploads/filename]`
- Queues attachment metadata in `_pending_uploads` for the dispatcher to upload to the terminal filesystem
- `_pending_uploads` is stripped from the dict by the dispatcher before the message reaches the completions pipeline

### Attachment Upload (Dispatcher)

**File:** `src/channels/dispatcher.py` — `_upload_attachments()`

After translation, before the completions pipeline, the dispatcher:
1. Pops `_pending_uploads` from the request dict
2. Downloads each file from its source URL (Discord CDN, OpenWebUI, etc.)
3. Uploads the bytes to `/home/user/conversations/{conversation_id}/uploads/{filename}` in the terminal
4. Failures are logged as warnings and never block the pipeline — the text reference remains

The agent sees `[Attachment: filename — uploads/filename]` and can call `read_media` to inspect any file on demand.

### Response Chunker

**File:** `src/channels/chunker.py`

Splits long responses for platform limits.

**Configuration:**
- `CHANNEL_MAX_CHUNK_CHARS`: Max chars per chunk (default: 1500)

**Split Priority:**
1. Paragraph break (`\n\n`)
2. Sentence break (`.\n` or `.`)
3. Newline (`\n`)
4. Space (` `)
5. Hard cut

### Delivery

**File:** `src/channels/delivery.py`

Platform-specific response delivery.

**Discord:**
- Sequential chunk delivery with 0.5s delay
- Files attached to last chunk
- Typing indicator during processing

**OpenWebUI:**
- Single combined message
- Attachments as markdown links

## Webhook Registration

### `POST /v1/webhooks/register`

**Discord:**
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

**OpenWebUI:**
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

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CHANNEL_DEBOUNCE_SECONDS` | `5` | Message batching window |
| `CHANNEL_MAX_CHUNK_CHARS` | `1500` | Max chars per response chunk |
| `OPENWEBUI_POLL_INTERVAL` | `5.0` | OpenWebUI polling interval |
| `MEDIA_UPLOAD_DIR` | `uploads` | Subdirectory within conversation dir for uploaded attachments |

## How to Add a New Platform

1. Create `src/channels/listeners/{platform}_listener.py`:

```python
def start_{platform}_listener(record: WebhookRecord, push_callback: Callable):
    """Start listening to platform. Call push_callback(message_dict) for each message."""
```

2. Create `src/channels/translators/{platform}_translator.py`:

```python
def translate_{platform}_batch(messages: list[dict], conversation_id: str) -> dict:
    """Convert platform messages to ChatCompletionRequest format."""
```

3. Register in `src/channels/manager.py`:

```python
def start_listener(record: WebhookRecord) -> None:
    if record.platform == "your_platform":
        start_your_platform_listener(record, push_message)
```

4. Add delivery method in `src/channels/delivery.py`

## Gotchas

- Each Discord channel requires its own bot connection
- OpenWebUI uses polling, not webhooks
- Debounce prevents message flooding
- Chunking handles Discord's 2000 char limit
