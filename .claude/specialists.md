# Specialist Subagents

Specialists are domain-specific subagents spawned by the main agent for deep expertise.

**Module:** `src/agent/specialists.py`

## Available Specialists

| Specialist | Description | Directive Types | MCP Servers |
|------------|-------------|-----------------|-------------|
| `debugger` | Deep code debugging and error analysis | code, architecture | - |
| `architect` | System architecture and design patterns | architecture, code | aws_docs |
| `secops` | Security operations and vulnerability analysis | security, code | - |
| `devops` | Infrastructure and deployment automation | code, architecture | - |
| `financial_analyst` | Financial data analysis and market research | finance, competition | yahoo_finance, alpha_vantage |
| `finance_write` | Validated write agent for finance snapshot mutations | finance | - |
| `health_write` | Validated write agent for training program mutations | health | - |
| `web_researcher` | Web research and information synthesis | core, competition | - |
| `proofreader` | General prose editing — grammar, clarity, tone, flow | writing, core | - |
| `jira_writer` | Jira ticket writing with AC, subtasks, and metadata | writing, code | - |
| `email_writer` | Professional email drafting with tone matching | writing | - |
| `constrained_writer` | Character-limited content | writing | - |
| `media_reader` | On-demand file and image analysis (vision) | core | - |

## Skills (Mode Modifiers)

Specialists can operate in different modes:

| Skill | Description |
|-------|-------------|
| `red_team` | Adversarial/attack perspective |
| `blue_team` | Defensive/protection perspective |
| `pro_con` | Balanced pros and cons analysis |

## How to Add a New Specialist

Specialists are file-based — no Python code changes needed.

### Step 1: Create the Specialist Folder

Create `src/agent/prompts/specialists/{name}/` with two files:

**`specialist.yaml`** (config):

```yaml
description: "What this specialist does"
tools:
  - terminal_execute
  - read_file
mcp_servers: []
directive_types:
  - relevant
  - types
# max_turns: 3  # optional, defaults to SPECIALIST_MAX_TURNS (15)
# preset: specialist  # optional, defaults to SPECIALIST_PRESET
```

**`agent.j2`** (prompt template):

```jinja2
You are a specialist.

## Your Task
{{ task }}

{% if context %}
## Context
{{ context }}
{% endif %}

{% if directives %}
## Directives
{{ directives }}
{% endif %}

{% if skill %}
## Mode: {{ skill }}
{% endif %}

## Your Role
[Describe the specialist's focus and approach]

## Output Format
[Describe expected output format]
```

The folder name becomes the specialist slug. The template is always `agent.j2`.

### Step 2: (Optional) Update Delegation Routing

Add to `src/agent/prompts/specialists/delegation.yaml` if you want auto-routing:

```yaml
category_specialist_map:
  your_category: your_name
```

### Step 3: Test

```python
# In agent conversation
result = spawn_specialist(
    specialist_type="your_specialist",
    task="Test task description",
    context="Background information"
)
```

## Directive Filtering

Specialists receive filtered directives based on their domain:

```python
def get_for_subagent(types: List[str]) -> List[Directive]:
    """
    1. All tier 0 directives (always included for safety)
    2. All directives matching any of the given types
    3. Exclude main-agent-only types (tool, memory, metacognition)
    """
```

## Tools for Spawning

**Module:** `src/agent/tools/subagents.py`

### spawn_specialist

```python
spawn_specialist(
    specialist_type: str,      # debugger, architect, secops, etc.
    task: str,                 # Task description
    context: str = "",         # Background information
    extra_directives: str = "",# Additional directive text
    skill: str = None,         # red_team, blue_team, pro_con
    write_to_file: str = None  # Optional file path for output
) -> str
```

### spawn_specialists (Parallel)

```python
spawn_specialists(
    specialist_types: List[str],  # e.g., ["debugger", "secops"]
    task: str,                    # Same task sent to all
    context: str = ""             # Same context sent to all
) -> str
```

### deep_think

```python
deep_think(
    topic: str,           # Topic identifier (used in output filename)
    task: str,            # Detailed task description
    context: str = "",    # Background information
    extra_directives: str = ""  # Additional directive text
) -> str
```

**Output**: Analysis saved to `plans/{topic}-plan.md`

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SPECIALIST_PRESET` | `@preset/standard` | Default preset for specialists |
| `SPECIALIST_MAX_TURNS` | `15` | Maximum turns per specialist |
| `THINKING_PRESET` | `@preset/general` | Preset for deep thinking |
| `THINKING_MAX_TURNS` | `20` | Maximum turns for deep thinking |

## Gotchas

- Specialists run in isolated contexts — they don't share conversation history
- Use `context` parameter to pass relevant background
- Specialist output returns to main agent, which can then synthesize
- MCP servers are configured per-specialist type in the registry
