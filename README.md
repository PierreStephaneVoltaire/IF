# IF — Intelligent Agent API

A single main agent with context-aware tiering and specialist subagent delegation. Built on the OpenHands SDK, routes through OpenRouter, persists knowledge in LanceDB.

---

## What This Is

This is an architectural exercise and personal learning project — not a product. The goal is to build practical knowledge of multi-agent orchestration, runtime behavior shaping, specialist delegation, and operational observability by building something that actually runs. It is deployed on a personal Kubernetes cluster and used daily, which means real bugs surface and architectural decisions have real consequences. Current LLM provider: OpenRouter. Current interaction layer: Discord. Planned: AWS Bedrock, Slack, Teams.

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

## Comparative Analysis

Four systems examined: **OpenHands** (the SDK IF is built on), **Claude Cowork** (Anthropic's autonomous task desktop app), **OpenClaw** (local-first multi-platform personal agent), **Hermes Agent** (Nous Research's self-improving autonomous agent). All approach the same problem space — persistent, autonomous, personalized AI agents — from different architectural angles.

### At a Glance

| | IF | OpenHands | Claude Cowork | OpenClaw | Hermes |
|---|---|---|---|---|---|
| LLM providers | OpenRouter (multi-model routing) | Any | Claude only | Claude, GPT, local | OpenRouter, OpenAI, custom |
| Chat platforms | Discord, OpenWebUI | GitHub, GitLab, Slack, Jira | Desktop app | 6+ (Discord, Slack, WhatsApp, Telegram, Signal, iMessage) | 14+ via unified gateway |
| Memory | LanceDB (vector semantic search) | Not specified | Cross-session cloud | Local persistent | FTS5 full-text + LLM summarization |
| Execution sandbox | LocalWorkspace within pod | LocalWorkspace (cloud/local) | Local file system | Local machine | 6 backends (Docker, SSH, Modal, Daytona…) |
| Multi-agent | Specialist subagents | Cloud agent pools | Not specified | Multiple concurrent instances | Parallel isolated subagents |
| Behavior config | Runtime directives (DynamoDB) | Prompt files | Prompt files | SOUL.md (static) | Static config + RL loop |
| AgentSkills | Yes (SKILL.md) | Yes | No | No | Yes |
| Multi-user session | Yes (channel-based) | No | No | No | No |
| Auth / access control | None (gap) | Not specified | Desktop local | Local machine | Not specified |
| Image generation | No | No | No | No | Yes |
| Audio (TTS / input) | No | No | No | No | Yes (TTS) |
| Deployment | Kubernetes | Cloud / CLI / self-hosted | Desktop | Local machine | Any infrastructure |

---

### OpenHands

*The SDK IF is built on.*

**Common ground**: IF uses `openhands-sdk 1.11.4`. LocalWorkspace isolation, the Action/Observation/Executor/ToolDefinition tool pattern, and the AgentSkills SKILL.md format are all shared. AgentSkills compliance means skills are theoretically portable across both systems and the 30+ agent ecosystem at agentskills.io (GitHub Copilot, VS Code, Gemini CLI, Cursor, Goose, Claude Code, Spring AI, and others are all compliant).

**Key differences**: OpenHands targets software development at cloud scale — thousands of parallel agents, GitHub/GitLab/Bitbucket/Jira/Linear integrations at the platform level. IF targets single-operator personal assistant use cases (health, finance, writing, coaching). OpenHands agents are ephemeral and task-scoped; IF builds persistent operator context over time. OpenHands has no directive system, reflection engine, or domain-specialist directive filtering.

**Architectural lessons**: Platform-level webhook integration (GitHub issue → agent task) is worth studying for any future dev-workflow support. The cloud agent pool architecture is the natural evolution path for multi-user scenarios.

---

### Claude Cowork

*Anthropic's autonomous task desktop app.*

**Common ground**: Multi-step autonomous execution without step-by-step prompting. Persistent memory across sessions. Proactive engagement: Cowork's scheduled dispatch ↔ IF's heartbeat system. File artifact delivery.

