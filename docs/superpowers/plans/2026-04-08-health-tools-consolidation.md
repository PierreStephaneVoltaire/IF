# Health Tools Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move health tool business logic from `app/src/health/tools.py` into `tools/health/core.py`, making the plugin self-contained.

**Architecture:** Move all 35 health tool functions into `tools/health/core.py`. Update SDK wrappers in `tools/health/tool.py` to import from the new core. Keep infrastructure (`program_store.py`, `rag.py`, `renderer.py`) in `app/src/health/`. Update `main.py` initialization.

**Tech Stack:** Python 3.12, FastAPI, OpenHands SDK 1.11.4, DynamoDB, ChromaDB

---

## File Structure

```
tools/health/
├── core.py          # NEW: Tool functions (moved from app/src/health/tools.py)
├── tool.py          # MODIFY: Update imports to use .core
├── tool.yaml        # UNCHANGED
app/src/health/
├── __init__.py      # MODIFY: Remove tool function exports
├── program_store.py # UNCHANGED
├── rag.py           # UNCHANGED
└── renderer.py      # UNCHANGED
app/src/main.py      # MODIFY: Update initialization
```

---

### Task 1: Create tools/health/core.py

**Files:**
- Create: `tools/health/core.py`
- Source: `app/src/health/tools.py` (copy content, then delete original)

- [ ] **Step 1: Create tools/health/core.py**

Copy the entire content of `app/src/health/tools.py` to `tools/health/core.py`. Update the imports at the top:

```python
"""Health tool plugin core — training program management and powerlifting tools.

Business logic for health tools. Used by tools/health/tool.py SDK wrappers.

Initialization:
    init_tools(store, rag) must be called at startup to set the ProgramStore
    and HealthDocsRAG instances.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

# Import from health infrastructure module (app/src/health/)
from health.program_store import ProgramStore, ProgramNotFoundError

logger = logging.getLogger(__name__)

# ... rest of the file unchanged (lines 21-1299 from original tools.py)
```

- [ ] **Step 2: Verify the new file compiles**

Run: `cd /home/sirsimpalot/Downloads/discord-ai-bot && python -c "import sys; sys.path.insert(0, 'app/src'); from tools.health.core import init_tools; print('OK')"`
Expected: "OK" printed

- [ ] **Step 3: Commit**

```bash
git add tools/health/core.py
git commit -m "feat: create tools/health/core.py with health tool functions

Moves business logic from app/src/health/tools.py to plugin directory."
```

---

### Task 2: Update tools/health/tool.py imports

**Files:**
- Modify: `tools/health/tool.py`

- [ ] **Step 1: Update imports in tool.py**

Replace all `from health import ...` statements with `from .core import ...`. There are approximately 30 such imports throughout the file.

Example change in executor classes:

```python
# Before:
class HealthGetProgramExecutor(ToolExecutor[HealthGetProgramAction, HealthGetProgramObservation]):
    def __call__(self, action: HealthGetProgramAction, conversation=None) -> HealthGetProgramObservation:
        from health import health_get_program
        result = _run_async(health_get_program())
        return HealthGetProgramObservation.from_text(_format_result(result))

# After:
class HealthGetProgramExecutor(ToolExecutor[HealthGetProgramAction, HealthGetProgramObservation]):
    def __call__(self, action: HealthGetProgramAction, conversation=None) -> HealthGetProgramObservation:
        from .core import health_get_program
        result = _run_async(health_get_program())
        return HealthGetProgramObservation.from_text(_format_result(result))
```

Apply this pattern to all executor classes that import from `health`.

- [ ] **Step 2: Update the execute() dispatcher function**

Update the imports at the top of the `execute()` function (around line 1593):

```python
async def execute(name: str, args: Dict[str, Any]) -> str:
    """Route health tool calls to the underlying health module functions."""
    from .core import (
        health_get_program,
        health_get_session,
        health_update_session as do_update_session,
        # ... all other imports
    )
```

- [ ] **Step 3: Verify the updated file compiles**

Run: `cd /home/sirsimpalot/Downloads/discord-ai-bot && python -c "import sys; sys.path.insert(0, 'app/src'); from tools.health.tool import get_tools; print('OK')"`
Expected: "OK" printed

- [ ] **Step 4: Commit**

```bash
git add tools/health/tool.py
git commit -m "refactor: update tools/health/tool.py to import from .core"
```

---

### Task 3: Update app/src/health/__init__.py

