# IF — Intelligent Agent API

A single main agent with context-aware tiering and specialist subagent delegation, built on the OpenHands SDK. Routes through OpenRouter with a dynamic model registry and smart model router. Persists knowledge in LanceDB. Behavior evolves through runtime directives stored in DynamoDB.

## Tech Stack

- Python 3.12, FastAPI, OpenHands SDK 1.11.4
- LanceDB (user facts, all-MiniLM-L6-v2 embeddings), ChromaDB (health docs RAG)
- SQLite (webhooks, activity via SQLModel), DynamoDB (directives, health, finance, diary, proposals, models)
- Docker terminal containers for shell access (via OpenTerminal)
- MCP servers for extended capabilities (time, AWS docs, Yahoo Finance, Alpha Vantage)
- Kubernetes deployment via Terraform, Docker images via Packer

## How to Run

```bash
cd app
pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Requires `OPENROUTER_API_KEY` in environment (or `.env` file). See `app/src/config.py` for full configuration.

## Project Layout

```
app/
├── src/
│   ├── main.py              # FastAPI app entry point, lifespan init
│   ├── config.py            # All env vars (plain module-level, os.getenv defaults)
│   ├── logging_config.py    # Centralized logging configuration
│   ├── api/                 # FastAPI routers
│   │   ├── completions.py   # POST /v1/chat/completions (OpenAI-compatible)
│   │   ├── models.py        # GET /v1/models
│   │   ├── files.py         # File serving from sandbox
│   │   ├── webhooks.py      # Channel registration
│   │   ├── directives.py    # Directive CRUD API
│   │   └── admin.py         # POST /admin/reload-tools (hot reload)
│   ├── agent/               # Core agent system
│   │   ├── session.py       # AgentSession, system prompt assembly, execute_agent()
│   │   ├── tool_registry.py # External tool plugin discovery, loading, indexing
│   │   ├── specialists.py   # YAML-based specialist auto-discovery + rendering
│   │   ├── tiering.py       # Context-aware model selection (air/standard/heavy)
│   │   ├── condenser.py     # Conversation summarization
│   │   ├── commands.py      # Slash command definitions
│   │   ├── memory_tools.py  # ChromaDB memory search/add/remove/list
│   │   ├── prompts/         # Jinja2 templates + specialist definitions
│   │   │   ├── system_prompt.j2
│   │   │   ├── delegation.yaml   # Category→specialist + category→directive mapping
│   │   │   └── mcp_servers.yaml   # MCP server command definitions
│   │   ├── reflection/      # Metacognitive layer
│   │   │   ├── engine.py           # ReflectionEngine (periodic, post-session, on-demand)
│   │   │   ├── pattern_detector.py # Behavioral pattern detection
│   │   │   ├── opinion_formation.py
│   │   │   ├── meta_analysis.py
│   │   │   └── growth_tracker.py
│   │   └── tools/           # OpenHands SDK tools (Action/Observation/Executor/ToolDefinition)
│   │       ├── tool_schemas.py     # Registry-backed schema resolution for specialists
│   │       ├── discovery_tools.py  # discover_tools + use_tool system tools
│   │       └── base.py             # TextObservation base class
│   ├── models/              # Dynamic model routing
│   │   ├── loader.py        # ModelPresetManager (subagents) + TierConfigManager (tiers)
│   │   └── router.py        # Smart model selection via fast LLM
│   ├── channels/            # Multi-platform message handling
│   │   ├── dispatcher.py    # Message flow bridge (translate → agent → chunk → deliver)
│   │   ├── delivery.py      # Send responses back to platforms
│   │   ├── chunker.py       # Split responses into 1500-char chunks
│   │   ├── debounce.py      # 5-second message batching window
│   │   ├── manager.py       # Listener lifecycle management
│   │   ├── context.py       # Platform context var for status embed threading
│   │   ├── status.py        # Discord status embed system
│   │   ├── slash_commands.py
│   │   ├── listeners/       # discord_listener.py, openwebui_listener.py
│   │   └── translators/     # discord_translator.py, openwebui_translator.py
│   ├── memory/              # Persistent memory
│   │   ├── user_facts.py    # UserFact dataclass + UserFactStore (LanceDB-backed)
│   │   ├── lancedb_store.py # LanceDB table management, context-scoped storage
│   │   ├── store.py         # Legacy ChromaDB MemoryStore
│   │   ├── embeddings.py    # Sentence transformer embedding generation
│   │   └── summarizer.py    # Conversation summarization (fire-and-forget)
│   ├── storage/             # Storage abstraction
│   │   ├── factory.py       # Backend factory (webhooks, directives, model registry)
│   │   ├── sqlite_backend.py    # SQLite (WAL mode) for webhooks
│   │   ├── dynamodb_backend.py  # DynamoDB stub
│   │   ├── directive_store.py   # DynamoDB directive storage + cache
│   │   └── model_registry.py    # DynamoDB model metadata registry + cache
│   ├── routing/             # Request routing
│   │   ├── interceptor.py   # Bypass routing
│   │   ├── cache.py         # Conversation cache
│   │   └── commands.py      # Command parsing (/reset, /pondering, /reflect, etc.)
│   ├── terminal/            # Docker container shell access
│   │   ├── client.py        # TerminalClient for API calls
│   │   ├── static_client.py # StaticTerminalManager (shared OpenTerminal deployment)
│   │   ├── files.py         # File operations on terminal volumes
│   │   └── config.py        # Terminal URL, API key, volume paths
│   ├── orchestrator/        # Multi-step task execution
│   │   ├── executor.py      # execute_plan tool (sequential steps with subagents)
│   │   └── analyzer.py      # analyze_parallel tool (parallel perspective analysis)
│   ├── presets/             # OpenRouter preset definitions (legacy, still active)
│   │   └── loader.py        # PresetManager (loaded at startup)
│   ├── mcp_servers/         # MCP server config
│   │   └── config.py        # PRESET_MCP_MAP, server resolution
│   ├── heartbeat/           # Proactive engagement
│   │   ├── runner.py        # Idle detection, cooldown, quiet hours
│   │   └── activity.py      # Activity log queries
│   └── health/              # Fitness/training module
│       ├── program_store.py # DynamoDB program storage
│       ├── rag.py           # ChromaDB RAG for PDF documents (IPF rulebook, etc.)
│       ├── renderer.py      # Program rendering
│       └── tools.py         # Health CRUD functions (called by tool plugin)
├── docker/                  # Packer build files (.pkr.hcl)
├── terraform/               # Kubernetes, AWS infra
└── main_system_prompt.txt   # Agent personality base prompt
specialists/                 # One subdir per specialist (specialist.yaml + agent.j2)
models/                       # Dynamic model routing config
├── presets.yaml             # Subagent preset definitions (YAML)
├── tiers.yaml               # Internal tier config (air/standard/heavy + media)
└── model_ids.txt            # Newline-delimited model IDs to track
tools/                       # External tool plugins (one subdir per plugin)
├── health/                  # Training program management (35 tools)
├── finance/                 # Financial profile and investments (21 tools)
├── diary/                   # Write-only diary entries and signals
└── proposals/              # Agent-proposed directives (4 tools)
utils/                       # TypeScript/Node.js utility apps
├── main-portal/             # Hub dashboard (port 3000)
├── finance-portal/          # Net worth, investments (port 3002)
├── diary-portal/            # Mental health journaling (port 3003)
├── proposals-portal/        # Directive proposal kanban (port 3004)
├── powerlifting-app/        # Training tracking (port 3005)
└── video-lambda/            # Lambda function for video processing
```

## Architecture

```
Client (Discord / OpenWebUI / HTTP)
  → Channel Listener
    → Debounce (5s batching)
      → Dispatcher (translate to ChatCompletionRequest, set platform context)
        → Completions Pipeline
          → Command parsing (/reset, /pondering, /reflect, etc.)
          → Interceptor (bypass routing)
          → Tier tracking (context token estimation)
          → Model routing (tier-based model selection via ModelRegistry)
          → Session creation (with model_override from router)
            → System prompt assembly:
                base prompt + directives + operator context (LanceDB facts)
                + signals (diary, financial) + addenda
          → Agent execution (OpenHands SDK → OpenRouter)
            → Delegation pipeline
              → categorize_conversation → get_directives → condense_intent
              → spawn_subagent (model routing via fast LLM)
                → Specialist execution (agentic SDK or raw OpenRouter)
                  → Tool execution (with Discord status embeds)
          → Response extraction (FILES: metadata stripping)
        → Chunker (1500 char chunks)
      → Delivery (back to platform)
