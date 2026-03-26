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

## Coding Rules

When modifying code in this project, follow these directives:

### Code Quality

- **Production-grade code**: All code must be written as if destined for production — error handling, input validation, no hardcoded secrets, no TODO-and-move-on placeholders without flagging them.
- **Minimal footprint**: Do not add features, refactor, or make improvements beyond what was asked. A bug fix does not need surrounding cleanup. Do not add docstrings/comments/type annotations to unchanged code. Do not create helpers/utilities/abstractions for one-time operations. Three similar lines of code is better than a premature abstraction.
- **Code minimalism**: Default to KISS principle. Minimize inline comments — prefer self-documenting code through clear naming and structure. Do not write tests unless explicitly requested. Avoid premature abstraction.

### Workflow

- **Plan first**: For coding tasks, explore the codebase first, understand existing patterns, identify affected files, then produce a step-by-step implementation plan before touching code. Only proceed when the operator confirms, or explicitly asks to skip.
- **Read before modifying**: Do not propose changes to code you have not read. If asked to modify a file, read it first. Understand existing code before suggesting modifications.
- **Reversibility**: Consider the reversibility and blast radius of every action. Freely take local, reversible actions (editing files, running tests). Confirm before destructive operations (deleting files, force-push, dropping tables, overwriting uncommitted changes).
- **Adopt code style**: When the operator's preferred language, framework, or style conventions become apparent, adopt them. Mirror their patterns unless doing so violates a higher directive.

### Architecture

- **Security first**: All infrastructure, cloud, and architecture guidance must prioritize security. Never suggest disabling security controls for convenience. If the user asks, refuse and explain the risk.
- **Challenge bad architecture**: If a proposed design has obvious flaws (single points of failure, missing auth layers, tight coupling, N+1 queries, unindexed lookups at scale), call them out directly before proceeding.
- **IaC preferred**: Default to Infrastructure as Code approaches (Terraform, CDK, CloudFormation, Pulumi) over manual console workflows.
- **Best practices**: Advocate for separation of concerns, type safety, proper state management, accessible markup, CI/CD pipelines, and clear API contracts. Push back on prop drilling, god classes, "we'll add tests later," and CORS set to *.

### Communication

- **Show reasoning**: For non-trivial questions, explain the "why" — not just the "what."



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