**Files:**
- Modify: `app/src/health/__init__.py`

- [ ] **Step 1: Remove tool function exports**

Update `__init__.py` to only export infrastructure classes. Remove all tool function imports and exports:

```python
"""Health module for IF Prototype A1.

Provides DynamoDB-backed training program storage and ChromaDB-backed RAG
for health documents.

Public API:
    - ProgramStore: DynamoDB store for training programs
    - ProgramNotFoundError: Exception when program not found
    - HealthDocsRAG: ChromaDB RAG for health documents
    - render_program_summary: Render program as markdown
    - render_session: Render session as markdown

Note: Tool functions have moved to tools/health/core.py
"""
from health.program_store import ProgramStore, ProgramNotFoundError
from health.rag import HealthDocsRAG
from health.renderer import render_program_summary, render_session

__all__ = [
    "ProgramStore",
    "ProgramNotFoundError",
    "HealthDocsRAG",
    "render_program_summary",
    "render_session",
]
```

- [ ] **Step 2: Verify the updated file compiles**

Run: `cd /home/sirsimpalot/Downloads/discord-ai-bot/app/src && python -c "from health import ProgramStore, HealthDocsRAG; print('OK')"`
Expected: "OK" printed

- [ ] **Step 3: Commit**

```bash
git add app/src/health/__init__.py
git commit -m "refactor: simplify health/__init__.py to only export infrastructure"
```

---

### Task 4: Update app/src/main.py initialization

**Files:**
- Modify: `app/src/main.py` (lines 187-227)

- [ ] **Step 1: Update health module initialization imports**

Change the import from `health` to `tools.health.core`:

```python
    # Health module initialization
    try:
        from tools.health.core import init_tools
        from health import ProgramStore, HealthDocsRAG, ProgramNotFoundError

        program_store = ProgramStore(
            table_name=os.environ.get("IF_HEALTH_TABLE_NAME", "if-health"),
            pk=os.environ.get("HEALTH_PROGRAM_PK", "operator"),
            region=os.environ.get("AWS_REGION", "ca-central-1")
        )

        # Get existing ChromaDB client from user facts store
        chroma_client = None
        try:
            from memory import get_user_fact_store
            user_facts_store = get_user_fact_store()
            chroma_client = user_facts_store._client if user_facts_store else None
        except Exception:
            pass

        health_rag = HealthDocsRAG(
            docs_dir=os.environ.get("HEALTH_DOCS_DIR", "docs/health"),
            chroma_client=chroma_client
        )

        init_tools(program_store, health_rag)
        # ... rest unchanged
```

- [ ] **Step 2: Verify application starts**

Run: `cd /home/sirsimpalot/Downloads/discord-ai-bot/app && timeout 5 python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 || true`
Expected: Application starts without import errors (timeout is expected)

- [ ] **Step 3: Commit**

```bash
git add app/src/main.py
git commit -m "refactor: update main.py to initialize health tools from tools.health.core"
```

---

### Task 5: Delete app/src/health/tools.py

**Files:**
- Delete: `app/src/health/tools.py`

- [ ] **Step 1: Delete the old tools.py file**

Run: `rm /home/sirsimpalot/Downloads/discord-ai-bot/app/src/health/tools.py`
Expected: File deleted successfully

- [ ] **Step 2: Verify no remaining imports reference the old location**

Run: `cd /home/sirsimpalot/Downloads/discord-ai-bot && grep -r "from health import.*health_get" app/src/ || echo "No old imports found"`
Expected: "No old imports found"

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove app/src/health/tools.py (moved to tools/health/core.py)"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run a quick smoke test**

Start the application and verify health tools work:

```bash
cd /home/sirsimpalot/Downloads/discord-ai-bot/app
python -c "
import sys
sys.path.insert(0, 'src')
from tools.health.core import init_tools, health_get_program
print('Health core imports: OK')
"
```

Expected: "Health core imports: OK"

- [ ] **Step 2: Verify tool registry loads health tools**

```bash
cd /home/sirsimpalot/Downloads/discord-ai-bot/app
python -c "
import sys
sys.path.insert(0, 'src')
from agent.tool_registry import init_tool_registry
registry = init_tool_registry()
health_tools = [t for t in registry.list_tools() if t['slug'] == 'health']
print(f'Health tools loaded: {health_tools[0][\"tool_count\"]} tools')
"
```

Expected: "Health tools loaded: 35 tools" (or similar count)
