# pod_logs.txt — Bug Report

Analysis of `pod_logs.txt` (24,515 lines, covering startup at `2026-04-07 08:56:50` through runtime up to `~09:33:52`). Scope is strictly diagnostic — no code changes. Fixes are deferred.

---

## 1. `ImportError: cannot import name 'terminal_execute' from 'agent.tools.terminal_tools'` (CRITICAL)

**Occurrences:** `pod_logs.txt:3080`, `pod_logs.txt:11830`

**Symptom:**
```
ERROR | agent.tools.subagents | [Subagent] Error: cannot import name 'terminal_execute'
  from 'agent.tools.terminal_tools' (/app/src/agent/tools/terminal_tools.py)
```

**What failed:** Every specialist subagent spawn that expects `terminal_execute` as a tool (`planner` at 09:02:15, `health_write` at 09:15:30) crashes at import time. The subagent returns a pre-canned error string of length 141 instead of a real result, and the main agent falls back to "Proceeding with direct response" (see `pod_logs.txt:3092-3095`).

**Why:** In the OpenHands SDK pattern documented in `.claude/CLAUDE.md`, tool modules export getter functions (e.g. `get_terminal_tools()`), and individual executors are exposed via `register_tool()` / PascalCase class names — not as snake_case top-level attributes. The subagent loader in `agent/tools/subagents.py` is doing `from agent.tools.terminal_tools import terminal_execute`, which is not a symbol that module exports. The terminal tool must be obtained through the registry (e.g. `get_terminal_tools()` or the registered ToolDefinition), not as a bare function import.

**Blast radius:** Disables *every* subagent that relies on the terminal — per the README this includes `coder`, `scripter`, `debugger`, `secops`, `devops`, `file_generator`, `git_ops`, `code_reviewer`, `code_explorer`, `doc_generator`, `test_writer`, `refactorer`, `incident_responder`, `performance_analyst`, `project_manager`, `resume`, `cover_letter`, `pdf_generator`, `changelog_writer`, `data_analyst`, `sql_analyst`, `ml_tutor`, `migration_planner`. Also affects `planner` and `health_write` as observed. The delegation pipeline is effectively no-op for any terminal-using specialist.

---

## 2. Health module init failure — `UnboundLocalError` on `asyncio` (HIGH)

**Occurrence:** `pod_logs.txt:79`

**Symptom:**
```
WARNING | main | Health module initialization failed: cannot access local variable
  'asyncio' where it is not associated with a value
```

**Why:** Classic Python "shadowed import" bug. Somewhere inside the health init function, `asyncio` is referenced before assignment — almost certainly because there is a *nested* `import asyncio` (conditional, inside an `if`/`try`) that causes Python to treat `asyncio` as a local for the entire function body. Any read of `asyncio` before the conditional import hits executes `UnboundLocalError` masked as `cannot access local variable`.

**Why it matters:** The health module (DynamoDB program store + ChromaDB RAG) is initialized as "failed but warned" — startup continues, but per README/CLAUDE.md the health subsystem (program CRUD, session logging, RAG over IPF rulebook / supplements / anti-doping PDFs) is silently broken. Combined with bug #1, training workflows are doubly broken.

---

## 3. Tool registry not initialized at dependency-install time (MEDIUM — initialization-order bug)

**Occurrence:** `pod_logs.txt:74`

**Symptom:**
```
WARNING | agent.tool_registry | Tool registry not initialized, cannot install deps
INFO    | agent.tool_registry | Tool registry: 4 external tools loaded: [...]
```

**Why:** A dependency-install hook is called on the registry *before* it has been constructed. Next line shows the registry populating successfully with 4 plugins — so the install step is reached via a code path that runs earlier in lifespan than the constructor. The `requirements.txt` declared by each `tools/*/tool.yaml` plugin (mentioned in CLAUDE.md as an optional per-plugin pip deps file) will not be auto-installed on first boot.

**Blast radius:** Silent — any plugin depending on an uninstalled pip package will blow up later at tool-invoke time with a confusing `ModuleNotFoundError`, not at startup.

---

## 4. Apache Tika not available → PDF extraction will fail silently (MEDIUM)

**Occurrence:** `pod_logs.txt:77`

**Symptom:**
```
WARNING | health.rag | [HealthDocsRAG] Apache Tika not available. PDF extraction will fail.
```

**Why:** The image/pod doesn't have `tika` on the PATH or the Tika server isn't reachable. Per CLAUDE.md the health RAG specifically uses Apache Tika for PDF extraction (IPF rulebook, anti-doping list, supplement PDFs) with 500-token / 50-overlap chunking. All PDF-backed RAG queries will return no documents. The warning is logged but the subsystem continues — failures will surface as empty RAG hits, not hard errors.

---

## 5. `User facts store initialized (-1 active facts)` — negative sentinel leaks into log (LOW)

**Occurrence:** `pod_logs.txt:57`

**Symptom:**
```
INFO | main | User facts store initialized (-1 active facts)
```

