# Health Module Consolidation & Tool-First Architecture (V3)

## 1. Goal

Consolidate the entire health domain into `tools/health/` so that it follows
the same self-contained pattern as every other tool plugin (diary, finance,
proposals). The tool discovers, loads, and initialises itself through the
standard `ToolRegistry` scan — no special-casing in `main.py`. `app/src/health/`
is deleted entirely.

---

## 2. How tool loading works (the pattern to follow)

When the registry loads `tools/health/`:
1. It inserts `tools/health/` into `sys.path[0]`.
2. It `exec`s `tools/health/tool.py` as module `tools.health`.
3. `tool.py` already does `from core import health_get_program` — Python finds
   `core.py` sitting flat inside `tools/health/` because that directory is on
   `sys.path[0]`. ✓

That same rule applies to every other file we move there. After the move,
`tools/health/` on `sys.path` means `import program_store`, `import analytics`,
`import export`, etc. all resolve to the flat files sitting alongside `core.py`.

The target layout is simply:

```
tools/health/
├── tool.yaml            (unchanged)
├── tool.py              (executor wrappers — unchanged)
├── core.py              (updated: lazy self-init, remove init_tools)
├── __init__.py          (empty — unchanged)
├── program_store.py     ← moved from app/src/health/
├── analytics.py         ← moved from app/src/health/
├── export.py            ← moved from app/src/health/
├── fatigue_ai.py        ← moved from app/src/health/
├── correlation_ai.py    ← moved from app/src/health/
├── program_evaluation_ai.py  ← moved from app/src/health/
├── rag.py               ← moved from app/src/health/
├── renderer.py          ← moved from app/src/health/
└── prompt_context.py    ← moved from app/src/health/
```

---

## 3. Structural Changes

### 3.1 Move files — no extra directories

```bash
# Move every file from app/src/health/ flat into tools/health/
mv app/src/health/program_store.py         tools/health/program_store.py
mv app/src/health/analytics.py             tools/health/analytics.py
mv app/src/health/export.py                tools/health/export.py
mv app/src/health/fatigue_ai.py            tools/health/fatigue_ai.py
mv app/src/health/correlation_ai.py        tools/health/correlation_ai.py
mv app/src/health/program_evaluation_ai.py tools/health/program_evaluation_ai.py
mv app/src/health/rag.py                   tools/health/rag.py
mv app/src/health/renderer.py              tools/health/renderer.py
mv app/src/health/prompt_context.py        tools/health/prompt_context.py

# The app/src/health/__init__.py is replaced by tools/health/__init__.py (already empty)
rm app/src/health/__init__.py
rmdir app/src/health/
```

### 3.2 Update all `from health.X import Y` → `from X import Y`

Since `tools/health/` is on `sys.path`, all sibling files are importable
directly by name. Every occurrence of `from health.something import ...` must
become `from something import ...`.

**Affected locations:**

1. **`tools/health/core.py`** — top of file:
   ```python
   # BEFORE:
   from health.program_store import ProgramStore, ProgramNotFoundError

   # AFTER:
   from program_store import ProgramStore, ProgramNotFoundError
   ```

2. **`tools/health/prompt_context.py`** — any cross-module imports, e.g.:
   ```python
   # BEFORE:
   from health.analytics import calculate_dots
   from health.renderer import render_session

   # AFTER:
   from analytics import calculate_dots
   from renderer import render_session
   ```

3. **`tools/health/analytics.py`**, **`tools/health/fatigue_ai.py`**,
   **`tools/health/correlation_ai.py`**,
   **`tools/health/program_evaluation_ai.py`**, **`tools/health/renderer.py`** —
   grep every file and replace any `from health.X import` with `from X import`.
   Use:
   ```bash
   grep -rn "from health\." tools/health/
   ```
   to find every remaining occurrence after the move and fix them.

4. **`tools/health/export.py`** — likely imports `from health.program_store` or
   `from health.renderer` for formatting helpers; update the same way.

