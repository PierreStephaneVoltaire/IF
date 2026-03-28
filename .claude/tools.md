# Tool Authoring

Agent tools are Python functions registered with the OpenHands SDK.

**Location:** `src/agent/tools/`

## Tool Registration Pattern

Tools follow the **OpenHands SDK** pattern using Action/Observation/Executor/ToolDefinition classes. They are registered module-level with `register_tool()` and loaded into sessions via getter functions.

In `src/agent/session.py` `execute_agent()`:

```python
tools = get_memory_tools()
tools.extend(get_terminal_tools(session.session_id))
tools.extend(get_media_tools(session.conversation_id))
# ... etc
agent = Agent(llm=llm, tools=tools, ...)
```

## Writing a New Tool

### Step 1: Create Action, Observation, Executor, ToolDefinition

Create or add to a file in `src/agent/tools/`:

```python
from openhands.sdk.tool.tool import Action, Observation, ToolAnnotations, ToolDefinition, ToolExecutor
from openhands.sdk import register_tool
from pydantic import Field

class MyAction(Action):
    param1: str = Field(description="Description shown to the LLM")
    param2: int = Field(default=10, description="Optional param")

class MyObservation(Observation):
    result: str = Field(default="")

class MyExecutor(ToolExecutor):
    def __init__(self, dependency: str):
        self.dependency = dependency

    def __call__(self, action: MyAction, conversation=None) -> MyObservation:
        # Async tools use ThreadPoolExecutor + asyncio.run (see terminal_tools.py)
        result = do_something(action.param1, self.dependency)
        return MyObservation(result=result)

class MyTool(ToolDefinition[MyAction, MyObservation]):
    @classmethod
    def create(cls, conv_state=None, dependency: str = "", **params) -> Sequence[Self]:
        return [cls(
            action_type=MyAction,
            observation_type=MyObservation,
            description="What this tool does — shown to the LLM",
            executor=MyExecutor(dependency=dependency),
            annotations=ToolAnnotations(title="my_tool", readOnlyHint=True, ...),
        )]
```

### Step 2: Register and expose a getter

```python
register_tool("my_tool", MyTool)

def get_my_tools(dependency: str):
    from openhands.sdk import Tool
    return [Tool(name="my_tool", params={"dependency": dependency})]
```

### Step 3: Add to session.py

```python
from agent.tools.my_tools import get_my_tools
# In execute_agent():
tools.extend(get_my_tools(session.session_id))
```

## Tool Categories

| Category | File | Purpose |
|----------|------|---------|
| User Facts | `user_facts.py` | Store/search operator facts |
| Subagents | `subagents.py` | Spawn specialists, deep think |
| Terminal | `terminal_tools.py` | Shell execution, file ops |
| Media | `media_tools.py` | On-demand file/image analysis via vision model |
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
- The `Observation.result` (or equivalent field) is what the LLM reads — keep it a string
- Tools execute synchronously within the agent loop; for async work, use `ThreadPoolExecutor` + `asyncio.run` (see `terminal_tools.py` or `media_tools.py` for the pattern)
- `session.conversation_id` is the raw cache_key; `session.session_id` adds preset slug + random hex — use the right one for file path resolution

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TOOL_OUTPUT_CHAR_LIMIT` | `200000` | Max chars before truncation |
