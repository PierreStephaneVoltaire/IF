# External Tool Translator Layer — Implementation Plan

## Context

The tool plugin discovery system is now implemented. The `ToolRegistry` scans an external tools folder, dynamically loads tools, and makes them available to specialists and (via `discover_tools`/`use_tool`) the main agent. 

Now we need the registry to accept tools from external ecosystems — specifically MCP servers and SKILL.md-format skills (used by Claude Code, OpenClaw/ClawHub, Cursor, Gemini CLI, Codex CLI). These ecosystems use different wire formats than OpenHands SDK's Action/Observation/Executor/ToolDefinition pattern. We need translator layers that bridge each format into OpenHands-compatible tools so the registry can treat them identically to native tools.

## Goal

Implement a `ToolSource` abstraction in the `ToolRegistry` so it can load tools from multiple sources. Each source has its own loader/translator that outputs standard OpenHands `ToolDefinition` objects. The rest of the system (specialists, `discover_tools`, `use_tool`) doesn't know or care where a tool came from.

Three source types:

1. **Native** — existing `tool.yaml` + `tool.py` folders (already implemented)
2. **MCP** — connect to MCP server endpoints, enumerate tools, translate calls
3. **SKILL.md** — load Claude Code / OpenClaw skill folders, translate into tools or context injections

## Wire Format Reference

### OpenHands SDK (target format — everything must translate INTO this)

- **ToolDefinition**: `name`, `description`, JSON schema for parameters
- **Action**: dataclass with typed input params (constructed from schema)
- **Executor**: receives Action, runs logic, returns Observation  
- **Observation**: must inherit `TextObservation` (see `agent/tools/base.py`) for `to_llm_content` to work
- Registration via `register_tool()`, discovery via `get_*_tools()` getters

### MCP (JSON-RPC 2.0)

**Discovery** — `tools/list` response:
```json
{
  "tools": [
    {
      "name": "calculate_sum",
      "description": "Add two numbers together",
      "inputSchema": {
        "type": "object",
        "properties": {
          "a": {"type": "number"},
          "b": {"type": "number"}
        },
        "required": ["a", "b"]
      }
    }
  ]
}
```

**Invocation** — `tools/call` request:
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "calculate_sum",
    "arguments": {"a": 10, "b": 5}
  }
}
```

**Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": {
    "content": [{"type": "text", "text": "Result: 15"}],
    "isError": false
  }
}
```

Errors are returned inside `result` with `isError: true`, NOT as JSON-RPC protocol errors. This is intentional — it lets the LLM see the error and self-correct.

**Transport**: stdio (local processes), SSE, or Streamable HTTP (remote servers). For IF, we only care about remote (SSE/HTTP) since MCP servers would be external services.

**Lifecycle**: `initialize` handshake → capability negotiation → `tools/list` → `tools/call` → repeat. Each client maintains a 1:1 connection with a server.

### SKILL.md (folder convention, no wire protocol)

**Structure**:
```
skill-name/
├── SKILL.md          # YAML frontmatter + markdown instructions
├── scripts/          # Executable Python/Bash (optional)
├── references/       # Reference docs loaded on demand (optional)
└── assets/           # Templates, configs (optional)
```

**SKILL.md format**:
```markdown
---
name: my-skill
description: What this skill does and when to use it
---

# Instructions

When doing X, always:
1. Step one
2. Step two

## Scripts

Use `scripts/run.py` for deterministic execution of Y.
```

**Key detail**: Skills have a three-level loading system:
1. **Metadata** (frontmatter) — always in context (~100 words), used for triggering
2. **SKILL.md body** — loaded only when skill triggers
3. **Bundled resources** — scripts/references loaded/executed as needed

Skills with `scripts/` contain actual executable code. Skills without scripts are pure prompt/instruction injection.

## Translator Architecture

### ToolSource Interface

```python
class ToolSource(ABC):
    """Base class for all tool loading sources."""
    
    @abstractmethod
    async def discover(self) -> list[ToolDefinition]:
        """Return all available tools from this source."""
        
    @abstractmethod
    async def execute(self, tool_name: str, params: dict) -> TextObservation:
        """Execute a tool by name with given parameters."""
        
    @abstractmethod
    def source_type(self) -> str:
        """Return source identifier: 'native', 'mcp', 'skill'"""
```

The `ToolRegistry` holds a list of `ToolSource` instances. `discover_tools` aggregates across all sources. `use_tool` routes to the correct source based on which source registered the tool name.

### MCP Translator

**MCPToolSource** — connects to an MCP server, translates between MCP and OpenHands.

Discovery flow:
1. Connect to MCP server URL (SSE or Streamable HTTP transport)
2. Send `initialize` request, negotiate capabilities
3. Call `tools/list`, receive tool definitions
4. For each MCP tool, generate an OpenHands `ToolDefinition`:
   - `name` → prefix with source name to avoid collisions (e.g., `mcp_yahoo_finance.get_quote`)
   - `description` → pass through
   - `inputSchema` → translate JSON Schema to Action dataclass fields, or use a generic `MCPAction` with a `tool_name: str` and `arguments: dict` 