> **`tools/health/tool.py` does NOT change** — it already imports
> `from core import ...` (flat) and has no `from health.X` imports.

### 3.3 Make `tools/health/core.py` self-initialising

`core.py` already uses `_get_store()` as the accessor throughout all 1387
lines. The only edits needed are:

**Change 1 — Delete `init_tools()` (lines 28–40):**

```python
# DELETE this entire function:
def init_tools(store: ProgramStore, rag: Any = None) -> None:
    global _store, _rag
    _store = store
    _rag = rag
    logger.info("[HealthTools] Initialized with store and rag")
```

**Change 2 — Make `_get_store()` lazy instead of raising (lines 43–47):**

```python
# BEFORE:
def _get_store() -> ProgramStore:
    """Get the store instance, raising if not initialized."""
    if _store is None:
        raise RuntimeError("Health tools not initialized. Call init_tools() first.")
    return _store

# AFTER:
def _get_store():
    """Lazily create and return the ProgramStore singleton."""
    global _store
    if _store is None:
        import os
        from program_store import ProgramStore as _PS
        _store = _PS(
            table_name=os.environ.get("IF_HEALTH_TABLE_NAME", "if-health"),
            pk=os.environ.get("HEALTH_PROGRAM_PK", "operator"),
            region=os.environ.get("AWS_REGION", "ca-central-1"),
        )
        logger.info("[HealthTools] ProgramStore initialised from env vars")
    return _store
```

Note: The top-level `from program_store import ProgramStore` on line 18
should be **removed** now that `_get_store()` does a lazy local import. This
avoids any module-level import running before the registry has set up
`sys.path`.

**Change 3 — Add `_get_rag()` lazy accessor:**

```python
def _get_rag():
    """Lazily create and return the HealthDocsRAG singleton."""
    global _rag
    if _rag is None:
        import os
        from rag import HealthDocsRAG
        _rag = HealthDocsRAG(
            docs_dir=os.environ.get("HEALTH_DOCS_DIR", "docs/health"),
        )
        logger.info("[HealthTools] HealthDocsRAG initialised from env vars")
    return _rag
```

Update `health_rag_search` to call `_get_rag()`:

```python
async def health_rag_search(query: str, n_results: int = 4) -> list[dict]:
    rag = _get_rag()
    return await rag.query(query, n_results=n_results)
```

No other changes to `core.py`. Every other function already calls `_get_store()`
and needs no edit. Also update the module docstring to remove the stale
"init_tools must be called at startup" instruction.

---

## 4. Remove health initialisation from `app/src/main.py`

Delete the entire health init try/except block:

```python
# DELETE this whole block (~lines 183–229):
# Health module initialization (MUST run before tool registry...)
try:
    import sys as _sys
    _tools_dir = os.environ.get(...)
    _health_plugin_dir = ...
    if _health_plugin_dir not in _sys.path:
        _sys.path.insert(0, _health_plugin_dir)

    from core import init_tools
    from health import ProgramStore, HealthDocsRAG, ProgramNotFoundError
    ...
    init_tools(program_store, health_rag)
    asyncio.create_task(health_rag.index_docs())
    ...
except ImportError as e:
    ...
except Exception as e:
    ...
```

The tool registry's own `_load_plugin_in_process` already does
`sys.path.insert(0, plugin_dir)` when it loads `tools/health/`, so no special
ordering or manual path manipulation is needed.

Also remove:

```python
# DELETE these lines:
from api import health_analytics
...
app.include_router(health_analytics.router)
```

---

## 5. Delete `app/src/api/health_analytics.py`

This file exposed `GET /v1/health/export/xlsx`. It is replaced by the
`export_program_history` tool (Section 6). Delete it **in the same release**
as the portal migration in Section 7 is deployed.

---

## 6. Tool-First Export Architecture

### 6.1 Update `_do_export` in `tools/health/tool.py`

The existing `_do_export` writes to `tempfile.mkstemp`. Replace it so the
file lands in the per-conversation sandbox (serveable via
`GET /files/sandbox/{conversation_id}/{filename}`) and the response carries a
`FILES:` marker:

```python
def _do_export(args):
    import json
    import os
    from config import SANDBOX_PATH
    from export import build_program_xlsx

    conversation_id = args.get("_conversation_id", "default")
    out_dir = os.path.join(SANDBOX_PATH, conversation_id)
    os.makedirs(out_dir, exist_ok=True)

    filename = "program_history.xlsx"
    out_path = os.path.join(out_dir, filename)

    program = _run_async(_get_store().get_program())
    build_program_xlsx(program, out_path)

    payload = json.dumps({
        "filename": filename,
        "message": "Program history exported successfully.",
    })
    return f"{payload}\nFILES: {filename} (Excel export of full program history)"
```

Note the import changed to `from export import build_program_xlsx` (flat,
no `health.` prefix).

Also update `from core import _get_store, _run_async` if `_do_export` is in
`tool.py` — or ensure `_get_store` is imported from `core` at the top of
`tool.py`.

### 6.2 Update `app/src/api/completions.py` — direct_invoke branch

The `if direct_invoke:` block must:
1. Inject `cache_key` as `_conversation_id` in `args`.
2. Strip `FILES:` lines and log file refs.

```python
if direct_invoke:
    import re
    match = re.match(r'^/(\w+)\s*(.*)', last_user_message.strip(), re.DOTALL)
    if not match:
        return json.dumps({"error": "Direct tool invoke expects '/tool_name {json_args}'."}), []

    tool_name, raw_args = match.group(1), match.group(2).strip()
    try:
        args = _parse_json_object_args(raw_args)
    except (json.JSONDecodeError, ValueError) as e:
        return json.dumps({"error": f"Invalid tool arguments: {e}"}), []

    # Inject sandbox key — file-emitting tools write to SANDBOX_PATH/cache_key/
    args["_conversation_id"] = cache_key

    from agent.tool_registry import get_tool_registry
    registry = get_tool_registry()
    if not registry.has_tool(tool_name):
        return json.dumps({"error": f"Unknown tool: {tool_name}"}), []

    result = await registry.execute_tool(tool_name, args)

    # Strip FILES: lines and log refs (mirrors the normal agent path)
    cleaned, file_refs = strip_files_line(result)
    if file_refs:
        log_file_refs(cache_key, file_refs)

    return cleaned, []
```

`strip_files_line` and `log_file_refs` are already imported at the top of
`completions.py` — no new imports needed.

### 6.3 Add `export_program_history` to `get_schemas()` in `tool.py`

```python
# In get_schemas(), add:
"export_program_history": {
    "name": "export_program_history",
    "description": "Export the full training program to an Excel (.xlsx) file.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
},
```

---

## 7. Migrate the Powerlifting Portal Export

`utils/powerlifting-app/backend/src/routes/export.ts` currently calls the
deprecated `GET /v1/health/export/xlsx` endpoint. Replace with the tool-first
flow:

```typescript
import { Router } from 'express'

export const exportRouter = Router()

const IF_API_URL = process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'
// Stable chat_id → predictable sandbox directory for the exported file
const EXPORT_CHAT_ID = process.env.EXPORT_CHAT_ID || 'pl-export'

exportRouter.get('/xlsx', async (_req, res) => {
  try {
    // Step 1: invoke the export tool via X-Direct-Tool-Invoke
    const invokeRes = await fetch(`${IF_API_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Direct-Tool-Invoke': 'true',
      },
      body: JSON.stringify({
        model: 'if-prototype-a1',  // must match API_MODEL_NAME in config
        chat_id: EXPORT_CHAT_ID,
        messages: [{ role: 'user', content: '/export_program_history {}' }],
      }),
    })

    if (!invokeRes.ok) {
      return res.status(invokeRes.status).json({ data: null, error: 'Tool invocation failed' })
    }

    const invokeJson = await invokeRes.json()
    // The tool response is a JSON payload on the first line
    const content: string = invokeJson?.choices?.[0]?.message?.content ?? ''
    let filename = 'program_history.xlsx'
    try {
      const parsed = JSON.parse(content.split('\n')[0])
      if (parsed.filename) filename = parsed.filename
    } catch { /* use default filename */ }

    // Step 2: fetch the binary from the sandbox
    // Note: the files endpoint has NO /v1/ prefix
    const fileRes = await fetch(
      `${IF_API_URL}/files/sandbox/${EXPORT_CHAT_ID}/${filename}`
    )

    if (!fileRes.ok) {
      return res.status(fileRes.status).json({ data: null, error: 'File not found in sandbox' })
    }

    const contentType =
      fileRes.headers.get('content-type') ||
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    res.setHeader('Content-Type', contentType)
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`)

    const arrayBuffer = await fileRes.arrayBuffer()
    res.end(Buffer.from(arrayBuffer))
  } catch (err) {
    res.status(502).json({ data: null, error: `Proxy error: ${err}` })
  }
})
```

