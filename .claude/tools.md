# Tool Authoring

Agent tools are Python functions registered with the OpenHands SDK.

**Location:** `src/agent/tools/`

## Tool Registration Pattern

Tools are registered in `src/agent/session.py`:

```python
def _register_tools(self, agent: CodeActAgent) -> None:
    """Register all agent tools."""
    # Memory tools
    from .tools.user_facts import register_user_facts_tools
    register_user_facts_tools(agent, self.user_fact_store)

    # Terminal tools
    from .tools.terminal_tools import register_terminal_tools
    register_terminal_tools(agent, self.terminal_client)

    # ... more tool registrations
```

## Writing a New Tool

### Step 1: Create the Tool Function

Create or add to a file in `src/agent/tools/`:

```python
from openhands.events.action.message import MessageAction
from openhands.events.observation.message import MessageObservation

def my_new_tool(
    param1: str,
    param2: int = 10,
) -> str:
    """
    Brief description of what the tool does.

    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)

    Returns:
        Description of return value
    """
    # Implementation
    result = do_something(param1, param2)
    return f"Result: {result}"
```

### Step 2: Create Registration Function

```python
def register_my_tools(agent: CodeActAgent, dependency: SomeDependency) -> None:
    """Register tools with the agent."""

    @agent.tool
    def my_new_tool(param1: str, param2: int = 10) -> str:
        """
        Brief description for LLM.

        Args:
            param1: Description
            param2: Description (default: 10)

        Returns:
            Description
        """
        # Use dependency
        result = dependency.do_something(param1, param2)
        return f"Result: {result}"
```

### Step 3: Register in session.py

```python
def _register_tools(self, agent: CodeActAgent) -> None:
    # ... existing registrations ...

    from .tools.my_tools import register_my_tools
    register_my_tools(agent, self.my_dependency)
```

## Tool Categories

| Category | File | Purpose |
|----------|------|---------|
| User Facts | `user_facts.py` | Store/search operator facts |
| Subagents | `subagents.py` | Spawn specialists, deep think |
| Terminal | `terminal_tools.py` | Shell execution, file ops |
| Directives | `directive_tools.py` | Directive CRUD |
| Finance | `finance_tools.py` | Financial data access |
| Health | `health_tools.py` | Training program management |
| Context | `context_tools.py` | Context injection |
| Capability | `capability_tracker.py` | Gap tracking |
| Opinion | `opinion_tools.py` | Opinion management |
| Diary | `diary_tools.py` | Diary entry tools |
| Proposal | `proposal_tools.py` | Proposal management |
| Session | `session_reflection.py` | Post-session reflection |

## Docstring Guidelines

The docstring is what the LLM sees — make it clear:

1. **First line**: Brief description (what it does)
2. **Args section**: Each parameter with description
3. **Returns section**: What the tool outputs
4. **Usage hints**: When to use this tool

```python
def user_facts_search(query: str, category: str = None, limit: int = 5) -> str:
    """
    Search stored user facts using semantic similarity.

    Use this when you need to recall information about the operator's
    preferences, skills, past discussions, or any stored context.

    Args:
        query: Natural language search query
        category: Optional category filter (e.g., "preference", "skill")
        limit: Maximum results to return (default: 5)

    Returns:
        Formatted list of matching facts with content and metadata
    """
```

## Gotchas

- Tool output is truncated at `TOOL_OUTPUT_CHAR_LIMIT` (default: 200K chars)
- Use type hints — they're included in the tool schema
- Default values should be sensible for most use cases
- Return strings, not complex objects — the LLM reads the output
- Tools run synchronously within the agent loop

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TOOL_OUTPUT_CHAR_LIMIT` | `200000` | Max chars before truncation |
