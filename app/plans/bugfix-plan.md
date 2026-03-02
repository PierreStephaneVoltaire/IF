# Bug Fix Plan - March 1, 2026

## Issues Identified from Error Logs

### 1. ToolExecutor Instantiation Error (CRITICAL)
**Error:** `ToolExecutor() takes no arguments`
**Location:** [`src/agent/tools/user_facts.py:301`](src/agent/tools/user_facts.py:301) and similar lines

**Root Cause:** The code is using `ToolExecutor(function)` as if it's a callable wrapper, but according to the OpenHands SDK docs, `ToolExecutor` is an abstract base class (ABC) that must be subclassed, not instantiated directly.

**Current (Wrong) Pattern:**
```python
Tool(
    name="user_facts_search",
    executor=ToolExecutor(user_facts_search)  # WRONG
)
```

**Correct Pattern (from memory_tools.py):**
```python
class UserFactsSearchExecutor(ToolExecutor[UserFactsSearchAction, UserFactsSearchObservation]):
    def __call__(self, action, conversation=None):
        result = user_facts_search(action.query, action.category, action.limit)
        return UserFactsSearchObservation.from_text(result)

class UserFactsSearchTool(ToolDefinition[UserFactsSearchAction, UserFactsSearchObservation]):
    @classmethod
    def create(cls, conv_state=None, **params):
        return [cls(
            description="...",
            action_type=UserFactsSearchAction,
            observation_type=UserFactsSearchObservation,
            executor=UserFactsSearchExecutor(),
        )]
```

**Fix:** Rewrite user_facts.py to follow the same ToolDefinition pattern used in memory_tools.py.

---

### 2. SQLiteBackend Missing get_session Method
**Error:** `'_SQLiteBackend' object has no attribute 'get_session'`
**Location:** [`src/routing/cache.py:267`](src/routing/cache.py:267)

**Root Cause:** The `_SQLiteBackend` class only exposes an `engine` property, but cache.py is trying to call `storage_backend.get_session()`.

**Current Code in cache.py:**
```python
with storage_backend.get_session() as session:
```

**Fix:** Add a `get_session()` method to `_SQLiteBackend` class:
```python
def get_session(self):
    """Create a new database session.
    
    Returns:
        SQLModel Session instance
    """
    if _engine is None:
        raise RuntimeError("SQLite not initialized. Call init_sqlite().")
    return Session(_engine)
```

---

### 3. ChromaDB Query Error - Multiple Operators
**Error:** `Expected where to have exactly one operator, got {'active': True, 'category': 'model_assessment'}`
**Location:** [`src/agent/session.py:191`](src/agent/session.py:191) via get_operator_context

**Root Cause:** ChromaDB's where clause requires the `$and` operator when combining multiple conditions.

**Current (Wrong) Pattern:**
```python
where = {"active": True, "category": category}
```

**Correct Pattern:**
```python
where = {"$and": [{"active": True}, {"category": category}]}
```

**Fix:** Update the query in [`src/memory/user_facts.py`](src/memory/user_facts.py) search method.

---

### 4. ONNX Model Download During Request
**Error:** Model download happening during request (blocking)
**Location:** ChromaDB embedding model initialization

**Root Cause:** ChromaDB's default embedding function downloads the ONNX model on first use, which happens during the first request.

**Fix:** Initialize the embedding model at startup in main.py:
```python
# In startup lifecycle
from chromadb import HttpClient
# Or pre-initialize the embedding function
import sentence_transformers
# Force model load at startup
```

---

### 5. datetime.utcnow() Deprecation
**Error:** `DeprecationWarning: datetime.datetime.utcnow() is deprecated`
**Location:** [`src/heartbeat/runner.py:332`](src/heartbeat/runner.py:332)

**Current Code:**
```python
now = datetime.utcnow().time()
```

**Fix:**
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc).time()
```

---

## Implementation Order

1. **Fix ToolExecutor** - Most critical, blocks all agent execution
2. **Fix SQLiteBackend.get_session** - Blocks cache persistence
3. **Fix ChromaDB query** - Blocks operator context retrieval
4. **Fix datetime deprecation** - Low priority, just a warning
5. **Move embedding model init** - Performance improvement

## Files to Modify

| File | Changes |
|------|---------|
| `src/agent/tools/user_facts.py` | Rewrite to use ToolDefinition pattern |
| `src/storage/sqlite_backend.py` | Add get_session method to _SQLiteBackend |
| `src/memory/user_facts.py` | Fix ChromaDB where clause to use $and |
| `src/heartbeat/runner.py` | Fix datetime.utcnow() deprecation |
| `src/main.py` | Add embedding model pre-initialization |
