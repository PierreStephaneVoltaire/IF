# IF — Intelligent Agent API

## What This Is

A single main agent with context-aware tiering and specialist subagent delegation, built on the OpenHands SDK. Routes through OpenRouter. Persists knowledge in LanceDB.

## Tech Stack

- Python 3.12, FastAPI, OpenHands SDK
- LanceDB (user facts), SQLite (webhooks, activity), DynamoDB (directives)
- Docker terminal containers for shell access
- MCP servers for extended capabilities

## How to Run

```bash
cd app
pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Project Layout

```
app/
├── src/
│   ├── api/           # FastAPI endpoints (completions, webhooks, directives, files)
│   ├── agent/         # Agent session, tiering, specialists, tools, reflection
│   ├── channels/      # Discord + OpenWebUI listeners, translators, delivery
│   ├── memory/        # LanceDB user facts, embeddings, summarizer
│   ├── storage/       # SQLite + DynamoDB backends
│   ├── terminal/      # Docker container shell access
│   ├── orchestrator/  # Multi-step plan execution, parallel analysis
│   ├── presets/       # Static preset definitions
│   ├── mcp_servers/   # MCP server config
│   ├── heartbeat/     # Proactive engagement
│   └── health/        # Fitness module (DynamoDB + ChromaDB RAG)
└── utils/             # TypeScript utility apps (portals)
```

## Conventions

- All agent tools are in `app/src/agent/tools/` as Python functions
- Specialist templates are Jinja2 files in `app/src/agent/prompts/specialists/`
- New specialists: add to `specialists.py` registry + create `.j2` template
- Presets are static (loaded at startup from `app/src/presets/loader.py`)
- Directives are dynamic (DynamoDB, loaded into memory cache)
- User facts use LanceDB with all-MiniLM-L6-v2 embeddings
- Environment config lives in `app/src/config.py` (dataclass with defaults)

## Key Patterns

- Subagent spawning: `spawn_specialist(type, task, context)` in `app/src/agent/tools/subagents.py`
- Tool authoring: Python function with docstring → registered in `app/src/agent/session.py`
- System prompt assembly: Jinja2 template + directives + operator context + addenda
- All channel messages flow through: listener → debounce → dispatcher → translator → completions pipeline

## Related Docs

See `.claude/` folder for detailed docs on each subsystem:

| Task | Read |
|------|------|
| Add a new specialist | [specialists.md](specialists.md) |
| Fix a bug in the channel system | [channels.md](channels.md) |
| Add a new tool to the agent | [tools.md](tools.md) |
| Modify the tiering logic | [presets.md](presets.md) |
| Add a new fact category | [memory.md](memory.md) |
| Change reflection behavior | [metacognition.md](metacognition.md) |
| Add a new directive | [directives.md](directives.md) |
| Fix terminal container issue | [terminal.md](terminal.md) |
| Add a new channel listener | [channels.md](channels.md) |
| Understand the full request flow | [architecture.md](architecture.md) |
| Work with the orchestrator | [orchestrator.md](orchestrator.md) |
| Understand storage backends | [storage.md](storage.md) |
| Modify heartbeat behavior | [heartbeat.md](heartbeat.md) |
| Work with utility apps | [portals.md](portals.md) |