**Key differences**: Cowork is a desktop app with direct local file system access; IF is server-side with LocalWorkspace within a pod. Cowork uses "computer use" (screen and UI control); IF uses shell commands. Cowork is Claude-exclusive with subscription pricing — subscription cost is subsidized at high usage volumes, which can outperform pay-per-token billing at scale. IF uses OpenRouter with per-call billing and model routing for cost optimization, but requires active API budget management. Cowork has phone↔desktop cross-device continuity; IF is channel-based — any platform that can send a webhook can connect, with no dedicated mobile client. Cowork is single-user by design.

**Architectural lessons**: Subscription vs. pay-per-token has different break-even points depending on volume — relevant when evaluating Bedrock or direct-provider integration. Cowork's scheduled dispatch is a natural extension of IF's heartbeat system.

---

### OpenClaw

*Local-first personal AI with multi-platform access.*

**Common ground**: Both accumulate operator context over time. Both support multiple chat platforms via an adapter/dispatcher pattern. Both are open source. Both have proactive engagement. Both route platform messages through a shared agent core.

**Key differences**:

*Behavior configuration*: OpenClaw uses a SOUL.md file — a static markdown document that defines the agent's personality and behavior rules. Authoring it requires deliberate prompt engineering; changing it requires editing the file and reloading. IF uses runtime-editable DynamoDB directives shaped iteratively through interaction — a directive change takes effect on the next request with no redeployment.

*Deployment*: OpenClaw runs on user hardware (local-first, no cloud dependency, private data). IF runs on Kubernetes. OpenClaw supports local models (Ollama, MiniMax) natively. IF could reach local model support via LiteLLM as a proxy — point `LLM_BASE_URL` at a LiteLLM instance and it covers Bedrock, Ollama, and direct provider APIs without app code changes. Hardware remains the constraint for local inference; Ollama Cloud removes the privacy benefit.

*Self-extension*: OpenClaw agents can write their own skills and tool extensions at runtime. IF agents can propose directives (`directive_add`) but cannot generate new tool plugins. IF's plugin architecture (`tools/*/tool.yaml` + `tool.py` + hot reload via `POST /admin/reload-tools`) is structurally ready for this — the gap is the generation step.

*Security*: OpenClaw's security perimeter is the local machine. IF exposes HTTP endpoints in a cluster with no authentication layer — no user allowlist, no per-request identity verification.

**Architectural lessons**: Self-extending tool generation is the most actionable gap. IF's channel adapter system (listener + translator per platform) is the right abstraction — the improvement is making adapters externally loadable like tool plugins rather than hardcoded imports. LiteLLM proxy is a low-code path to multi-provider support.

---

### Hermes Agent (Nous Research)

*Infrastructure-agnostic self-improving autonomous agent.*

**Common ground**: Both support OpenRouter. Both use Discord as a primary channel. Both are AgentSkills compliant (SKILL.md). Both spawn parallel subagents. Both use MCP servers. Both do conversation summarization. Both were built by practitioners, not product teams.

**Key differences**:

*Platform reach*: Hermes reaches 14+ platforms (Discord, Slack, WhatsApp, Signal, Matrix, Mattermost, Email, SMS, DingTalk, Feishu, WeCom, Home Assistant) via a unified messaging gateway — a single abstracted interface with pluggable platform adapters. IF has 2 platforms with Slack and Teams planned. This gateway design is worth examining before building each new IF adapter: a single external-plugin interface is cleaner than per-platform hardcoded imports.

*Memory*: Hermes uses FTS5 full-text search + LLM summarization. IF uses LanceDB vector semantic search. FTS5 excels at exact keyword recall; vector search excels at semantic similarity. These are complementary — a hybrid would cover both.

*Execution sandbox*: Hermes supports 6 backends (local, Docker, SSH, Daytona, Singularity, Modal). IF uses LocalWorkspace within a Kubernetes pod — meaningful isolation (namespace, resource limits) but shared kernel. IF already scopes workspaces per channel using `channel_id`; per-user isolation within a multi-user channel would be a path append (`/{channel_id}/{user_id}/`). The practical concerns are workspace cleanup (old directories accumulating) and preventing cross-user file read within a shared channel workspace.

