# IF — Discord bot built with OpenHands SDK

A single main agent with context-aware tiering and specialist subagent delegation. Built on the OpenHands SDK, routes through OpenRouter, persists knowledge in LanceDB.

---

## Philosophy: IF vs Traditional Agent Frameworks

Most agent frameworks (OpenAI Agents SDK, LangGraph, CrewAI) follow a **design-time** philosophy: you architect the agent's behavior upfront through careful prompt engineering, define handoffs between agents, and deploy. Changes require code modifications and redeployment.

IF takes an **evolutionary** approach: start with a base agent and let behavior emerge through interaction.

| Aspect | Traditional Frameworks | IF |
|--------|------------------------|-----|
| **Prompt Engineering** | Heavy upfront investment; static instructions baked into code | Iterative refinement; directives stored in DynamoDB, editable at runtime |
| **Iteration Speed** | Slow: edit → commit → test → deploy cycle | Fast: DynamoDB edit → immediate effect |
| **Knowledge Accumulation** | Stateless between sessions (unless you build custom persistence) | Built-in: user facts accumulate, context enriches over time |
| **Behavior Shaping** | Prompt versioning and rollback | Directive versioning + reflection engine auto-detects issues |
| **Personalization** | Generic assistant; custom memory is your problem | Operator context injected automatically from LanceDB facts |
| **Failure Recovery** | Rollback to previous code version | Directive rollback + metacognitive triggers |
| **Learning** | None (you redesign prompts) | Reflection engine, opinion formation, capability gap tracking |

### The Incremental Advantage

Traditional: *"Let me design the perfect system prompt, define all handoffs, and ship it."*

IF: *"Here's a base agent. Through conversation, it will learn the operator's preferences, accumulate context, and I can nudge its behavior with directive edits without touching code."*

This makes IF better suited for:
- **Long-running relationships** where the agent should learn and adapt
- **Solo operators** who want a personalized assistant without building custom memory systems
- **Rapid iteration** where you want to shape behavior through interaction, not prompt engineering sessions

The trade-off: IF requires more infrastructure (DynamoDB, LanceDB, Docker) and has higher complexity. Traditional frameworks are simpler to get started with but remain static unless you build your own persistence layer.

---


## Core Components

### Agent System
Single main agent using OpenHands SDK with automatic context-based tiering (air → standard → heavy) and specialist subagent delegation.

### Tiering System
Context-aware model selection based on conversation size:
- **Air**: Simple queries (< 30K tokens)
- **Standard**: Most conversations (< 120K tokens)
- **Heavy**: Complex tasks (< 200K tokens)

### Specialist Subagents

Domain experts spawned by the main agent for deep tasks. Each specialist has its own prompt template, filtered directives, and tool access.

#### Code & Infrastructure

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `debugger` | Deep code debugging and error analysis | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `architect` | System design and architecture patterns | `read_file`, `write_file`, `search_files` + AWS docs MCP |
| `secops` | Security operations and vulnerability analysis | `terminal_execute`, `read_file`, `search_files` |
| `devops` | Infrastructure and deployment automation | `terminal_execute`, `read_file`, `write_file` |

#### Writing & Communication

| Specialist | Purpose | Use Case |
|------------|---------|----------|
| `proofreader` | Prose editing, grammar, clarity, tone | General text improvement |
| `email_writer` | Professional email drafting | Formal tone, sensitive subjects |
| `jira_writer` | Jira ticket creation | Structured issues with acceptance criteria |
| `constrained_writer` | Character-limited content | Tweets (280), Discord, SMS, Bluesky (300) |

#### Domain-Specific

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `health_write` | Training program mutations (log sessions, update RPE, body weight) | Health DynamoDB tools |
| `finance_write` | Finance snapshot mutations (balances, holdings, goals) | Finance DynamoDB tools |
| `financial_analyst` | Market research and financial analysis | Yahoo Finance + Alpha Vantage MCPs |
| `web_researcher` | Web research and information synthesis | `read_file`, `write_file` |
| `media_reader` | On-demand file and image analysis | Vision model (single turn) |

#### Skills (Mode Modifiers)

Specialists can be invoked with skill modes that change their perspective:

| Skill | Effect |
|-------|--------|
| `red_team` | Adversarial/attack perspective |
| `blue_team` | Defensive/protection perspective |
| `pro_con` | Balanced pros and cons analysis |

Example: `spawn_specialist(specialist_type="architect", skill="red_team")` produces an adversarial architecture review.

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
