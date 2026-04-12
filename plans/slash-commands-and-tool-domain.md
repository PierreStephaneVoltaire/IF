# Plan: Slash Commands, Tool Domain Architecture & Analytics Refactor

## Background & Problem Statement

Several design inconsistencies need to be resolved:

1. **Health analytics bypass the agent entirely** — `GET /v1/health/analysis/weekly`, `GET /v1/health/analysis/correlation`, and `POST /v1/health/fatigue-profile/estimate` are raw FastAPI endpoints that call OpenRouter directly inside Python. They are not tools, not governed by the agent, and violate the "this is an AI agent API" domain principle.

2. **Health tool descriptions are weak** — `tools/health/tool.yaml` description is `"Training program management and powerlifting tools"`, which is not distinctive enough for the main agent to route confidently to the right specialist.

3. **No slash command coverage for tools** — Discord slash commands are all hardcoded. The full tool registry and specialist roster have zero Discord slash command representation.

4. **The powerlifting app directly proxies internal FastAPI endpoints** — `utils/powerlifting-app/backend/src/routes/analytics.ts` reaches into `IF_API_URL/v1/health/...` which is an internal implementation detail, not the public API surface.

---

## Architecture Decision: Two Slash Command Modes

### Mode 1 — Human / Agent mode (default)

A human types `/weekly_analysis weeks:4` in Discord, or `/plan build my peaking block`. The message flows through the full agent pipeline. The agent recognizes the slash command, identifies whether it maps to a tool it can invoke directly or a specialist it should delegate to, runs the tool/specialist, and responds conversationally. There is **no special behavior** enforced — the agent can add commentary and interpret the result naturally.

Slash commands from the Discord UI always use this path.

### Mode 2 — Direct Tool Invoke (programmatic callers only)

A programmatic API caller (e.g., the Node.js powerlifting backend) sends:

```
POST /v1/chat/completions
X-Direct-Tool-Invoke: true

{"messages": [{"role": "user", "content": "/weekly_analysis {\"weeks\": 4, \"block\": \"current\"}"}]}
```

The completions endpoint detects the header, parses the tool name from the slash command, looks it up in the tool registry, executes it directly (no LLM, no agent loop), and returns the raw string result as the chat completion content.

This guarantees deterministic JSON output for the powerlifting frontend without any risk of LLM commentary wrapping the result.

---

## Changes Required

### 1. Health Tool Descriptions

**File:** `tools/health/tool.yaml`

Replace weak description with specialist-scoped description that signals to the router this is a sports-scientist-level capability:

```yaml
name: health
description: >
  Sports scientist toolset for powerlifting program management. Exclusively available to
  powerlifting_coach and health_write specialists. Provides: training session CRUD (get,
  create, update, delete, reschedule), program metadata and phases, competition management,
  attempt calculation, supplement protocol, diet notes, IPF weight classes, RPE/e1RM
  calculations, weekly training analysis, exercise ROI correlation analysis, fatigue profile
  estimation, and IPF rulebook semantic search.
version: 1.0.0
scope: specialist
execution: in_process
```

**File:** `specialists/powerlifting_coach/specialist.yaml`

