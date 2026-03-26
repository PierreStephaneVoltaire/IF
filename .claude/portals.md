# Utility Applications (Portals)

TypeScript/Node.js utility apps in `app/utils/` directory.

## Available Portals

### Main Portal (Hub) — Port 3000

Central dashboard for operator interaction.

**Location:** `app/utils/hub/`

### Finance Portal — Port 3002

Financial data visualization and tracking.

**Location:** `app/utils/finance/`

**Tables:**
- `IF_FINANCE_TABLE_NAME` (default: `if-finance`) — Versioned financial profile storage

### Diary Portal — Port 3003

Journaling and signal tracking.

**Location:** `app/utils/diary/`

**Tables:**
- `IF_DIARY_ENTRIES_TABLE_NAME` (default: `if-diary-entries`) — TTL-enabled write-only entries
- `IF_DIARY_SIGNALS_TABLE_NAME` (default: `if-diary-signals`) — Distilled signals for charting/injection

**Configuration:**
- `DIARY_TTL_DAYS` (default: `3`) — TTL for diary entries in days
- `DIARY_SIGNAL_COMPUTE_INTERVAL_HOURS` (default: `6.0`) — Interval for automatic signal computation
- `DIARY_SIGNAL_MODEL` (default: `@preset/air`) — Model for diary signal computation

### Proposals Portal — Port 3004

Agent-proposed directives and tools.

**Location:** `app/utils/proposals/`

**Tables:**
- `IF_PROPOSALS_TABLE_NAME` (default: `if-proposals`) — Agent-proposed directives/tools

### Powerlifting App

Fitness and training tracking.

**Location:** `app/utils/powerlifting/` or `app/src/health/`

**Configuration:**
- `IF_HEALTH_TABLE_NAME` (default: `if-health`) — DynamoDB table for health program storage
- `HEALTH_PROGRAM_PK` (default: `operator`) — Partition key value
- `HEALTH_DOCS_DIR` (default: `docs/health`) — Directory containing health PDF documents for RAG
- `RESEARCH_AGENT_MODEL` (default: `@preset/heavy`) — Model for research agent spawned by health tools

### Discord Webhook Server

Webhook handling for Discord integration.

**Location:** `app/utils/discord-webhook/`

## Shared Patterns

### DynamoDB Tables

All portals use DynamoDB for persistence:

| Table | Purpose |
|-------|---------|
| `if-finance` | Versioned financial snapshots |
| `if-diary-entries` | Raw diary entries (TTL-enabled) |
| `if-diary-signals` | Computed signals from entries |
| `if-proposals` | Agent proposals for directives/tools |
| `if-health` | Training programs and fitness data |

### Common Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `IF_USER_PK` | `operator` | Default user PK for all infrastructure tables |
| `AWS_REGION` | `us-east-1` | AWS region for DynamoDB |

## Agent Tools for Portals

| Portal | Tool File | Tools |
|--------|-----------|-------|
| Finance | `src/agent/tools/finance_tools.py` | Finance data access |
| Health | `src/agent/tools/health_tools.py` | Training program management |
| Diary | `src/agent/tools/diary_tools.py` | Diary entry tools |
| Proposals | `src/agent/tools/proposal_tools.py` | Proposal management |

## Health Module Details

**Modules:**
- `src/health/__init__.py` — Module exports
- `src/health/rag.py` — ChromaDB RAG for health documents
- `src/health/renderer.py` — Output rendering
- `src/health/program_store.py` — DynamoDB program storage
- `src/health/tools.py` — Additional health tools

## How to Add a New Portal

1. Create directory in `app/utils/{name}/`
2. Set up Next.js or Express app
3. Create DynamoDB table (add config to `src/config.py`)
4. Create agent tools in `src/agent/tools/{name}_tools.py`
5. Register tools in `src/agent/session.py`
6. Add documentation here

## Gotchas

- Portals are separate from main Python app
- Each has its own port and dependencies
- DynamoDB tables must be created before use
- Health module uses ChromaDB for RAG (separate from LanceDB user facts)