```

### Request Processing (completions.py)

`process_chat_completion_internal()` is the core pipeline:
1. Resolve `cache_key` (from webhook channel_id, chat_id, or content hash) and `context_id`
2. Parse slash commands (`/reset`, `/pondering`, `/reflect`, `/gaps`, `/patterns`, `/opinions`, `/growth`, `/meta`, `/tools`)
3. Run interceptor for bypass routing
4. Track tier with context token estimation
5. Resolve concrete model for the tier via `select_model_for_tier()` (returns first model in tier's sorted list)
6. Create session with `model_override` and signals injection
7. Execute agent via OpenHands SDK
8. Extract file attachments from `FILES:` metadata
9. Trigger async conversation summarization

### System Prompt Assembly (session.py)

`assemble_system_prompt()` builds the complete prompt from:
1. Current signals (mental health, life load, training status from `context_tools.py`)
2. Base personality prompt (`main_system_prompt.txt`)
3. Operator context from user facts (LanceDB)
4. Conversation history
5. Directives from DynamoDB DirectiveStore
6. Memory protocol instructions
7. Media protocol instructions
8. Terminal environment instructions
9. Pondering addendum (if in pondering mode)

## Model Router

Dynamic model selection replacing rigid OpenRouter `@preset/` references with concrete model IDs, controlled via YAML config and a fast routing LLM.

### Model Registry (`storage/model_registry.py`)

DynamoDB-backed registry (`if-models` table, PK=`MODEL`, SK=model_id) storing metadata for OpenRouter models. Populated from the OpenRouter API via the seed script.

**ModelInfo fields**: model_id, context_size, max_output_tokens, input/output pricing (per-provider), input/output modalities, tool_support, caching_support, zero_data_retention, throughput, latency.

**Seeding**: `python scripts/seed_models.py [--models-file models/model_ids.txt]` — fetches all models from OpenRouter, filters to the input list (skipping models without tool support), upserts to DynamoDB. Also fetches per-provider latency/throughput from `/api/v1/models/{id}/endpoints` (min p50 latency, max p50 throughput across providers). Runs automatically at startup to refresh metadata.

**Periodic stats refresh**: Background task in `main.py` calls `ModelRegistry.refresh_endpoint_stats()` every `MODEL_STATS_REFRESH_INTERVAL` seconds (default 1800 / 30 min) to keep latency/throughput data current. Updates both DynamoDB and the in-memory cache.

**Sorting strategies**: `price_asc`, `price_desc`, `latency_asc`, `context_size_desc`, `throughput_desc`.

### Model Presets (`models/presets.yaml`)

YAML config defining **subagent presets only** (mapped from specialist `@preset/` references). Auto-loaded at startup via `ModelPresetManager`.

```yaml
presets:
  code:
    models: [anthropic/claude-sonnet-4, google/gemini-2.5-pro]
    sort_by: price_asc
    when: "Code generation, debugging, code review"
