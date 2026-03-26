# Terminal System

Persistent Docker containers for command execution and file operations.

**Modules:**
- `src/terminal/__init__.py` — Module exports
- `src/terminal/config.py` — Configuration dataclass
- `src/terminal/static_client.py` — Static terminal manager (singleton lifecycle)
- `src/terminal/client.py` — HTTP client for terminal API
- `src/terminal/files.py` — File reference handling

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    TERMINAL SYSTEM                                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               StaticTerminalManager                       │    │
│  │                                                           │    │
│  │  - Connects to pre-deployed terminal instance (HTTP)     │    │
│  │  - Conversation-scoped working directories               │    │
│  │  - /home/user/conversations/{chat_id}                    │    │
│  │  - Initialized when TERMINAL_API_KEY is configured       │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   TerminalClient                          │    │
│  │                                                           │    │
│  │  - HTTP API to container exec endpoint                    │    │
│  │  - Command execution with timeout                         │    │
│  │  - File listing and reading operations                    │    │
│  │  - Output truncation for large responses                  │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│              ┌──────────────┴──────────────┐                    │
│              ▼                             ▼                    │
│  ┌────────────────────┐        ┌────────────────────┐          │
│  │  Terminal Tools    │        │   Files Handling   │          │
│  │                    │        │                    │          │
│  │  terminal_execute  │        │  strip_files_line  │          │
│  │  terminal_list_    │        │  FilesStripBuffer  │          │
│  │    files           │        │  FileRef           │          │
│  │  terminal_read_    │        │  log_file_refs     │          │
│  │    file            │        │                    │          │
│  │  terminal_write_   │        │                    │          │
│  │    file            │        │                    │          │
│  └────────────────────┘        └────────────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

## Terminal Tools

**Module:** `src/agent/tools/terminal_tools.py`

| Tool | Description |
|------|-------------|
| `terminal_execute` | Execute shell command with optional timeout and working directory |
| `terminal_list_files` | List files in a directory |
| `terminal_read_file` | Read file contents |
| `terminal_write_file` | Write content to a file |

## FILES: Line Handling

The terminal system includes special handling for file references in agent output:

- `FILES:` lines in responses are stripped from visible output
- File references are logged for tracking generated artifacts
- `FilesStripBuffer` class handles streaming output

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TERMINAL_URL` | `http://open-terminal:7681` | Terminal API URL |
| `TERMINAL_API_KEY` | `""` | API key for terminal authentication |
| `TERMINAL_VOLUME_HOST_ROOT` | `""` | Host path for Docker volume access |

## Working Directories

Each conversation gets its own working directory:

```
/home/user/conversations/{conversation_id}/
```

This ensures isolation between different sessions and users.

## Usage Examples

### Execute a command

```python
terminal_execute(
    command="ls -la",
    working_dir="/home/user/conversations/abc123"
)
```

### Write a file

```python
terminal_write_file(
    path="/home/user/conversations/abc123/output.py",
    content="# Generated code\nprint('hello')"
)
```

### Read a file

```python
terminal_read_file(
    path="/home/user/conversations/abc123/output.py"
)
```

## How to Extend

### Add a new terminal tool

1. Edit `src/agent/tools/terminal_tools.py`
2. Add new function with docstring
3. Register in `register_terminal_tools()`

### Modify file handling

1. Edit `src/terminal/files.py`
2. Adjust `FilesStripBuffer` or add new utilities

## Gotchas

- Terminal must be pre-deployed and accessible at `TERMINAL_URL`
- Commands run in container context, not host
- File paths are relative to container filesystem
- Large output is truncated — check logs if output seems incomplete
- `TERMINAL_API_KEY` must be configured for terminal access
