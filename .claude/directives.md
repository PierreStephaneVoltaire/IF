# Directive System

Versioned behavioral directives backed by DynamoDB. Directives define standing orders and behavioral rules that the agent follows across all conversations.

**Modules:**
- `src/storage/directive_model.py` — Directive data model
- `src/storage/directive_store.py` — DynamoDB backend with caching
- `src/agent/tools/directive_tools.py` — Agent tools for directive CRUD
- `src/api/directives.py` — REST API endpoints

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    DIRECTIVE SYSTEM                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    DynamoDB Backend                       │    │
│  │                                                           │    │
│  │  PK=DIR, SK={alpha}-{beta}-{version}                     │    │
│  │  - All directives stored with versioning                 │    │
│  │  - Immutable history (revisions create new versions)     │    │
│  │  - Active flag for soft-delete                           │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    In-Memory Cache                        │    │
│  │                                                           │    │
│  │  - Loads all active directives at startup                │    │
│  │  - Only highest version per alpha/beta is cached         │    │
│  │  - Fast access for system prompt assembly                │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│              ┌──────────────┴──────────────┐                    │
│              ▼                             ▼                    │
│  ┌────────────────────┐        ┌────────────────────┐          │
│  │   Agent Tools      │        │    REST API        │          │
│  │                    │        │                    │          │
│  │  directive_add     │        │  GET /directives   │          │
│  │  directive_revise  │        │  GET /{a}/{b}      │          │
│  │  directive_deact-  │        │  POST /reload      │          │
│  │    ivate           │        │                    │          │
│  └────────────────────┘        └────────────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

## Directive Schema

```python
@dataclass
class Directive:
    alpha: int              # Tier number (0-5)
    beta: int               # Directive number within tier
    version: int            # Version number (auto-incremented)
    label: str              # Short label (e.g., "VERIFY_CLAIMS")
    content: str            # Full directive text
    active: bool            # Soft-delete flag
    created_by: str         # "agent" or "operator"
    created_at: str         # ISO timestamp
```

## Alpha Tiers

| Alpha | Description | Protection |
|-------|-------------|------------|
| 0 | Core Identity | Protected — cannot be modified via agent tools |
| 1 | Fundamental Rules | Protected — cannot be modified via agent tools |
| 2 | Behavioral Guidelines | Modifiable via agent tools |
| 3 | Task-Specific Rules | Modifiable via agent tools |
| 4 | Context-Specific Rules | Modifiable via agent tools |
| 5 | Temporary/Session Rules | Modifiable via agent tools |

## Content Rewriting

All directive content is rewritten through an LLM before storage:

```
Raw Operator Intent → LLM Rewriter → Directive Voice
```

The rewrite ensures consistent voice: terse, imperative prose. No filler. No corporate warmth.

## Agent Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `directive_add` | `alpha`, `label`, `content`, `created_by` | Add new directive (alpha 2-5 only) |
| `directive_revise` | `alpha`, `beta`, `content` | Create new version of existing directive |
| `directive_deactivate` | `alpha`, `beta` | Soft-delete a directive |
| `directive_list` | `alpha?` | List all directives (optionally filtered) |

## REST API Endpoints

### `GET /v1/directives/`

List all active directives. Optional `?alpha=N` filter.

### `GET /v1/directives/{alpha}/{beta}`

Get a specific directive.

### `GET /v1/directives/{alpha}/{beta}/history`

Get version history for a directive.

### `POST /v1/directives/reload`

Force reload of directives from DynamoDB.

## DynamoDB Table Schema

```sql
CREATE TABLE if-core (
    PK STRING,          -- Always "DIR"
    SK STRING,          -- "{alpha}-{beta}-{version}"
    label STRING,
    content STRING,
    active BOOLEAN,
    created_by STRING,
    created_at STRING,
    PRIMARY KEY (PK, SK)
);
```

## Prompt Assembly

Directives are formatted and injected into the system prompt:

```python
def format_for_prompt(self, alpha: int = None) -> str:
    lines = ["## Directives\n"]
    for d in self.get_all(alpha=alpha):
        lines.append(f"### {d.alpha}-{d.beta}: {d.label}")
        lines.append(d.content)
        lines.append("")
    return "\n".join(lines)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DIRECTIVE_STORE_ENABLED` | `true` | Enable directive store |
| `DYNAMODB_DIRECTIVES_TABLE` | `if-core` | DynamoDB table name |
| `AWS_REGION` | `us-east-1` | AWS region |
| `DIRECTIVE_REWRITE_MODEL` | `@preset/heavy` | Model for content rewriting |

## How to Add a Directive

### Via Agent Tool

```python
directive_add(
    alpha=3,
    label="MY_DIRECTIVE",
    content="When X happens, do Y. Exceptions: Z.",
    created_by="operator"
)
```

### Via REST API

```bash
curl -X POST http://localhost:8000/v1/directives \
  -H "Content-Type: application/json" \
  -d '{"alpha": 3, "label": "MY_DIRECTIVE", "content": "..."}'
```

## Gotchas

- Alpha 0-1 are protected — agent tools cannot modify them
- Revisions create new versions; history is preserved
- Reload cache after manual DynamoDB edits
- Content is auto-rewritten for consistent voice
