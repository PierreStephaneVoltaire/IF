# IF — Intelligent Agent API

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
- **Air**: Simple queries (< 100K tokens)
- **Standard**: Most conversations (< 200K tokens)
- **Heavy**: Complex tasks (≥ 200K tokens)

### Specialist Subagents

Domain experts spawned by the main agent for deep tasks. Each specialist has its own prompt template, filtered directives, and tool access. Auto-discovered from YAML configs — no code changes needed to add specialists.

#### Code & Infrastructure

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `coder` | General software engineering — writing code, features, modifications | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `scripter` | Quick tasks completable in 3-5 commands (max 3 turns) | `terminal_execute`, `read_file`, `write_file` |
| `debugger` | Deep code debugging and error analysis | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `architect` | System design and architecture patterns | `read_file`, `write_file`, `search_files` + AWS docs MCP |
| `secops` | Security operations and vulnerability analysis | `terminal_execute`, `read_file`, `search_files` |
| `devops` | Infrastructure and deployment automation | `terminal_execute`, `read_file`, `write_file` |
| `file_generator` | Structured file generation with syntax validation (scripts, configs, IaC, code modules) — agentic loop, validates syntax before delivery | `terminal_execute`, `write_file`, `read_file`, `terminal_list_files` |
| `git_ops` | Git operations — rebasing, conflict resolution, PR workflows, history rewriting | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `code_reviewer` | Structured code review — correctness, security, performance, maintainability | `terminal_execute`, `read_file`, `search_files` |
| `code_explorer` | Codebase navigation, dependency mapping, "how does X work?" | `terminal_execute`, `read_file`, `search_files` |
| `doc_generator` | Technical documentation — READMEs, ADRs, RFCs, API docs, runbooks | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `test_writer` | Test generation — unit, integration, edge cases (agentic: GENERATE→RUN→FIX→VERIFY) | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `refactorer` | Code refactoring without behavior change — extract, rename, decouple | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `api_designer` | REST/GraphQL/gRPC API design, OpenAPI specs | `read_file`, `write_file`, `search_files` |
| `migration_planner` | Database/infrastructure migration planning with rollback strategies | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `incident_responder` | Production incident triage — fast, action-first, no preamble | `terminal_execute`, `read_file`, `search_files` |
| `performance_analyst` | Performance profiling, optimization — MEASURE→IDENTIFY→OPTIMIZE→VERIFY | `terminal_execute`, `read_file`, `write_file`, `search_files` |

#### Reasoning & Planning

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `planner` | Decomposes goals into sequenced, dependency-aware plans (produces plans; does not execute) | `read_file`, `write_file`, `search_files` |
| `dialectic` | Structured adversarial reasoning — thesis-antithesis-synthesis | `read_file` |
| `decision_analyst` | Multi-criteria decision analysis with weighted scoring and tradeoff matrices | `write_file` |

#### Project & Task Management

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `project_manager` | Implementation verification — confirms planned work exists in codebase | `terminal_execute`, `read_file`, `search_files` |
| `todo_generator` | Extracts actionable task lists from conversations and documents | `read_file`, `write_file` |

#### Communication & Writing

| Specialist | Purpose | Use Case |
|------------|---------|----------|
| `proofreader` | Prose editing, grammar, clarity, tone | General text improvement |
| `email_writer` | Professional email drafting | Formal tone, sensitive subjects |
| `jira_writer` | Jira ticket creation | Structured issues with acceptance criteria |
| `constrained_writer` | Character-limited content | Tweets (280), Discord, SMS, Bluesky (300) |
| `interviewer` | Requirements gathering through structured questioning | Underspecified requests |
| `summarizer` | Condensing long content into structured summaries | Documents, threads, transcripts |
| `meeting_prep` | Meeting preparation — talking points, background research | Pre-meeting briefings |
| `negotiation_advisor` | Negotiation strategy — BATNA analysis, concession planning | Salary, contracts, vendors |

#### Document Generation

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `resume` | Resume tailoring via LaTeX, JD analysis, compile to PDF | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `cover_letter` | Cover letter generation — JD-specific, one page max | `terminal_execute`, `read_file`, `write_file` |
| `workday` | Workday/ATS application form input — copy-paste-ready text blocks | `read_file`, `write_file` |
| `pdf_generator` | Formatted PDF creation via WeasyPrint/Pandoc/LaTeX | `terminal_execute`, `read_file`, `write_file` |
| `changelog_writer` | Release notes and changelogs from git history | `terminal_execute`, `read_file`, `write_file` |

#### Analytical

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `data_analyst` | Data exploration, analysis, visualization — CSV, JSON, logs | `terminal_execute`, `read_file`, `write_file`, `search_files` |
| `legal_reader` | Contract, ToS, and policy analysis — NOT legal advice | `read_file` |
| `prompt_engineer` | Writing, refining, and testing prompts for LLMs | `read_file`, `write_file`, `search_files` |
| `sql_analyst` | Database query specialist — optimization, schema analysis | `terminal_execute`, `read_file`, `write_file` |

#### Learning & Education

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `math_tutor` | Mathematics instruction — algebra, calculus, linear algebra, ML/AI math | `write_file` |
| `language_tutor` | Language learning — Japanese, Spanish, French | `write_file` |
| `ml_tutor` | ML/AI instruction — architectures, training, practical implementation | `terminal_execute`, `read_file`, `write_file` |

#### Career

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `career_advisor` | Career strategy — trajectory analysis, skill gaps, market positioning | `write_file`, user facts |

#### Meta & System

| Specialist | Purpose | Tools |
|------------|---------|-------|
| `consensus_builder` | Multi-source synthesis — spawns 2-3 specialists, collects, synthesizes | `spawn_specialist(s)`, `write_file` |
| `self_improver` | Analyzes IF's own performance, proposes directive/prompt improvements | `read_file`, `write_file`, `search_files` |

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
| `steelman` | Strongest possible version of a given position |
| `devils_advocate` | Deliberately attacks the operator's preferred option |
| `backcast` | Start from desired outcome, work backward |
| `rubber_duck` | Ask questions instead of answers — force articulation |
| `eli5` | Explain like I'm five — simplify maximally |
| `formal` | Formal/professional register for external output |
| `speed` | Compressed output, skip rationale, action-only |
| `teach` | Explain the why alongside the what — educational mode |

Example: `spawn_specialist(specialist_type="architect", skill="red_team")` produces an adversarial architecture review.

### Delegation Pipeline

Automatic message routing: categorize → directives → condense → spawn. The main agent classifies each message domain, retrieves filtered directives, rewrites the intent, and routes to the appropriate specialist subagent.

### Memory System
- **User Facts Store**: LanceDB with semantic search for operator context (22 fact categories)
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

Docker containers for shell access. Each conversation gets isolated working directory at `/home/user/conversations/{chat_id}/`. Tools: `terminal_execute`, `terminal_read_file`, `terminal_write_file`, `terminal_list_files`.

Two client modes: dynamic (`TerminalClient` — per-conversation containers) and static (`StaticTerminalManager` — single shared deployment managed via IaC, Kubernetes-friendly).

---

## MCP Servers

Extended capabilities via MCP servers:
- `time` — Current date/time
- `aws_docs` — AWS documentation lookup
- `yahoo_finance` — Stock quotes
- `alpha_vantage` — Financial indicators

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