*Modalities*: Hermes includes web search, browser control, TTS, and image generation. IF handles vision input via `read_media` but has no generation capabilities — no TTS, no image generation, no audio input.

*Self-improvement*: Hermes runs a closed learning loop with RL support — the model improves at the weights level. IF's self-improvement operates at the prompt layer: the reflection engine detects patterns and proposes directive changes, but the model is not modified. The infrastructure for behavioral evolution (directives, reflection engine, subagent proposals, skills) is in place and partially tested; systematic end-to-end benchmarking has not been done.

*Security*: API keys in IF are environment variables injected at deployment (no Vault or AWS Secrets Manager). There is no per-user access control — any participant in a registered channel can trigger agent execution.

**Architectural lessons**: Unified messaging gateway before adding platforms. FTS5 + vector hybrid memory. Hermes's AgentSkills compliance means skill packages could be shared directly.

---

### IF's Distinct Design Choices

What IF does that none of the above do:

- **Runtime directive system**: Behavioral rules stored in DynamoDB, editable via API with no redeployment. No peer has an equivalent — all require file edits or code changes to modify agent behavior.
- **Domain-specialist + directive filtering**: Each specialist receives only the directives relevant to its domain (health, finance, code). Context is scoped, not broadcast to every subagent.
- **Tiered model selection**: Air/Standard/Heavy tiers based on live context token count. Model complexity scales automatically with conversation complexity.
- **Smart model routing per specialist**: A fast LLM selects the best concrete model from a YAML preset at spawn time, using task intent + model metadata (latency, price, context size).
- **Multi-user channel sessions**: IF operates in chat channels where multiple users can participate simultaneously. No peer does this. The unsolved design problem: per-user context (health facts, personal directives, memory) must be dynamically applied based on who's speaking, with a collision policy when multiple users make conflicting requests in the same channel.
- **Evolutionary behavior**: Directives accumulate, user facts build up, reflection engine detects patterns. Behavior shapes itself through interaction rather than requiring redesign cycles.

---

### Known Gaps and Future Directions

**Multi-provider support** — LiteLLM as a proxy layer covers Bedrock, direct Anthropic/OpenAI/Google APIs, and local models (Ollama) without app code changes. Planned: Bedrock.

**Platform expansion** — Slack and Teams planned. Study Hermes's unified gateway before building each; externally-loadable adapters are cleaner than hardcoded imports.

**Authentication and access control** — None currently. Any user in a registered channel can trigger execution. Needed: per-user allowlist, per-channel permissions, request-level identity propagation.

**Hooks and guardrails** — No pre-/post-execution hooks. No content policy enforcement beyond LLM-level refusals. Required for safe multi-user deployment.

**Per-user context in multi-user channels** — IF's channel model is architecturally unusual and genuinely interesting. The missing layer: identify the speaking user per message, load their personal facts and directives dynamically, and define a collision policy for conflicting concurrent requests.

**Memory hybrid** — FTS5 keyword search alongside LanceDB vector search for exact recall.

**Self-extending tools** — IF's plugin system is structurally ready (YAML + Python + hot reload). The gap is the generation step: an agent that writes a new plugin and triggers reload.

**Modalities** — No TTS, no image generation, no audio input. `read_media` covers vision input only.

**AgentSkills marketplace** — IF's skills are already SKILL.md compliant. Publishing to agentskills.io would enable sharing skills with any of the 30+ compliant agents.

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

### Delegation

The main agent routes requests to specialists via three tools: `list_specialists` (enumerate available specialists), `condense_intent` (rewrite the user's message as a focused task), and `spawn_specialist` (spawn with directive injection from the specialist's `directive_types` config).

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

Shell access via OpenHands SDK `LocalWorkspace`, running within the application pod. Each conversation gets an isolated working directory at `$WORKSPACE_BASE/{channel_id}/`. Tools: `terminal_execute`, `terminal_read_file`, `terminal_write_file`, `terminal_list_files`.

Isolation is at the pod level (shared kernel). The workspace root is scoped per channel — per-user subdirectories within a multi-user channel would be a path append.

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

---

## Utility Applications

TypeScript/Node.js apps in `utils/`:

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

