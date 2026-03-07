# Plan: Extract Inline Prompts to Template Files

## Summary

Found **6 inline prompts** in Python source files that should be extracted to `.j2` (Jinja2) or `.md` (Markdown) template files.

## Current State

The project already has a prompts directory at [`src/agent/prompts/`](src/agent/prompts/) containing:
- [`pondering_addendum.md`](src/agent/prompts/pondering_addendum.md) - Static markdown prompt
- [`system_prompt.j2`](src/agent/prompts/system_prompt.j2) - Simple Jinja2 template

## Prompts to Extract

### 1. OPINION_FORMATION_PROMPT
**File:** [`src/agent/reflection/opinion_formation.py`](src/agent/reflection/opinion_formation.py:24)
**Type:** `.j2` (has variable placeholders)
**Placeholders:** `{topic}`, `{user_position}`

```python
OPINION_FORMATION_PROMPT = """
You are forming an opinion on a topic where the operator has expressed a position.

Topic: {topic}
Operator's Position: {user_position}
...
"""
```

**Target:** `src/agent/prompts/opinion_formation.j2`

---

### 2. REFLECTION_PROMPT
**File:** [`src/agent/reflection/engine.py`](src/agent/reflection/engine.py:51)
**Type:** `.md` (static content, no placeholders)

```python
REFLECTION_PROMPT = """
You are performing a reflection analysis. You have access to:
1. Recent conversation summaries
...
"""
```

**Target:** `src/agent/prompts/reflection.md`

---

### 3. REWRITE_PROMPT
**File:** [`src/agent/tools/directive_tools.py`](src/agent/tools/directive_tools.py:24)
**Type:** `.j2` (has variable placeholder)
**Placeholders:** `{raw_content}`

```python
REWRITE_PROMPT = """You are rewriting a directive for an AI agent's behavioral system.
...
Operator intent:
{raw_content}"""
```

**Target:** `src/agent/prompts/directive_rewrite.j2`

---

### 4. TERMINAL_SYSTEM_PROMPT
**File:** [`src/agent/tools/terminal_tools.py`](src/agent/tools/terminal_tools.py:661)
**Type:** `.md` (static content, no placeholders)

```python
TERMINAL_SYSTEM_PROMPT = """
You have a persistent Linux terminal accessible via the `terminal_execute` tool.
...
"""
```

**Target:** `src/agent/prompts/terminal_system.md`

---

### 5. SUMMARY_PROMPT
**File:** [`src/memory/summarizer.py`](src/memory/summarizer.py:26)
**Type:** `.j2` (has variable placeholder)
**Placeholders:** `{conversation}`

```python
SUMMARY_PROMPT = """Summarize this conversation exchange in 2-3 sentences.
...
Conversation:
{conversation}
..."""
```

**Target:** `src/agent/prompts/summary.j2`

---

### 6. TOPIC_SHIFT_PROMPT
**File:** [`src/routing/topic_shift.py`](src/routing/topic_shift.py:73)
**Type:** `.j2` (has variable placeholders)
**Placeholders:** `{anchor_messages}`, `{current_messages}`

```python
TOPIC_SHIFT_PROMPT = """You are a conversation topic classifier...
## PREVIOUS CONVERSATION CONTEXT (used to select the current specialist):
{anchor_messages}
## NEW MESSAGES (most recent):
{current_messages}
..."""
```

**Target:** `src/agent/prompts/topic_shift.j2`

---

## Implementation Steps

### Step 1: Create template files
Create6 new template files in `src/agent/prompts/`:

| File | Type | Source |
|------|------|--------|
| `opinion_formation.j2` | Jinja2 | `opinion_formation.py` |
| `reflection.md` | Markdown | `engine.py` |
| `directive_rewrite.j2` | Jinja2 | `directive_tools.py` |
| `terminal_system.md` | Markdown | `terminal_tools.py` |
| `summary.j2` | Jinja2 | `summarizer.py` |
| `topic_shift.j2` | Jinja2 | `topic_shift.py` |

### Step 2: Create prompt loader utility
Create a utility module `src/agent/prompts/loader.py` with functions:
- `load_prompt(name: str) -> str` - Load static prompts from `.md` files
- `render_template(name: str, **kwargs) -> str` - Render Jinja2 templates with variables

### Step 3: Update source files
Modify each source file to:
1. Remove inline `*_PROMPT` variable
2. Import the prompt loader
3. Replace `PROMPT.format(...)` calls with `render_template(...)` or `load_prompt(...)`

### Step 4: Convert placeholder syntax
For `.j2` files, convert Python format string syntax to Jinja2:
- `{variable}` → `{{ variable }}`

---

## File Changes Summary

### New Files
- `src/agent/prompts/opinion_formation.j2`
- `src/agent/prompts/reflection.md`
- `src/agent/prompts/directive_rewrite.j2`
- `src/agent/prompts/terminal_system.md`
- `src/agent/prompts/summary.j2`
- `src/agent/prompts/topic_shift.j2`
- `src/agent/prompts/loader.py`

### Modified Files
- `src/agent/reflection/opinion_formation.py` - Remove prompt, use loader
- `src/agent/reflection/engine.py` - Remove prompt, use loader
- `src/agent/tools/directive_tools.py` - Remove prompt, use loader
- `src/agent/tools/terminal_tools.py` - Remove prompt, use loader
- `src/memory/summarizer.py` - Remove prompt, use loader
- `src/routing/topic_shift.py` - Remove prompt, use loader

---

## Questions for User

1. Should all prompts go in `src/agent/prompts/` or should we organize by module (e.g., `src/agent/reflection/prompts/`, `src/routing/prompts/`)?
2. For Jinja2 templates, should we keep using Python's `.format()` syntax or fully convert to Jinja2 `{{ }}` syntax?
