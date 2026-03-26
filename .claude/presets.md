# Preset System

Presets are static definitions that define routing targets. They are loaded at startup from `src/presets/loader.py`.

## Available Presets

| Preset | Model | Description |
|--------|-------|-------------|
| `architecture` | `@preset/architecture` | System design, infrastructure planning |
| `code` | `@preset/code` | Writing, modifying, debugging code |
| `shell` | `@preset/shell` | CLI commands, one-liners |
| `security` | `@preset/security` | Threat modeling, compliance |
| `health` | `@preset/health` | Fitness, nutrition, sports |
| `mental_health` | `@preset/mental_health` | Emotional support, crisis routing |
| `finance` | `@preset/finance` | Market data, investing |
| `proofreader` | `@preset/proofreader` | Proofreading, editing, rewriting non-code text |
| `social` | `@preset/social` | Casual conversation |
| `general` | `@preset/general` | General-purpose fallback |
| `pondering` | `@preset/pondering` | Operator profiling (manual/heartbeat only) |

> **Note:** The `pondering` preset is excluded from automatic selection. It can only be activated via `/pondering` command or the heartbeat system.

## Preset Structure

```python
@dataclass
class Preset:
    slug: str           # URL-safe identifier
    name: str           # Display name
    description: str    # Used for scoring classification
    model: str          # OpenRouter model: @preset/{slug}
```

## Tier System

The tiering system uses context-based presets:

| Tier | Name | Context Limit | Preset | Use Case |
|------|------|---------------|--------|----------|
| 0 | Air | 30,000 tokens | `@preset/air` | Simple queries, quick responses |
| 1 | Standard | 120,000 tokens | `@preset/standard` | Most conversations |
| 2 | Heavy | 200,000 tokens | `@preset/heavy` | Complex tasks, large context |

### Tier Upgrade Logic

**Module:** `src/agent/tiering.py`

```python
def check_tier(context_tokens: int, current_tier: int) -> tuple[bool, Optional[int]]:
    """
    Returns:
        (try_condensation, upgrade_available)

    - try_condensation: True if context exceeds limit
    - upgrade_available: New tier number if upgrade recommended
    """
```

**Upgrade Threshold**: 65% of current tier's limit (`TIER_UPGRADE_THRESHOLD`)

### Context Estimation

```python
def estimate_context_tokens(
    system_prompt: str,
    messages: List[dict],
    tool_overhead: int = 0
) -> int:
    """Estimate total context tokens (~4 chars per token)."""
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TIER_UPGRADE_THRESHOLD` | `0.65` | Fraction of context limit before tier upgrade |
| `TIER_AIR_LIMIT` | `30000` | Air tier context limit (tokens) |
| `TIER_STANDARD_LIMIT` | `120000` | Standard tier context limit (tokens) |
| `TIER_HEAVY_LIMIT` | `200000` | Heavy tier context limit (tokens) |
| `TIER_AIR_PRESET` | `@preset/air` | Preset for air tier |
| `TIER_STANDARD_PRESET` | `@preset/standard` | Preset for standard tier |
| `TIER_HEAVY_PRESET` | `@preset/heavy` | Preset for heavy tier |

## Pondering Preset

The pondering preset is special:

- **Objective**: Build and refine the operator profile
- **Behavior**: Ask ONE question at a time, focus on depth over breadth
- **MCP Servers**: Only `time` (all others disabled)
- **Pin Behavior**: Never auto-releases; only `/end_convo` or `/{other_preset}` releases

### Activation

```bash
# Manual activation
/pondering

# Automatic activation via heartbeat after idle period
```

### Hard Constraints

- Do NOT produce code blocks
- Do NOT start architecture discussions
- Do NOT enter analysis or debugging flows
- Do NOT generate files

## How to Add a New Preset

1. Define preset in OpenRouter (or use existing)
2. Add to preset loader or configuration
3. Map MCP servers in `src/mcp_servers/config.py` if needed:

```python
PRESET_MCP_MAP = {
    # ... existing ...
    "your_preset": ["mcp_server_1", "mcp_server_2"],
}
```

## Gotchas

- Presets are static — changes require restart
- `pondering` preset is never auto-selected
- Tier upgrades happen at 65% of limit
- Context estimation uses ~4 chars per token