The description is already good but missing the analytics tools explicitly in the tools list (they reference `weekly_analysis`, `analyze_progression`, etc. but these aren't defined in the plugin yet — see Part 2).

**File:** `specialists/health_write/specialist.yaml`

Improve description to clearly separate from `powerlifting_coach`:

```yaml
description: >
  Use health_write exclusively when a write mutation to the training program record is
  needed: logging a completed session, updating body weight, recording RPE, changing
  attempt targets, updating supplement protocol, editing diet notes, or creating/deleting
  sessions. For read-only queries, coaching advice, or analysis — use powerlifting_coach
  instead. Never use health_write for reads.
```

---

### 2. Add Analytics Tools to the Health Plugin

**Problem:** `weekly_analysis`, `correlation_analysis`, `fatigue_profile_estimate` are currently implemented as raw FastAPI endpoints (`app/src/api/health_analytics.py`). They call Python functions directly (`health.analytics.weekly_analysis`, `health.correlation_ai.generate_correlation_report`, `health.fatigue_ai.estimate_fatigue_profile`). We want to expose these as proper SDK tools in the `tools/health` plugin.

**File changes:**

#### `tools/health/core.py` — add 3 wrapper functions

```python
async def weekly_analysis(weeks: int = 1, block: str = "current") -> dict:
    """Wrapper calling health.analytics.weekly_analysis()."""
    ...

async def correlation_analysis(weeks: int = 4, block: str = "current", refresh: bool = False) -> dict:
    """Wrapper calling health.correlation_ai.generate_correlation_report() with DynamoDB cache."""
    ...

async def fatigue_profile_estimate(exercise: dict) -> dict:
    """Wrapper calling health.fatigue_ai.estimate_fatigue_profile()."""
    ...
```

These wrappers import from `health.*` (already on the path) and handle all existing logic including the DynamoDB cache for correlation reports.

#### `tools/health/tool.py` — add 3 new Tool classes

```
WeeklyAnalysisTool / WeeklyAnalysisAction / WeeklyAnalysisObservation / WeeklyAnalysisExecutor
    params: weeks: int (default 1), block: str (default "current")
    description: "Sports scientist weekly training analysis. Returns structured metrics:
    progression rates, fatigue index, compliance, INOL, ACWR, readiness score, attempt
    selection. Use for reviewing the past N weeks of training. Returns JSON."

CorrelationAnalysisTool / ...
    params: weeks: int (default 4), block: str (default "current"), refresh: bool (default False)
    description: "AI-powered exercise ROI correlation analysis. Identifies which accessory
    exercises correlate with improvements in squat/bench/deadlift over a rolling window.
    Results are cached in DynamoDB. Use refresh=true to force regeneration. Returns JSON."

FatigueProfileEstimateTool / ...
    params: exercise: dict (name, category, equipment, primary_muscles, secondary_muscles, cues, notes)
    description: "Estimate the fatigue profile (axial/neural/peripheral/systemic components) for
    an exercise using AI analysis of its biomechanical characteristics. Returns JSON."
```

#### `specialists/powerlifting_coach/specialist.yaml` — add to tools list

```yaml
tools:
  - ...existing tools...
  - weekly_analysis
  - correlation_analysis
  - fatigue_profile_estimate
```

---

### 3. Remove Health Analytics FastAPI Router

**File:** `app/src/main.py`

Remove the line that mounts the `health_analytics` router. The `app/src/api/health_analytics.py` file can be kept for reference but should be clearly marked as deprecated / no longer mounted.

The 3 endpoints (`/v1/health/analysis/weekly`, `/v1/health/analysis/correlation`, `/v1/health/fatigue-profile/estimate`) will no longer exist as HTTP endpoints. All callers must go through `/v1/chat/completions`.

---

### 4. Direct Tool Invoke Path in Completions

**File:** `app/src/api/completions.py`

At the very top of `process_chat_completion_internal`, before any routing or command parsing, check for the `X-Direct-Tool-Invoke: true` header and a `/toolname {...}` message pattern:

```python
# Check for programmatic direct tool invocation
direct_invoke = raw_request.headers.get("X-Direct-Tool-Invoke", "").lower() == "true"
if direct_invoke:
    match = re.match(r'^/(\w+)\s*(.*)', last_user_message.strip(), re.DOTALL)
    if match:
        tool_name = match.group(1)
        raw_args = match.group(2).strip()
        args = json.loads(raw_args) if raw_args else {}
        from agent.tool_registry import get_tool_registry
        registry = get_tool_registry()
        if registry.has_tool(tool_name):
            result = await registry.execute_tool(tool_name, args)
            return result, []
        # Fall through if tool not found
```

This must be done before `parse_command()` and before any routing. It short-circuits into imperatively calling the tool and returning raw output. The `raw_request` object needs to be threaded through (currently `process_chat_completion_internal` doesn't receive the request — the call site needs to pass headers or the direct_invoke flag).

**Signature change:** `process_chat_completion_internal` gains an optional `direct_invoke: bool = False` param. The `chat_completions` route handler reads the header and passes it through.

---

### 5. Auto-Register Tools + Specialists as Discord Slash Commands

**File:** `app/src/channels/slash_commands.py`

Add a new function `register_dynamic_commands(tree, ...)` called from `setup_command_tree` after the static commands are registered:

#### Tool commands

```python
def _register_tool_commands(tree, channel_id, conversation_id):
    from agent.tool_registry import get_tool_registry
    registry = get_tool_registry()
    for config in registry._tools.values():
        for tool_name, schema in config.schemas.items():
            # Skip if already registered
            if tool_name in STATIC_COMMAND_NAMES:
                continue
            discord_name = tool_name[:32]  # Discord max 32 chars
            description = (schema.get("description") or tool_name)[:100]

            # Register with optional json_args string parameter
            @tree.command(name=discord_name, description=description)
            @app_commands.describe(args="Optional JSON arguments e.g. {\"weeks\": 4}")
            async def tool_handler(interaction, args: str = "", _name=tool_name):
                await interaction.response.defer()
                # Build message and flow through normal agent pipeline
                message_content = f"/{_name} {args}".strip()
                # ... route through process_chat_completion_internal (agent path)
                result = await _invoke_via_agent(message_content, channel_id, conversation_id)
                await _send_chunked(interaction, result)
```

#### Specialist commands

```python
def _register_specialist_commands(tree, channel_id, conversation_id):
    from agent.specialists import list_specialists
    for spec in list_specialists():
        if spec.slug in STATIC_COMMAND_NAMES:
            continue
        discord_name = spec.slug[:32]
        description = spec.description[:100]

        @tree.command(name=discord_name, description=description)
        @app_commands.describe(args="Task or question for the specialist")
        async def specialist_handler(interaction, args: str = "", _slug=spec.slug):
            await interaction.response.defer()
            message_content = f"/{_slug} {args}".strip()
            result = await _invoke_via_agent(message_content, channel_id, conversation_id)
            await _send_chunked(interaction, result)
```

`_invoke_via_agent` calls `process_chat_completion_internal` with no `X-Direct-Tool-Invoke` header, allowing the agent to respond naturally.

`_send_chunked` splits responses over Discord's 2000-char limit.

`STATIC_COMMAND_NAMES` is the set of hardcoded command names (`end_convo`, `pondering`, `clear`, `reflect`, `gaps`, `patterns`, `opinions`, `growth`, `meta`, `tools`) to prevent collisions.

---

### 6. Powerlifting App Backend — Analytics via Chat Completions

**File:** `utils/powerlifting-app/backend/src/routes/analytics.ts`

Replace the 3 direct proxy routes with `/v1/chat/completions` calls using `X-Direct-Tool-Invoke: true`:

```typescript
const IF_API_URL =
  process.env.IF_API_URL ||
  "http://if-agent-api.if-portals.svc.cluster.local:8000";
const AGENT_MODEL = process.env.AGENT_MODEL || "if-agent";

async function invokeToolDirect(
  toolName: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  const content = `/${toolName} ${JSON.stringify(args)}`;
  const response = await fetch(`${IF_API_URL}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Direct-Tool-Invoke": "true",
    },
    body: JSON.stringify({
      model: AGENT_MODEL,
      messages: [{ role: "user", content }],
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Agent API error ${response.status}: ${text}`);
  }
  const body = await response.json();
  const rawContent = body?.choices?.[0]?.message?.content ?? "";
  return extractJson(rawContent);
}

function extractJson(text: string): unknown {
  // Safety shim: extract first valid JSON object or array from response
  const match = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
  if (!match)
    throw new Error(`No JSON in tool response: ${text.slice(0, 200)}`);
  return JSON.parse(match[0]);
}

// GET /api/analytics/analysis/weekly?weeks=N&block=X
analyticsRouter.get("/analysis/weekly", async (req, res) => {
  try {
    const weeks = parseInt(req.query.weeks as string) || 1;
    const block = (req.query.block as string) || "current";
    const data = await invokeToolDirect("weekly_analysis", { weeks, block });
    res.json({ data, error: null });
  } catch (err) {
    res
      .status(502)
      .json({ data: null, error: `Tool invocation error: ${err}` });
  }
});

// GET /api/analytics/correlation?weeks=N&block=X&refresh=bool
analyticsRouter.get("/correlation", async (req, res) => {
  try {
    const weeks = parseInt(req.query.weeks as string) || 4;
    const block = (req.query.block as string) || "current";
    const refresh = req.query.refresh === "true";
    const data = await invokeToolDirect("correlation_analysis", {
      weeks,
      block,
      refresh,
    });
    res.json({ data, error: null });
  } catch (err) {
    res
      .status(502)
      .json({ data: null, error: `Tool invocation error: ${err}` });
  }
});

// POST /api/analytics/fatigue-profile/estimate
analyticsRouter.post("/fatigue-profile/estimate", async (req, res) => {
  try {
    const data = await invokeToolDirect("fatigue_profile_estimate", req.body);
    res.json({ data, error: null });
  } catch (err) {
    res
      .status(502)
      .json({ data: null, error: `Tool invocation error: ${err}` });
  }
});
```

---

### 7. Powerlifting App Frontend — No Change Needed

The frontend (`src/api/analytics.ts`) calls the Node.js backend, which returns `{ data: <tool result>, error: null }` — same shape as before. No frontend changes required as long as the tool output shape matches what the existing TypeScript interfaces expect (it does — the same Python functions are called, just via a different path).

---

## File Change Summary

| File                                                     | Change Type     | Summary                                                |
| -------------------------------------------------------- | --------------- | ------------------------------------------------------ |
| `tools/health/tool.yaml`                                 | Update          | Specialist-scoped description                          |
| `tools/health/tool.py`                                   | Add             | 3 new analytics tool classes                           |
| `tools/health/core.py`                                   | Add             | 3 wrapper functions for analytics/AI features          |
| `specialists/health_write/specialist.yaml`               | Update          | Sharper write-only description                         |
| `specialists/powerlifting_coach/specialist.yaml`         | Update          | Add 3 analytics tools to tools list                    |
| `app/src/api/health_analytics.py`                        | Mark deprecated | Add header comment, keep file                          |
| `app/src/main.py`                                        | Update          | Remove health_analytics router mount                   |
| `app/src/api/completions.py`                             | Update          | Add `direct_invoke` param, short-circuit path          |
| `app/src/channels/slash_commands.py`                     | Update          | Auto-register tools + specialists from registries      |
| `utils/powerlifting-app/backend/src/routes/analytics.ts` | Rewrite         | Use `/v1/chat/completions` with `X-Direct-Tool-Invoke` |

---

## Execution Order

1. `tools/health/tool.yaml` — description update (no code risk)
2. `specialists/health_write/specialist.yaml` — description update
3. `specialists/powerlifting_coach/specialist.yaml` — description + tools list update
4. `tools/health/core.py` — add analytics wrapper functions
5. `tools/health/tool.py` — add analytics tool SDK classes
6. `app/src/api/health_analytics.py` — add deprecation header comment
7. `app/src/main.py` — remove health_analytics router mount
8. `app/src/api/completions.py` — add `direct_invoke` support
9. `app/src/channels/slash_commands.py` — add dynamic slash command registration
10. `utils/powerlifting-app/backend/src/routes/analytics.ts` — rewrite 3 routes

---

## Risks & Mitigations

| Risk                                                         | Mitigation                                                                                |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| `weekly_analysis` tool output shape differs from old API     | Same Python function called — shape is identical                                          |
| Discord slash command name collision (32-char limit)         | Truncate + skip if name already in static set                                             |
| Too many Discord slash commands registered (100 guild limit) | Only `scope: specialist` tools are registered; scope filtering reduces count              |
| `X-Direct-Tool-Invoke` bypasses auth                         | Header is only accepted from internal cluster traffic; external callers don't set it      |
| `correlation_analysis` has 30s+ response time                | Existing timeout already handled; Node.js uses default fetch timeout (increase if needed) |
