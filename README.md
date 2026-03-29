# IF — Discord bot built with OpenHands SDK

A single main agent with context-aware tiering and specialist subagent delegation. Built on the OpenHands SDK, routes through OpenRouter, persists knowledge in LanceDB.


## Core Components

### Agent System
Single main agent using OpenHands SDK with automatic context-based tiering (air → standard → heavy) and specialist subagent delegation.

### Tiering System
Context-aware model selection based on conversation size:
- **Air**: Simple queries (< 30K tokens)
- **Standard**: Most conversations (< 120K tokens)
- **Heavy**: Complex tasks (< 200K tokens)

### Specialist Subagents
Domain experts spawned by the main agent for deep tasks:

| Specialist | Purpose |
|------------|---------|
| `debugger` | Code debugging and error analysis |
| `architect` | System design and architecture |
| `secops` | Security operations and vulnerabilities |
| `devops` | Infrastructure and deployment |
| `financial_analyst` | Financial data and market research |
| `web_researcher` | Web research and synthesis |
| `proofreader` | Prose editing and review |
| `health_write` | Training program mutations |
| `finance_write` | Finance snapshot mutations |

### Memory System
- **User Facts Store**: LanceDB with semantic search for operator context
- **Metacognitive Layer**: Pattern detection, opinion formation, growth tracking
- **Reflection Engine**: Post-session analysis and self-improvement

---

## Channels

| Platform | Type | Description |
|----------|------|-------------|
| Discord | Bot | Listen to registered channels |
| OpenWebUI | Polling | Chat interface integration |
| HTTP API | REST | Direct API access |

Messages flow through: listener → debounce → translator → agent → chunker → delivery.

---

## Storage

| Store | Backend | Purpose |
|-------|---------|---------|
| User Facts | LanceDB | Operator context with semantic search |
| Webhooks | SQLite | Channel registration and activity |
| Directives | DynamoDB | Behavioral rules with versioning |
| Health | DynamoDB + ChromaDB | Training programs with RAG |
| Finance | DynamoDB | Financial snapshots |

---

## Terminal System

Docker containers for shell access. Each conversation gets isolated working directory. Tools: `terminal_execute`, `terminal_read_file`, `terminal_write_file`, `terminal_list_files`.

---

## MCP Servers

Extended capabilities via MCP servers:
- `time` — Current date/time
- `aws_docs` — AWS documentation lookup
- `yahoo_finance` — Stock quotes
- `alpha_vantage` — Financial indicators
- `google_sheets` — Spreadsheet access

---

## Heartbeat System

Proactive engagement after idle periods. Monitors channel activity and initiates pondering conversations after configurable idle threshold.

---

## Directive System

Versioned behavioral directives stored in DynamoDB. Tiered by priority (0-5), with content rewriting for consistent voice.

---


## Commands

Registered as Discord guild slash commands (autocomplete) and also work as plain text messages.

| Command | Action |
|---------|--------|
| `/end_convo` | Clear conversation state and force reclassification |
| `/clear [amount]` | Delete recent messages from channel (default 100, requires Manage Messages) |
| `/pondering` | Enter reflective conversation mode (heavy tier) |
| `/reflect` | Trigger manual reflection cycle |
| `/gaps [min_triggers]` | List capability gaps ranked by priority |
| `/patterns` | Show detected behavioral patterns |
| `/opinions` | Show opinion pairs (operator vs agent positions) |
| `/growth [days]` | Show operator growth report (default 30 days) |
| `/meta` | Show store health metrics and category suggestions |
| `/tools` | Show tool suggestions from capability gaps |

---

## Environment Variables

Key configuration (see `app/src/config.py` for full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | required | API key for model access |
| `TIER_UPGRADE_THRESHOLD` | 0.65 | Context fraction before upgrade |
| `HEARTBEAT_ENABLED` | true | Enable proactive engagement |
| `HEARTBEAT_IDLE_HOURS` | 6.0 | Hours idle before heartbeat |
| `DIRECTIVE_STORE_ENABLED` | true | Enable DynamoDB directives |
| `TERMINAL_API_KEY` | | Terminal authentication key |

---

## Utility Applications

TypeScript/Node.js apps in `app/utils/`:

| App | Port | Purpose |
|-----|------|---------|
| Hub | 3000 | Central dashboard aggregating all portals |
| Finance | 3002 | Net worth, investments, cashflow tracking |
| Diary | 3003 | Mental health journaling and signals |
| Proposals | 3004 | Kanban for agent-proposed directives |
| Powerlifting | 3005 | Training tracking and analytics |

---


## License

MIT