```

### Tier Config (`models/tiers.yaml`)

Separate YAML config for **internal tier selection** — not used for subagents. Auto-loaded at startup via `TierConfigManager`.

```yaml
tiers:
  air:
    models: [openai/gpt-5.4-nano, google/gemma-4-26b-a4b-it]
    sort_by: throughput_desc
    context_limit: 150000
  standard:
    models: [anthropic/claude-sonnet-4.6, google/gemini-3.1-pro-preview]
    sort_by: latency_asc
    context_limit: 200000
  heavy:
    models: [anthropic/claude-opus-4.6, openai/gpt-5.4]
    sort_by: price_asc
    context_limit: 1000000

media_tiers:
  air:
    models: [anthropic/claude-haiku-4.5, google/gemini-3-flash-preview]
    sort_by: price_asc
  standard:
    models: [anthropic/claude-sonnet-4.6, google/gemini-3.1-pro-preview]
    sort_by: price_asc
  heavy:
    models: [anthropic/claude-opus-4.6, google/gemini-4-31b-it]
    sort_by: context_size_desc
```

### Smart Selection (`models/router.py`)

Two selection paths:

**Main agent** (`select_model_for_tier`): Maps tier number (0/1/2) to `TierConfigManager` tier config, returns first model in the sorted list. No LLM call — tier selection itself is the routing decision.

**Subagents** (`select_model_for_specialist`): Maps specialist's `@preset/X` reference to a `ModelPresetManager` preset, then uses a fast LLM (`MODEL_ROUTER_MODEL`, default `google/gemma-3-4b-it`) to select the best model from the preset's candidate list based on the condensed task intent and model metadata. Falls back to first sorted model if router is disabled or fails.

**Media** (`media_tools.py`): Uses `TierConfigManager.get_media_tier()` to pick a vision-capable model from the media tier pool, sorted by the tier's strategy.

**Fallback**: If `MODEL_ROUTER_ENABLED=false`, the YAML preset doesn't exist, or the model registry is empty, the system falls back to the original `@preset/` reference (backward compatible).

## Agent System

### Tiering

Context-aware model selection based on conversation size:
- **Air**: Simple queries (< 150K tokens), models from `models/tiers.yaml` `tiers.air`
- **Standard**: Most conversations (< 200K tokens), models from `tiers.standard`
- **Heavy**: Complex tasks (≥ 200K tokens), models from `tiers.heavy`

Media tiers (vision-capable models) are selected when the conversation contains images/files.

Upgrade at 65% capacity (`TIER_UPGRADE_THRESHOLD`). Context estimated at ~4 chars per token. The concrete model for each tier is resolved from the `TierConfigManager` + `ModelRegistry` using the tier's `sort_by` strategy.

### Specialists

Domain experts spawned by the main agent. Each has its own `specialist.yaml` config and `agent.j2` prompt template. Auto-discovered from `specialists/*/specialist.yaml` at import time — no Python changes needed to add a specialist.

| Specialist | Purpose | Tools | Preset |
|------------|---------|-------|--------|
| `coder` | General software engineering | terminal_execute, read/write/search files | `@preset/code` |
| `scripter` | Quick tasks (3-5 commands), max 3 turns | terminal_execute, read/write files | `@preset/code` |
| `debugger` | Deep code debugging and error analysis | terminal_execute, read/write/search files | standard |
| `architect` | System design and architecture patterns | read/write/search files + AWS docs MCP | standard |
| `secops` | Security operations and vulnerability analysis | terminal_execute, read/search files | standard |
| `devops` | Infrastructure and deployment automation | terminal_execute, read/write files | standard |
| `file_generator` | Structured file generation with syntax validation — scripts, configs, IaC, code modules. `agentic: true` | terminal_execute, write/read files | `@preset/code` |
| `git_ops` | Git operations — rebasing, conflict resolution, PR workflows, history rewriting. `agentic: true` | terminal_execute, read/write/search files | `@preset/code` |
| `code_reviewer` | Structured code review — correctness, security, performance, maintainability. `agentic: true` | terminal_execute, read/search files | `@preset/code` |
| `code_explorer` | Codebase navigation, dependency mapping, "how does X work?". `agentic: true` | terminal_execute, read/search files | `@preset/code` |
| `doc_generator` | Technical documentation — READMEs, ADRs, RFCs, API docs, runbooks. `agentic: true` | terminal_execute, read/write/search files | `@preset/code` |
| `test_writer` | Test generation — unit, integration, edge cases. Agentic: GENERATE→RUN→FIX→VERIFY. `agentic: true` | terminal_execute, read/write/search files | `@preset/code` |
| `refactorer` | Code refactoring without behavior change — extract, rename, decouple. `agentic: true` | terminal_execute, read/write/search files | `@preset/code` |
| `api_designer` | REST/GraphQL/gRPC API design, OpenAPI specs | read/write/search files | `@preset/architecture` |
| `migration_planner` | Database/infrastructure migration planning with rollback strategies | terminal_execute, read/write/search files | `@preset/architecture` |
| `incident_responder` | Production incident triage — fast, action-first, no preamble | terminal_execute, read/search files | `@preset/code` |
| `performance_analyst` | Performance profiling, optimization, benchmarking — MEASURE→IDENTIFY→OPTIMIZE→VERIFY | terminal_execute, read/search files | `@preset/code` |
| `planner` | Decomposes goals into sequenced, dependency-aware plans. Produces plans; does not execute | read/write/search files | standard |
| `dialectic` | Structured adversarial reasoning — thesis-antithesis-synthesis | read_file | standard |
| `decision_analyst` | Multi-criteria decision analysis with weighted scoring and tradeoff matrices | write_file | standard |
| `project_manager` | Implementation verification — confirms planned work exists in codebase. `agentic: true` | terminal_execute, read/search files | `@preset/code` |
| `todo_generator` | Extracts actionable task lists from conversations and documents | read/write files | standard |
| `proofreader` | Prose editing, grammar, clarity, tone | — | standard |
| `email_writer` | Professional email drafting | — | standard |
| `jira_writer` | Structured Jira tickets with acceptance criteria | — | standard |
| `constrained_writer` | Character-limited content (tweets, Discord, SMS) | — | standard |
| `interviewer` | Requirements gathering through structured questioning — asks, does not answer | — | `@preset/air` |
| `summarizer` | Condensing long content into structured summaries | read/write files | `@preset/air` |
| `meeting_prep` | Meeting preparation — talking points, background research, anticipated questions | read/write files, user facts | standard |
| `negotiation_advisor` | Negotiation strategy — BATNA analysis, concession planning | user facts | standard |
| `resume` | Resume tailoring via LaTeX, JD analysis, compile to PDF. `agentic: true` | terminal_execute, read/write/search files | `@preset/air` |
| `cover_letter` | Cover letter generation — JD-specific, one page max. `agentic: true` | terminal_execute, read/write files | `@preset/air` |
| `workday` | Workday/ATS application form input — copy-paste-ready text blocks | read/write files | `@preset/air` |
| `pdf_generator` | Formatted PDF creation via WeasyPrint/Pandoc/LaTeX. `agentic: true` | terminal_execute, read/write files | `@preset/code` |
| `changelog_writer` | Release notes and changelogs from git history | terminal_execute, read/write files | `@preset/code` |
| `data_analyst` | Data exploration, analysis, visualization — CSV, JSON, logs. `agentic: true` | terminal_execute, read/write/search files | `@preset/code` |
| `legal_reader` | Contract, ToS, and policy analysis — extracts obligations and risks. NOT legal advice | read_file | standard |
| `prompt_engineer` | Writing, refining, and testing prompts for LLMs — including IF's own | read/write/search files | standard |
| `sql_analyst` | Database query specialist — optimization, schema analysis, explain plans | terminal_execute, read/write files | `@preset/code` |
| `math_tutor` | Mathematics instruction — algebra, calculus, linear algebra, ML/AI math foundations | write_file | standard |
| `language_tutor` | Language learning — Japanese, Spanish, French. Vocabulary, grammar, conversation | write_file | standard |
| `ml_tutor` | ML/AI instruction — architectures, training, practical implementation | terminal_execute, read/write files | `@preset/code` |
| `career_advisor` | Career strategy — trajectory analysis, skill gaps, market positioning | write_file, user facts | standard |
| `consensus_builder` | Multi-source synthesis — spawns 2-3 specialists, collects outputs, synthesizes | spawn_specialist(s), write_file | standard |
| `self_improver` | Analyzes IF's own performance and proposes improvements to directives and prompts | read/write/search files | standard |
| `health_write` | Training program mutations (log sessions, RPE, body weight) | Health DynamoDB tools | standard |
| `finance_write` | Finance snapshot mutations (balances, holdings, goals) | Finance DynamoDB tools | standard |
| `financial_analyst` | Market research and financial analysis | Yahoo Finance + Alpha Vantage MCPs | standard |
| `web_researcher` | Web research and information synthesis | read/write files | standard |
| `media_reader` | On-demand file and image analysis (vision model, single turn) | — | media preset |

**Skills** (mode modifiers for specialists): `red_team` (adversarial), `blue_team` (defensive), `pro_con` (balanced analysis), `steelman` (strongest version of a position), `devils_advocate` (attacks preferred option), `backcast` (start from outcome, work backward), `rubber_duck` (ask questions instead of answers), `eli5` (simplify maximally), `formal` (professional register), `speed` (compressed action-only), `teach` (explain why alongside what)

Specialists with `agentic: true` in their `specialist.yaml` are routed to `run_subagent_sdk()` (`agent/tools/subagent_sdk.py`) instead of the raw OpenRouter call loop. This enables proper SDK tool dispatch, stuck detection, and event-based iteration via `Conversation.run()`.

**Model routing for specialists**: When a specialist is spawned, its `@preset/X` reference is mapped to a YAML preset via `ModelPresetManager.resolve_preset_name()`. The `select_model_for_specialist()` function uses the fast router model to pick the best concrete model from the preset's candidate list based on the condensed task intent. If no matching YAML preset exists, the original `@preset/X` reference is used as fallback.

### Delegation Pipeline

Automatic message routing in `delegation.py`: `categorize_conversation` → `get_directives` → `condense_intent` → `spawn_subagent`. Uses `delegation.yaml` for category→specialist mapping.

Categories: `code` → coder, `architecture` → architect, `finance` → financial_analyst, `health` → health_write, `writing` → proofreader, `shell` → scripter, `planning` → planner, `reasoning` → dialectic, `decision` → decision_analyst, `git` → git_ops, `review` → code_reviewer, `exploration` → code_explorer, `documentation` → doc_generator, `testing` → test_writer, `refactoring` → refactorer, `api_design` → api_designer, `migration` → migration_planner, `incident` → incident_responder, `performance` → performance_analyst, `project_tracking` → project_manager, `tasks` → todo_generator, `requirements` → interviewer, `summarization` → summarizer, `meeting` → meeting_prep, `negotiation` → negotiation_advisor, `pdf` → pdf_generator, `resume` → resume, `cover_letter` → cover_letter, `workday` → workday, `changelog` → changelog_writer, `data` → data_analyst, `legal` → legal_reader, `prompting` → prompt_engineer, `sql` → sql_analyst, `math` → math_tutor, `language` → language_tutor, `ml_learning` → ml_tutor, `career` → career_advisor. Pattern overrides: `simple` → scripter, `investigative` → debugger, `multi_perspective` → consensus_builder, `self_assessment` → self_improver, `adversarial_reasoning` → dialectic, `implementation_check` → project_manager, `production_down` → incident_responder, `job_application` → resume, `study_math` → math_tutor, `study_language` → language_tutor, `study_ml` → ml_tutor.

## Tools

All tools use the OpenHands SDK Action/Observation/Executor/ToolDefinition pattern, registered via `register_tool()`.

### Main Agent Tools (loaded in session.py)

| Category | Module | Tools |
|----------|--------|-------|
| User Facts | `agent/tools/user_facts.py` | search, add, update, list, remove |
| Capability | `agent/tools/capability_tracker.py` | log_gap, list_gaps |
| Opinion | `agent/tools/opinion_tools.py` | log_opinion_pair, log_misconception |
| Session Reflection | `agent/tools/session_reflection.py` | store_session_reflection |
| Directives | `agent/tools/directive_tools.py` | add, revise, deactivate, list |
| Context | `agent/tools/context_tools.py` | get_signals, get_financial_context, get_context_snapshot, get_current_date |
| Delegation | `agent/tools/delegation.py` | categorize_conversation, get_directives, condense_intent, spawn_subagent |
| Subagents | `agent/tools/subagents.py` | deep_think, spawn_specialist, spawn_specialists |
| Subagent SDK | `agent/tools/subagent_sdk.py` | run_subagent_sdk (SDK agentic loop for specialists with `agentic: true`) |
| Media | `agent/tools/media_tools.py` | read_media |
| Orchestrator | `orchestrator/executor.py` | execute_plan, analyze_parallel |
| Memory | `agent/memory_tools.py` | search, add, remove, list (ChromaDB) |
| Discovery | `agent/tools/discovery_tools.py` | discover_tools, use_tool (external plugin access) |

### External Tool Plugins

Domain tools live in `tools/` as mountable, independently deployable plugins. Discovered at startup by `agent/tool_registry.py` — mirrors the specialist auto-discovery pattern. Each plugin is a subdirectory with `tool.yaml` (metadata) + `tool.py` (exports `get_tools()`, `get_schemas()`, `execute()`).

| Plugin | Scope | Tools | Description |
|--------|-------|-------|-------------|
| `tools/health/` | specialist | 35 | Training program CRUD, session logging, RAG search, unit conversions |
| `tools/finance/` | specialist | 21 | Financial profile, investments, goals, cashflow, holdings |
| `tools/diary/` | specialist | 2 | Write-only diary entries, signal computation |
| `tools/proposals/` | specialist | 4 | Proposal CRUD, implementation plan generation |

**Two execution paths:**
- **SDK path** (agentic specialists): Tools registered via `register_tool()` at import time. SDK resolves by PascalCase name.
- **JSON schema path** (non-agentic specialists): `tool_schemas.py` delegates to registry for schema resolution and dispatch. Uses snake_case names.

**Adding a new plugin:**
1. Create `tools/{name}/tool.yaml` with name, description, version, scope
2. Create `tools/{name}/tool.py` exporting `get_tools()`, `get_schemas()`, `async execute(name, args)`
3. Optionally add `requirements.txt` for pip dependencies
4. App picks it up on next startup, or hit `POST /admin/reload-tools` for hot reload

### Tool Authoring

**System tools** (in `agent/tools/`): Python classes with Action (params), Observation (result), Executor (logic), ToolDefinition (metadata). Exposed via `get_*_tools()` getter functions, loaded in `session.py`. `TOOL_OUTPUT_CHAR_LIMIT` is 200K chars (SDK default 50K causes silent clipping).

All Observation subclasses inherit from `TextObservation` (`agent/tools/base.py`) instead of the raw SDK `Observation`. This fixes an SDK bug where `to_llm_content` returns empty content because custom Observations store results in named fields but don't override `to_llm_content`. `TextObservation` wires `to_llm_content` through `visualize.plain`, so subclasses only need a correct `visualize` implementation.

**External tool plugins** (in `tools/`): Same SDK pattern, but self-contained with no imports from `agent/`. Export `get_tools()`, `get_schemas()`, and `async execute(name, args)`. Use `Observation` (not `TextObservation`) since they can't import from `agent/tools/base.py`.

## Channels

| Platform | Type | Description |
|----------|------|-------------|
| Discord | Bot (discord.py) | Listens to registered channels, slash commands, thread support, status embeds |
| OpenWebUI | Polling | Chat interface integration (5s poll interval) |
| HTTP API | REST | Direct OpenAI-compatible API access |

Flow: listener → debounce (5s) → dispatcher (set platform context) → translator → completions pipeline → chunker (1500 chars) → delivery.

### Discord Status Embeds

Lightweight, color-coded embeds sent to Discord channels for operational visibility. Only active for Discord platform — no-ops for API/OpenWebUI.

**Status types** (sent as separate small embeds per event):
| Status | Color | When |
|--------|-------|------|
| Message Received | Blue | Dispatcher receives batch |
| Model Selected | Green | Router picks a model for a subagent |
| Subagent Spawning | Yellow | Specialist subagent starts with model info |
| Subagent Completed | Green | Specialist subagent finishes |
| Subagent Failed | Red | Specialist subagent errors |
| Tool Started | Purple | SDK tool call detected |
| Tool Completed | Green | Tool execution succeeds |
| Tool Failed | Red | Tool execution errors |

**Implementation**: `channels/context.py` stores platform context (channel_ref, discord_loop) in a `contextvars.ContextVar`. `channels/status.py` reads this context to send embeds via `asyncio.run_coroutine_threadsafe()`. Context is propagated through `ThreadPoolExecutor` paths via `contextvars.copy_context()`.

### Attachment Handling

Discord attachments are downloaded by the dispatcher, uploaded to the terminal filesystem, and referenced via `FILES:` metadata in agent output. The `FilesStripBuffer` strips these lines from responses delivered to users.

### Discord History

The dispatcher fetches up to 100 historical messages from Discord for context enrichment.

## Memory System

### User Facts (LanceDB)

`UserFact` dataclass with: id, context_id, username, content, category, source, confidence, cache_key, timestamps, metadata.

**Categories** (22): personal, preference, opinion, skill, life_event, future_direction, project_direction, mental_state, interest_area, conversation_summary, topic_log, model_assessment, agent_identity, agent_opinion, agent_principle, capability_gap, tool_suggestion, opinion_pair, misconception, session_reflection, health, finance.

**Sources**: user_stated, model_observed, model_assessed, conversation_derived.

Context-scoped: each context_id gets its own LanceDB table. Supports semantic search within context, supersession for fact updates, and capability gap logging with priority scoring.

### Legacy Memory (ChromaDB)

`MemoryStore` in `store.py` — older RAG-backed semantic search. Categories: preference, personal, skill_level, opinion, life_event, future_plan, mental_state.

### Conversation Summarization

Fire-and-forget summarization in `summarizer.py` after conversations end.

## Directives

Versioned behavioral rules stored in DynamoDB (`if-core` table). Tiered by priority (0-5):

| Tier | Label | Purpose |
|------|-------|---------|
| 0 | Core Identity | Fundamental personality traits |
| 1 | Behavioral Rules | How to respond/act |
| 2 | Style & Tone | Voice adjustments |
| 3 | Domain Knowledge | Topic-specific guidance |
| 4 | Situational | Context-dependent rules |
| 5 | Temporary | Time-limited adjustments |

Content is rewritten through LLM for consistent voice. Cached in memory with periodic refresh. Injected into system prompt during assembly. Specialist subagents receive filtered directives based on their `directive_types` config.

Agent tools: `directive_add`, `directive_revise`, `directive_deactivate`, `directive_list`.

## Reflection Engine

Metacognitive layer in `agent/reflection/`. Analyzes interactions for self-improvement.

**Triggers**: post-session (>5 turns), periodic (6h), on-demand (`/reflect`), threshold-based (uncategorized facts, gaps, opinions).

**Cycle**: Pattern Detection → Opinion Formation → Capability Gap Analysis → Meta-Analysis → Growth Tracking.

**Capability gaps**: logged with priority score `(frequency * 0.4) + (recency * 0.3) + (impact * 0.3)`. High-frequency gaps are promoted to tool suggestions via `CAPABILITY_GAP_PROMOTION_THRESHOLD` (default 3).

## Orchestrator

Multi-step task execution in `orchestrator/`:

- **`execute_plan`**: Sequential multi-step plan with subagents. Each step sees filesystem state from previous steps.
- **`analyze_parallel`**: Spawns parallel analysis subagents across perspectives (security, performance, architecture, testing, documentation). Each writes to `/home/user/workspace/findings/{perspective}.md`. Synthesizer combines into prioritized report.

## Terminal System

Docker containers for shell access via shared OpenTerminal deployment (`TERMINAL_URL`). Each conversation gets isolated working directory at `/home/user/conversations/{conversation_id}/`.

Two client modes:
- **`TerminalClient`** (`terminal/client.py`) — dynamic per-conversation containers
- **`StaticTerminalManager`** (`terminal/static_client.py`) — single shared IaC-managed deployment (Kubernetes-friendly); exposes the same interface via `StaticTerminalContainer`

Tools: `terminal_execute`, `terminal_read_file`, `terminal_write_file`, `terminal_list_files`.

`FILES:` lines in agent output reference terminal files for artifact tracking and attachment delivery.

## Health Module

Training program management with DynamoDB storage (`if-health` table) and ChromaDB RAG for PDF documents (IPF rulebook, anti-doping list, supplement PDFs).

Core functions in `health/tools.py` are wrapped by the external tool plugin at `tools/health/tool.py`. Tools: program CRUD, session logging, competition management, RAG search, unit conversions. Uses Apache Tika for PDF extraction, 500-token chunks with 50-token overlap.

## Heartbeat

Proactive engagement system. Monitors channel activity, initiates pondering conversations after idle threshold.

Config: idle 6h, cooldown 6h, quiet hours 23:00-07:00 UTC. Opening message uses stored user facts. Integrates with pondering preset.

## MCP Servers

Extended capabilities via MCP servers (defined in `specialists/mcp_servers.yaml`):

| Server | Purpose |
|--------|---------|
| `time` | Current date/time |
| `aws_docs` | AWS documentation lookup |
| `yahoo_finance` | Stock quotes |
| `alpha_vantage` | Financial indicators |

Server assignment per specialist is configured in each `specialist.yaml` under `mcp_servers`.

## Storage

| Store | Backend | Purpose |
|-------|---------|---------|
| User Facts | LanceDB | Operator context with semantic search |
| Webhooks | SQLite (WAL) | Channel registration and activity |
| Directives | DynamoDB (`if-core`) | Behavioral rules with versioning |
| Models | DynamoDB (`if-models`) | OpenRouter model metadata registry |
| Health | DynamoDB (`if-health`) | Training programs |
| Finance | DynamoDB (`if-finance`) | Financial snapshots |
| Diary | DynamoDB (`if-diary-entries`, `if-diary-signals`) | Journaling + distilled signals |
| Proposals | DynamoDB (`if-proposals`) | Agent-proposed directives |

## Utility Applications

TypeScript/Node.js apps in `app/utils/`:

| App | Port | Purpose | DynamoDB Table |
|-----|------|---------|----------------|
| Hub | 3000 | Central dashboard aggregating all portals | — |
| Finance | 3002 | Net worth, investments, cashflow | `if-finance` |
| Diary | 3003 | Mental health journaling and signals | `if-diary-entries`, `if-diary-signals` |
| Proposals | 3004 | Kanban for agent-proposed directives | `if-proposals` |
| Powerlifting | 3005 | Training tracking and analytics | `if-health` |

## Commands

Discord guild slash commands (autocomplete) and plain text messages:

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

## Environment Variables

Key configuration (see `app/src/config.py` for full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | required | API key for model access |
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | LLM endpoint |
| `TIER_UPGRADE_THRESHOLD` | 0.65 | Context fraction before tier upgrade |
| `TIER_AIR_LIMIT` | 100000 | Air tier token limit |
| `TIER_STANDARD_LIMIT` | 200000 | Standard tier token limit |
| `TIER_HEAVY_LIMIT` | 1000000 | Heavy tier token limit |
| `HEARTBEAT_ENABLED` | true | Enable proactive engagement |
| `HEARTBEAT_IDLE_HOURS` | 6.0 | Hours idle before heartbeat |
| `DIRECTIVE_STORE_ENABLED` | true | Enable DynamoDB directives |
| `REFLECTION_ENABLED` | true | Enable reflection engine |
| `TERMINAL_URL` | `http://open-terminal:7681` | OpenTerminal deployment URL |
| `TOOL_OUTPUT_CHAR_LIMIT` | 200000 | Max tool output chars before SDK truncation |
| `EXTERNAL_TOOLS_PATH` | "" | Override path for external tool plugins |
| `EXTERNAL_TOOLS_FALLBACK` | `project_root/tools/` | Fallback path if EXTERNAL_TOOLS_PATH is empty |
| `SPECIALISTS_PATH` | `project_root/specialists/` | Path to specialists directory |
| `IF_MODELS_TABLE_NAME` | `if-models` | DynamoDB table for model registry |
| `MODELS_PATH` | `project_root/models/` | Path to model preset YAML configs |
| `MODEL_ROUTER_MODEL` | `google/gemma-3-4b-it` | Fast model for subagent model selection |
| `MODEL_ROUTER_ENABLED` | true | Enable LLM-based model routing |
| `MODEL_STATS_REFRESH_INTERVAL` | 1800 | Seconds between per-provider latency/throughput refreshes |

## Operational Rules

- **Build before declaring done**: Always run `npm run build` in both `frontend/` and `backend/` of any portal before declaring work complete. A successful build is the minimum verification bar — no exceptions.
- **k3s debugging**: The app is hosted on a k3s cluster. When debugging runtime issues, use `kubectl logs`, `kubectl describe`, and `kubectl get events` to inspect pod state. Do not guess at runtime behavior from code alone.
- **Terraform**: Never run `terraform apply` or `terraform destroy`. Targeted low-blast-radius `terraform apply -target=...` is the only exception, and only after explicit user approval via AskUserQuestion.
- **AWS resources**: Never delete AWS resources (CLI, SDK, console). Provide the command for the user to run manually.
- **kubectl mutations**: Never run `kubectl delete/apply/patch/edit/replace/scale/rollout/cordon/drain`. Provide the command for the user to run manually. Read-only commands (`get`, `describe`, `logs`, `events`, `top`) are fine.
- **No git writes**: Never run `git commit`, `git push`, `git merge`, `git rebase`, `git reset --hard`, or any mutating git command. No write privileges. Provide the command for the user to run manually.

## Key Patterns

- **Specialist auto-discovery**: `specialists.py` scans `SPECIALISTS_PATH` at import time — no code changes needed to add specialists
- **Model preset auto-discovery**: `models/loader.py` loads subagent presets from `MODELS_PATH/presets.yaml` and tier config from `MODELS_PATH/tiers.yaml` at startup — no code changes needed to add presets or adjust tiers
- **Model registry**: `storage/model_registry.py` mirrors DirectiveStore pattern (PK/SK, boto3, cache). Seeded from OpenRouter API at startup.
- **Smart model routing**: `models/router.py` uses a fast LLM to pick the best model from a preset's candidate list. Falls back to sorted-first if disabled.
- **Tool plugin auto-discovery**: `tool_registry.py` scans `tools/*/tool.yaml` at startup — no code changes needed to add domain tools. Plugins export `get_tools()`, `get_schemas()`, `execute()`. Hot reload via `POST /admin/reload-tools`.
- **Delegation pipeline**: `categorize_conversation` → `get_directives` → `condense_intent` → `spawn_subagent` in `delegation.py`
- **Subagent spawning**: `spawn_specialist(type, task, context)` in `subagents.py`; `_run_subagent()` gives subagents terminal and domain tool access via registry
- **Tool authoring**: System tools use Python classes (Action/Observation/Executor/ToolDefinition) registered with `register_tool()`. External plugins use the same SDK pattern but are self-contained in `tools/`.
- **Context/signal injection**: `context_tools.py` auto-injects diary signals, financial context, and snapshots into every system prompt
- **FILES metadata pattern**: `FILES:` lines in agent output are stripped by `FilesStripBuffer` for artifact tracking
- **Channel message flow**: listener → debounce → dispatcher → translator → completions → chunker → delivery
- **Directive injection**: System prompt includes directives from DynamoDB, filtered by specialist type for subagents
- **MCP server config**: `mcp_servers.yaml` defines servers; specialist `specialist.yaml` lists which servers each specialist gets
- **Discord status embeds**: `channels/status.py` sends color-coded embeds via `contextvars` propagation — no-ops for non-Discord platforms