**Why:** The LanceDB-backed `UserFactStore` returns `-1` as a sentinel for "count unknown / not supported" (likely because LanceDB `table.count_rows()` isn't called here, or the init path skips the scan for performance). The log string formats the sentinel verbatim instead of branching to "(count unavailable)". Cosmetic but misleading — later in the log the reflection engine reports "146 facts" (`pod_logs.txt:169`), proving facts do exist.

---

## 6. `latency=Nonems, throughput=None tok/s` — None rendered instead of skipped (LOW)

**Occurrences:** `pod_logs.txt:105, 109, 124`
```
google/gemini-3.1-flash-lite-preview: latency=Nonems, throughput=None tok/s
google/gemini-3.1-pro-preview:         latency=Nonems, throughput=None tok/s
openai/o4-mini-deep-research:          latency=Nonems, throughput=None tok/s
```

**Why:** The seed script (`scripts/seed_models.py` per CLAUDE.md) fetches per-provider p50 latency/throughput from `/api/v1/models/{id}/endpoints` and takes min/max. For these three models the endpoints call returned no usable stats, leaving the dataclass fields as `None`. The log f-string interpolates `None` into the middle of a `ms` unit — producing the nonsense token `Nonems`. This also suggests **ModelRegistry stores `None` in DynamoDB**, which will break any downstream sort comparator that assumes numeric (`sort_by: latency_asc`, `throughput_desc`) — Python will raise `TypeError: '<' not supported between instances of 'NoneType' and 'int'` if any of these models enter a sorted tier list. Latent crash waiting for a tier config to reference them.

---

## 7. Seed file references three nonexistent OpenRouter models (LOW, config drift)

**Occurrence:** `pod_logs.txt:129`
```
WARNING: not found on OpenRouter: {'mistral/mistral-small-3.2-24b-instruct',
  'nvidia/nemotron-3-super', 'qwen/qwen3-coder-480b-a35b-instruct'}
```

**Why:** `models/model_ids.txt` contains 33 IDs; OpenRouter only returns 30. These three are either deprecated, renamed, or typos. If any of `presets.yaml` / `tiers.yaml` reference them, the smart router (`models/router.py`) will fall through to the sorted-first fallback and the operator will silently get a different model than they expect.

---

## 8. Duplicate `[ToolCall]` log emissions with empty `args={}` (MEDIUM, logging correctness)

**Occurrences:** 25+ instances, starting `pod_logs.txt:3177-3182`, `6118-6125`, `9082-9089`, `11904-11909`, `14826-14827`, `20720-20725`, `24503-24508`, …

**Symptom:**
```
[ToolCall] name=list_specialists | args={"summary": "List available specialists ..."}
[ToolCall] name=list_specialists | args={}
[ToolCall] name=condense_intent | args={"last_message": "...", ...}
[ToolCall] name=condense_intent | args={}
[ToolCall] name=spawn_specialist | args={"specialist_type": "planner", ...}
[ToolCall] name=spawn_specialist | args={}
```

**Why:** Every tool call is logged twice in the same millisecond — once with the real args, once with `{}`. The second line is almost certainly the OpenHands SDK invoking the executor after an internal `Action.model_dump()` or reserialization step where the payload has already been consumed / drained, or a double-registered log handler firing from both the SDK's own event bus and `agent/session.py`'s manual `[ToolCall]` log at `agent/session.py`. The `args={}` line is a bug — it either comes from a stale/blank Action mirror or from logging the *parent* action after its kwargs have been popped by the dispatcher.

**Blast radius:** Corrupts audit/debug trails; anyone grepping `args=\{\}` for "tools called with no args" will get false positives. Does not affect actual execution.

---

## 9. Specialist `powerlifting_coach` is loaded but is undocumented and returns empty results (MEDIUM)

**Occurrences:**
- Loaded: `pod_logs.txt:1` (startup listing, between `performance_analyst` and `project_manager`, for a total of **51** specialists)
- Empty result: `pod_logs.txt:6087` → `[Subagents] Completed: slug=powerlifting_coach | result_len=0`
- Operator-facing fallout: `pod_logs.txt:6097-6113` → "`[TOOL FAILURE] powerlifting_coach specialist: Empty response returned.`"

**Why (two bugs bundled):**
1. **Drift:** `powerlifting_coach` exists on disk in `specialists/` and is auto-discovered (matching the README's documented behavior), but is **not listed in `README.md` nor `.claude/CLAUDE.md`** — both docs enumerate ~50 specialists without it. Someone added the specialist YAML without updating docs or `delegation.yaml` category mapping.
2. **Silent empty return:** When spawned (09:04:43) it completes after 18s with `result_len=0`. No error surface — the SDK `Conversation.run()` exited cleanly but the agent produced no content. The main agent had to invent the "TOOL FAILURE ... Empty response" message client-side. This means the subagent loop either (a) did not dispatch any tool call and the model generated only reasoning tokens that were stripped, or (b) the result-extraction layer in `agent/tools/subagents.py` is picking the wrong field off the final event. Either way, empty returns from specialists are not being treated as errors — they should fail loudly.

---

## 10. Same silent-empty-return pattern for `health_write` (MEDIUM)

**Occurrence:** `pod_logs.txt:14709` → `[Subagents] Completed: slug=health_write | result_len=0`

**Why:** Different from bug #1 (which returns a 141-char import-error string): here `health_write` completes cleanly with zero bytes. The spawning request was a **read** ("Fetch the operator's current training session ..." — `pod_logs.txt:14695`) routed to a specialist documented in the README as *write-only* ("Training program mutations"). Two overlapping bugs:
- **Routing bug:** The delegation layer (`delegation.yaml` category mapping per CLAUDE.md) is sending read queries to a write specialist. There is no paired `health_read` specialist, so the router has nowhere else to send it, but the symptom is that reads silently return empty.
- **Empty-return-swallowing:** Same as bug #9 — the subagent loop treats `result_len=0` as success rather than as a hard error.

---

## 11. Attachment `example_vulnerable.py` referenced but 404 on terminal volume (MEDIUM)

**Occurrence:** `pod_logs.txt:20729`
```
WARNING | api.completions | Failed to download attachment example_vulnerable.py:
  Terminal API error 404 (/files/read): {"detail":"File not found"}
```

**Why:** The subagent output included `example_vulnerable.py` in its `FILES:` metadata, the `FilesStripBuffer` extracted it, and the dispatcher then asked the OpenTerminal static deployment to serve it. Terminal returned 404. Three plausible root causes, all bugs:
1. The subagent emitted a `FILES:` entry for a path it never actually wrote (hallucination → orphan ref). The extractor does not verify existence before claiming the attachment.
2. The file was written to a per-conversation path (`/home/user/conversations/{chat_id}/`) but looked up via a different relative path in `/files/read`, i.e. path-resolution mismatch between `terminal_write_file` and `TerminalClient.read_file`.
3. Race between the subagent shutdown and the dispatcher's attachment fetch — the container/volume cleanup (in the dynamic client mode) evicted the file before the main pipeline requested it. Less likely here since the pod uses the static terminal deployment, but worth checking file-retention behavior.

Either way, the pipeline still claims `attachments=1` in the response log (`pod_logs.txt:20730`) — we're lying to the user about what we delivered.

---

## 12. Discord gateway: repeated "session has been invalidated" cascades at startup (LOW, cosmetic)

**Occurrences:** `pod_logs.txt:181-190`

**Symptom:** Between 08:57:31 and 08:57:54, three of the five Discord shards connect, immediately get invalidated by Discord, reconnect, get invalidated again, and finally stabilize. No error logged, but each invalidation throws away a `Session ID`.

**Why:** Almost certainly the result of the bot starting **five separate `discord.Client` instances** (one per webhook, per `channels/manager.py` "Started discord listener for wh_*") all logging in with the same token simultaneously. Discord's gateway throttles and invalidates duplicate identifies for the same bot token. Cosmetic at steady state, but it delays readiness by ~20s and could get the token rate-limited on restart storms.

---

## Environmental / non-bug warnings (informational)

These are logged but are not bugs in the project code:

- `pod_logs.txt:61-62, 141-142`: Missing `HF_TOKEN`, missing `PyNaCl`, missing `davey` — optional dependencies; voice unsupported is expected for a non-voice bot.
- `pod_logs.txt:120, 122`: `SKIP deepseek/deepseek-v3.2-speciale: no tool support`, `SKIP perplexity/sonar-pro-search: no tool support` — intentional filter in the seed script.

---

## Summary table

| # | Severity | Location | One-line |
|---|----------|----------|----------|
| 1 | CRITICAL | `subagents.py` import of `terminal_execute` | Breaks every terminal-using specialist |
| 2 | HIGH     | health module init | `UnboundLocalError` on `asyncio` — shadowed import |
| 3 | MEDIUM   | `tool_registry` init order | Deps install called before registry exists |
| 4 | MEDIUM   | `health.rag` | Tika missing → silent PDF-extraction failure |
| 5 | LOW      | `UserFactStore` init log | `-1` sentinel leaks into log message |
| 6 | LOW→latent | `model_registry` seed | `None` rendered as `Nonems`; will crash sort comparators |
| 7 | LOW      | `models/model_ids.txt` | 3 model IDs unknown to OpenRouter |
| 8 | MEDIUM   | `agent/session.py` ToolCall logging | Every tool call logged twice, 2nd with `args={}` |
| 9 | MEDIUM   | `powerlifting_coach` specialist | Undocumented + silent empty returns not treated as errors |
| 10 | MEDIUM  | delegation + `health_write` | Read queries routed to write specialist, empty returns swallowed |
| 11 | MEDIUM  | `FILES:` attachment pipeline | Attachment 404 on terminal; pipeline reports success anyway |
| 12 | LOW     | Discord listener startup | 5 concurrent identifies trigger session invalidations |