Execution flow:
1. Receive OpenHands Action (tool name + params)
2. Construct MCP `tools/call` JSON-RPC request with `name` and `arguments`
3. Send to MCP server, await response
4. Extract `content[].text` from response (may be multiple content blocks — concatenate)
5. Check `isError` flag
6. Wrap result text into a `TextObservation` subclass and return

Error handling:
- MCP tool errors (`isError: true`) → return as Observation with error text (let the LLM see it)
- Transport errors (connection failed, timeout) → log error, return Observation with error message
- Never crash the app on MCP failures

**Configuration** — MCP sources defined in a YAML config (similar to existing `mcp_servers.yaml`):
```yaml
mcp_sources:
  - name: yahoo_finance
    url: https://mcp.yahoo-finance.example.com/sse
    transport: sse
  - name: github
    url: https://mcp.github.com/mcp
    transport: streamable_http
```

**Note**: IF already has MCP server integration (`mcp_servers/config.py`). Study how the existing MCP servers are consumed and determine if the translator should build on top of that existing code or replace it. The goal is to unify MCP tool access through the registry rather than having two separate paths.

### SKILL.md Translator

**SkillToolSource** — loads SKILL.md folders, translates into tools or prompt injections.

Two categories of skills:

**Skills WITH scripts** (executable):
1. Parse SKILL.md frontmatter for name, description
2. Scan `scripts/` directory for executable files
3. For each script, register a `ToolDefinition`:
   - `name` → `skill_{skill_name}_{script_name}` 
   - `description` → extracted from SKILL.md instructions for that script
   - `inputSchema` → parse from script docstrings/comments, or use generic `{"command_args": "string"}`
4. On execution: run the script via terminal tools (`terminal_execute`), capture output, wrap in `TextObservation`

**Skills WITHOUT scripts** (prompt-only):
1. Parse SKILL.md frontmatter for name, description
2. Register as a pseudo-tool that injects the SKILL.md body into the specialist's system prompt as additional context/directives
3. This is closer to how directives work than how tools work — consider whether these should route through the directive system instead of the tool registry
4. On "execution": return the SKILL.md body as an Observation so the agent has the instructions in context

**Loading from ClawHub/marketplace**:
- For now, skills must be placed in a local folder (the external tools mount point or a dedicated `skills/` mount)
- Future: a CLI or admin endpoint that fetches a skill from a registry URL, downloads it to the skills folder, and triggers a reload

**Configuration** — skill source paths in config:
```yaml
skill_sources:
  - path: /app/skills        # mounted volume
  - path: ./local-skills     # local dev fallback
```

### Exposing OpenHands Tools as MCP (outbound — future/optional)

This is the reverse direction: making IF's tools consumable by external MCP clients. Not required now but the architecture should not prevent it.

The shape is straightforward:
- `tools/list` handler iterates the registry, serializes each `ToolDefinition` as MCP tool schema
- `tools/call` handler deserializes MCP arguments into the appropriate Action, runs the Executor, serializes the Observation as MCP `content` blocks
- Expose via a Streamable HTTP endpoint on the FastAPI app

## Existing Code to Study

1. **`mcp_servers/config.py`** — how MCP servers are currently configured and resolved. The translator should either extend or replace this.
2. **`agent/tools/base.py`** — `TextObservation` base class that all translated observations must inherit from.
3. **Tool registration pattern** — `register_tool()` and the `get_*_tools()` getter pattern. Translated tools must integrate with this.
4. **`ToolRegistry`** — the just-implemented plugin registry. The `ToolSource` abstraction plugs into this.
5. **Specialist YAML configs** — how specialists declare which tools they need. Translated tools must be referenceable by the same mechanism.

## Implementation Steps

1. Read the existing `ToolRegistry` implementation to understand how native tools are loaded and served
2. Read `mcp_servers/config.py` and trace how MCP servers are currently used by specialists — understand the existing bridge
3. Read `agent/tools/base.py` for `TextObservation` contract
4. Design the `ToolSource` interface and refactor `ToolRegistry` to use it (native tools become `NativeToolSource`)
5. Implement `MCPToolSource`:
   - MCP client connection (SSE and/or Streamable HTTP transport)
   - `initialize` handshake
   - `tools/list` → `ToolDefinition` translation
   - `tools/call` invocation with Action params → MCP arguments mapping
   - Response → `TextObservation` translation
   - Error handling (tool errors, transport errors)
6. Add MCP source configuration to YAML config
7. Test with an existing MCP server (e.g., the `time` server already in use)
8. Implement `SkillToolSource`:
   - SKILL.md frontmatter parser
   - Script-based skill → tool registration with terminal execution
   - Prompt-only skill → context injection or pseudo-tool
   - Folder scanning with error handling
9. Add skill source configuration to YAML config  
10. Test with a sample SKILL.md skill (grab one from the Anthropic skills repo)
11. Update `discover_tools` and `use_tool` system tools to aggregate across all sources
12. Add startup logging for each source: tools discovered, tools failed, source connection status
13. Update documentation (CLAUDE.md, README) with the new source types