> ⚠️ Deploy this TypeScript change **in the same release** as deleting
> `health_analytics.py`.

---

## 8. What does NOT change

| Component | Status |
|-----------|--------|
| `tools/health/tool.py` executor classes | Unchanged |
| `tools/health/tool.py` `execute()` dispatcher | Only `_do_export` updated |
| `tools/health/tool.yaml` | Unchanged |
| `tools/health/__init__.py` | Unchanged (stays empty) |
| All `from core import X` in `tool.py` | Unchanged |
| All function bodies in `core.py` that call `_get_store()` | Unchanged |
| Main portal (`utils/main-portal/`) | Not touched |
| Finance / Diary / Proposals portals | Not touched |
| DynamoDB table names / schema | Not touched |
| `app/src/api/completions.py` normal (non-direct) path | Unchanged |
| Tool registry scan and `_load_plugin_in_process` | Unchanged |

---

## 9. Implementation Order

1. Move all files from `app/src/health/` flat into `tools/health/` (Section 3.1).
2. Grep and replace all `from health.X import` → `from X import` in the moved
   files and in `core.py` (Section 3.2).
3. Update `tools/health/core.py` — remove `init_tools`, make `_get_store()`
   and `_get_rag()` lazy, remove module-level `from program_store import`
   (Section 3.3).
4. Update `tools/health/tool.py` — fix `_do_export` (flat import) and add
   schema entry (Section 6.1, 6.3).
5. Update `app/src/api/completions.py` direct_invoke branch (Section 6.2).
6. Update `utils/powerlifting-app/backend/src/routes/export.ts` (Section 7).
7. Update `app/src/main.py` — delete health init block and health_analytics
   router lines (Section 4).
8. Delete `app/src/api/health_analytics.py` (Section 5).
9. Delete the now-empty `app/src/health/` directory.

---

## 10. Verification Checklist

1. **Server starts** with no `ImportError` or health-related errors in logs.
2. **Tool registry** lists `health` with its full tool count.
3. **Grep confirms no `from health.` remains** in `tools/health/`:
   ```bash
   grep -rn "from health\." tools/health/
   # Expected: no output
   ```
4. **Direct invoke curl test:**
   ```bash
   curl -s -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "X-Direct-Tool-Invoke: true" \
     -d '{"model":"if-prototype-a1","chat_id":"test-export-1",
          "messages":[{"role":"user","content":"/export_program_history {}"}]}'
   ```
   Expected: `choices[0].message.content` contains `{"filename":"program_history.xlsx",...}`.
5. **File is serveable:**
   ```bash
   curl -o out.xlsx http://localhost:8000/files/sandbox/test-export-1/program_history.xlsx
   ```
6. **Portal export button** downloads a valid Excel file.
7. **`GET /v1/health/export/xlsx` returns 404** after cleanup.
8. **Main portal hub status** unaffected (does not call health analytics).
9. **Agent tool calls** (e.g. `health_get_program`) work in the normal
   conversational path.
