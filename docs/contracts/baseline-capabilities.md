# Historical capability inventory

Captured before implementation. Proposed replacement details in this baseline are not the final architecture; see rewrite.md and executable operation definitions.

# IF runtime conversion inventory

Read-only inventory for replacing OpenCode + Fission + OpenRouter with a pinned Python Codex SDK subscription runtime, while retaining IF behavior. Source context: `CONTEXT.md`, `docs/ARCHITECTURE.md`, `README.md`, and all `app/src` call sites. No ADR files are present under `docs/adr/`.

## Proposed replacement shape

Keep FastAPI, channel adapters, storage, memory, prompts, specialist YAML, tool plugins, reflection, heartbeat, and artifact delivery. Introduce one Python runtime adapter around the pinned Codex SDK and route all model work through it. The adapter should expose:

- `run_planner(...) -> IFPlan` (structured plan, fail closed)
- `run_social(...) -> text`
- `run_specialist(...) -> text/artifacts/handoffs`
- `run_technical(...) -> response/review/retry/artifacts`
- `run_reflection(...)`, `run_heartbeat(...)`, condensation and other background calls
- native Specialist delegation with validated specialist slug, scoped prompt/directives/tools, bounded depth/turns, and child result synthesis

The existing DynamoDB execution registry is the durable priority queue substrate. Its channel state, classification batches, intents, implementation tasks, run records, and Discord outbox should become the authoritative queue/job state; workers claim priority-ready items, resume stale work, persist every transition, and preserve per-channel ordering. Do not replace this with an in-process asyncio queue.

## Request and delivery entry points

| Current path | Current capability/caller | Conversion seam and required preservation |
|---|---|---|
| `app/src/main.py::lifespan`, `app/src/main.py::health_check` | Starts storage, directives, model registry, MCP manager, debounce/coordinator, listeners, heartbeat, reflection, local sandbox; reports health | Start Codex runtime/client and durable workers; remove OpenCode generator/model refresh/MCP startup only where obsolete. Keep all stores, listeners, heartbeat/reflection, readiness/shutdown, health counters, and HTTP client used by channels. |
| `app/src/api/completions.py::chat_completions`, alias, `process_chat_completion_internal` | OpenAI-compatible HTTP; commands, interceptor, cache/pinned specialist bypass, context IDs, history, uploads, flow, reflection, file refs, streaming SSE | Preserve both endpoints and schemas. Internal pipeline becomes enqueue/execute via Codex runtime or direct worker dispatch; retain command/interceptor/cache behavior, context IDs, history writes, attachment handling, and `FILES:` stripping. |
| `app/src/channels/listeners/discord_listener.py` | Discord client, message/edit events, slash command setup, history, attachments | Keep listener lifecycle and event identity; enqueue channel events durably. Codex responses still go through status embeds, chunking, outbox, and Discord handles. |
| `app/src/channels/listeners/openwebui_listener.py` | Polls OpenWebUI, turns messages into debounced channel events | Keep polling/config, message IDs, debounce and delivery translator; use common durable queue. |
| `app/src/channels/dispatcher.py` | Translates Discord/OpenWebUI batches, downloads uploads, calls `process_chat_completion_internal`, chunks/delivers | Preserve translation, upload nudge, webhook lookup, activity tracking, error delivery and channel context. Dispatcher may become a queue submitter plus worker callback. |
| `app/src/channels/delivery.py`, `chunker.py`, `attachments.py`, translators, `status.py` | Platform output, 1500-char chunks, attachments, status embeds | No model-runtime changes should alter platform contracts, chunk limits, attachment materialization, or status types. |
| `app/src/channels/slash_commands.py` | `/reflect`, `/gaps`, `/patterns`, `/opinions`, `/growth`, `/meta`, `/tools`, clear session, task controls and direct prompt execution | Preserve commands and task controls; clear Codex continuation/runtime state at the same command boundary. |
| `app/src/api/webhooks.py` | Register/list/activate/deactivate/restart Discord/OpenWebUI channels | Preserve webhook persistence and listener restart semantics. |
| `app/src/api/files.py` | Serves sandbox/workspace artifacts with traversal checks/content types | Preserve URLs, safe path resolution, and generated-file delivery. |
| `app/src/api/models.py` | `/v1/models` and alias | Preserve API compatibility; expose the pinned Codex model/subscription identity rather than OpenRouter registry choices. |
| `app/src/api/directives.py`, `admin.py`, `health_stats.py`, `template_imports.py` | Directive CRUD/reload; tool reload; health stats; async generated template import | Preserve APIs and authorization/read-only directive semantics. `template_imports.py::run_import_job` currently calls `run_specialist_flow`; route it through Codex specialist execution and keep generated payload discovery. |

## Core flow and direct callers

| Current path | Capability | Replacement/preservation |
|---|---|---|
| `app/src/flow/runner.py::run_if_flow` | Main route execution: planner then social/domain/technical; fail-closed `PlannerFailure` | Replace `_run_planner`, `_run_social`, `_run_domain`, `_run_technical` calls with Codex adapter. Keep `FlowResult`, plan validation, status events, explicit planner failure, workspace/history/artifacts. |
| `app/src/flow/runner.py::execute_route`, `run_specialist_flow` | Reusable route/specialist entry points called by completions, `channels/decision_applier.py`, `channels/task_worker.py`, and template imports | Keep signatures/semantics where possible; these are the central worker-facing seams. |
| `app/src/flow/runner.py::_run_planner` | Builds planner prompt from history, directives, runtime context, specialist catalog/model IDs; writes/parses `plan.md` | Codex structured output replaces file-written OpenCode plan. Keep `IFPlan` fields (`social/domain/technical`, specialist, model, thinking/planning mode), known-specialist/model validation and fail-closed behavior. A compatibility `plan.md` may remain for history/debug if cheap. |
| `app/src/flow/runner.py::_run_social`; `app/src/flow/direct_llm.py::call_openrouter_chat` | Direct chat, optional tool rounds, model selection, status | Replace HTTP OpenRouter call with Codex SDK response/tool loop. Preserve IF personality, core directives, runtime context, tool restrictions, response text and errors. |
| `app/src/flow/runner.py::_run_domain`, `_synthesize_handoffs` | Specialist prompt, filtered directives, scoped local/MCP tools, optional `HANDOFF_REQUIRED` child runs and synthesis | Native Codex Specialist delegation replaces textual `HANDOFF_REQUIRED` parsing where supported. Validate target against `agent/specialists.py`; pass only target tools/directive types/context; bound depth and turns; preserve ordered synthesis and final user text/artifacts. |
| `app/src/flow/runner.py::_run_technical` | Build in persistent conversation workspace, response artifact, review pass, one retry on `RETRY` | Codex technical worker gets the same workspace and terminal/file tools, writes/returns `response.md`; review is a bounded Codex review call; retain `OK`/`RETRY`, one retry, artifact exclusion and cancellation. |
| `app/src/flow/plan.py` | `IFPlan`, `parse_plan_text/file`, `ClassificationResult`, validation and fallback helpers | Keep data model and validation; change parser boundary to Codex structured response while retaining file parser for migration/artifacts. |
| `app/src/flow/context.py`, `history.py`, `session_dirs.py` | Runtime context (signals, LanceDB facts, uploads, memory/media protocols), edit-aware history, stable per-channel workspace | Keep all context and identity scoping. Codex thread/run IDs must be stored alongside existing conversation state; do not collapse Conversations into SDK sessions. |
| `app/src/flow/batch_classifier.py::run_batch_classification` | Discord batch classification into decisions/intent records; currently OpenCode planner model and execution registry | Codex structured classifier call; preserve classification confidence, retries, statuses, batch files/records and fail-closed categories. |
| `app/src/flow/opencode.py`, `opencode_fission.py`, `opencode_config.py` | OpenCode result wrapper, Fission HTTP POST, per-run MCP config/session markers | Legacy replacement boundary. Remove Rust/Fission/OpenCode invocation after Codex adapter is live. Preserve run IDs, timeout/cancel callbacks, status streaming, workspace isolation, scoped tool set, and artifacts in the new adapter. |
| `app/src/flow/model_catalog.py`, `app/src/storage/model_registry.py`, `agent/tiering.py`, `presets/loader.py` | OpenRouter model IDs/metadata, tier/preset selection and legacy support paths | Subscription runtime removes provider pricing/endpoint refresh and model allowlist as execution authority. Keep only compatibility/reporting if API or prompts require it; pin one configured Codex model/version and keep context-size/tiering only if still needed for condensation. |
| `app/src/flow/runtime_tool.py`, `app/src/mcp_runtime/*`, `app/src/mcp_servers/config.py`, `tools/mcp_server.py`, `tools/_plugin_runner.py` | Narrow memory CLI; MCP manager; local/external MCP discovery and tool invocation | Keep tool business logic. Replace OpenCode MCP exposure with Codex SDK native tools/function definitions or a small adapter that invokes the existing plugin executors. Preserve specialist allowlists and Decimal conversion. Remove only unused MCP server process/config machinery. |

## Specialists and tools

`app/src/agent/specialists.py` discovers `specialists/*/specialist.yaml`, renders each `agent.j2`, maps commands, and exposes descriptions, `tools`, `mcp_servers`, `directive_types`, `context_builder`, `skills`, `preset`, and `agentic` metadata. All 54 configured specialists must remain discoverable and routable:

`api_designer`, `architect`, `career_advisor`, `changelog_writer`, `code_explorer`, `code_reviewer`, `coder`, `consensus_builder`, `constrained_writer`, `cover_letter`, `data_analyst`, `debugger`, `decision_analyst`, `devops`, `dialectic`, `doc_generator`, `email_writer`, `file_generator`, `finance_write`, `financial_analyst`, `git_ops`, `health_write`, `incident_responder`, `interviewer`, `jira_writer`, `language_tutor`, `legal_reader`, `math_tutor`, `media_reader`, `meeting_prep`, `migration_planner`, `ml_tutor`, `negotiation_advisor`, `pdf_generator`, `performance_analyst`, `planner`, `powerlifting_coach`, `product_manager`, `product_owner`, `prompt_engineer`, `proofreader`, `refactorer`, `research_assistant`, `resume`, `scripter`, `secops`, `self_improver`, `sql_analyst`, `summarizer`, `tarot_reader`, `test_writer`, `todo_generator`, `workday`.

Tool categories under `tools/` are `diary`, `finance`, `proposals`, `supplement_research`, `tarot`, and `temporal_age`, `temporal_city_time`, `temporal_duration`, `temporal_from_unix`, `temporal_resolve`, `temporal_timezone`, `temporal_to_unix`; health and health-lambda integrations are also referenced by specialist/MCP configuration. Preserve exact tool names, local/subprocess execution, scoped visibility, read/write restrictions, and existing portal/DynamoDB effects. `specialists/mcp_servers.yaml` contains external server declarations that need an SDK-compatible tool bridge or deliberate per-specialist replacement.

## Durable queue, task, and cancellation path

| Current path | Capability | Conversion requirement |
|---|---|---|
| `app/src/channels/channel_coordinator.py` | Discord event state machine, 45s debounce/300s max wait, durable classifier lock, batch derivation/reconciliation | Keep state transitions and per-channel ordering; enqueue classification at priority; workers must survive process restart and stale locks. |
| `app/src/channels/execution_models.py` | `ChannelClassificationState`, `ClassificationBatch`, `ClassifierDecision`, `IntentRecord`, `ImplementationTask`, `OpenCodeRunRecord`, `DiscordOutboundMessage`; float→Decimal helper and instance identity | Keep records/status vocabulary; rename OpenCode fields only via compatibility migration. Add Codex thread/run IDs, priority, attempt, lease, idempotency key, parent/child specialist IDs. |
| `app/src/channels/execution_store.py` | DynamoDB registry operations, conditional transitions, locks, intent/task/run/outbox persistence, stale recovery | This is the durable priority queue foundation. Add priority-aware claim/query and leases with conditional writes; preserve TTLs, idempotency, conditional transitions, and Decimal conversion. |
| `app/src/channels/decision_applier.py` | Applies social response, clarify, ignore, start task, append/queue, await, cancel, pivot decisions | Keep decision semantics. Route starts/mutations through queue records and Codex cancellation/delegation controls. |
| `app/src/channels/task_worker.py` | Implements queued technical/domain tasks, run records, cancel polling, status, outbound enqueue | Replace OpenCode subprocess/session marker handling with Codex run IDs and SDK cancellation; keep task lifecycle, pivot/cancel, bounded retries, and outbound enqueue. |
| `app/src/channels/cancellable_executor.py` | In-process process registry, terminate/kill and cancel events | Replace process kill with Codex run cancellation plus lease/worker cancellation; retain local event for cooperative tool work. |
| `app/src/channels/outbound_queue.py` | DynamoDB outbox lock, ordered drain, retry/failure status, Discord delivery | Keep durable outbox, per-channel lock/order and delivery recovery. |

Priority policy is currently implicit in decision/task state; make it explicit at queue claim time: operator-visible interactive messages first, active-task instructions/cancel/pivot next, heartbeat/reflection/background work lowest, with FIFO within a priority/channel and no starvation. Preserve channel ordering even when multiple Codex specialist children run.

## Durable state and behavior to preserve

- `app/src/storage/directive_model.py` and `directive_store.py`: versioned, priority-tiered directives, global/core directives, filtered `get_for_subagent`, proposals/revisions/deactivation/reorder. Planner and Specialist prompts must continue receiving the correct filtered directives.
- `app/src/memory/user_facts.py`, `lancedb_store.py`, `embeddings.py`, `summarizer.py`, `store.py`, `migrate_chroma.py`: Operator/IF facts, sources/confidence, supersession, capability gaps, opinions, misconceptions, reflection records, semantic retrieval, legacy Chroma compatibility. Keep Conversation-scoped facts and Decimal-safe downstream writes.
- `app/src/agent/reflection/engine.py`, `pattern_detector.py`, `opinion_formation.py`, `growth_tracker.py`, `meta_analysis.py`, `agent/commands.py`: periodic/post-session/on-demand Reflection, gap proposals, opinions, growth and meta reports. Background calls use the same queue/runtime with low priority; proposals still require human approval.
- `app/src/heartbeat/activity.py`, `heartbeat/runner.py`: idle detection, quiet hours, cooldown, fact-based proactive opening, delivery through Discord/OpenWebUI. Heartbeat remains a Conversation-starting Channel action and must be queueable/cancellable.
- `app/src/routing/cache.py`, `routing/interceptor.py`, `routing/commands.py`: cache/pinning, command actions, special routing/intercepts. Preserve before planner execution.
- `app/src/agent/condenser.py`, `tiering.py`: context token estimate/condensation and tier behavior. Route condensation through Codex; keep thresholds and stored summary format unless proven unnecessary.
- `app/src/app_sandbox/local.py`, `terminal/files.py`: local workspace and terminal/file artifact capabilities. Technical Specialists need equivalent scoped access and safety boundaries.

## Legacy references to remove or quarantine

- Runtime/config: `app/src/config.py` (`OPENROUTER_*`, `OPENCODE_*`, `OPENCODE_FISSION_URL`, preset/model fallbacks), `app/.env.example`, `app/requirements.txt` (add pinned Codex SDK; remove only dependencies proven runtime-unused), and model/provider startup in `app/src/main.py`.
- OpenCode files/prompts: `app/src/flow/opencode.py`, `opencode_fission.py`, `opencode_config.py`; OpenCode wording and file contracts in `app/src/agent/prompts/*`, `main_system_prompt.txt`, specialist `agent.j2`, `README.md`, `docs/ARCHITECTURE.md`, and `.claude/CLAUDE.md`.
- Fission/Rust: `utils/opencode-runner/` and `terraform/k8s-fission.tf`, `terraform/k8s-fission-powerlifting.tf`, related image/build/deployment references. Remove only after live replacement is verified; do not delete infrastructure in this inventory phase.
- Scripts: `scripts/generate_opencode_agents.py`, `scripts/clean-fission-workloads.sh`, `scripts/reset-fission-packages.sh`, and OpenCode/model seeding/debug scripts. Classify migration utilities before removal.
- Provider-specific consumers: `flow/direct_llm.py`, `agent/condenser.py`, `memory/summarizer.py`, `heartbeat/runner.py`, reflection opinion/engine model normalization, `storage/model_registry.py`, and specialist research prompts mentioning OpenRouter/`:online`.

## Important constraints

1. IF is a single-Operator entity with persistent IF identity/opinions/principles; never replace it with a stateless SDK assistant.
2. Conversation identity is channel/workspace based and durable. SDK threads/runs are implementation details, not the domain Conversation key.
3. Specialist context must be scoped by declared tools and `directive_types`; native delegation must validate targets and bound recursion.
4. Planner failure remains explicit/fail-closed; no guessed social fallback.
5. Technical work retains persistent workspaces, generated files, review/retry, cancellation, and status visibility.
6. Discord/OpenWebUI/HTTP contracts, SSE, chunking, attachments, slash commands, heartbeat and reflection remain supported.
7. DynamoDB is never written with Python `float`; use existing conversion helpers.
8. Live k3s is the source of truth for runtime diagnosis; do not apply/destroy Terraform, mutate the IF API, delete AWS resources, or write git history during conversion.
9. Pin the SDK version and model/runtime compatibility explicitly. Subscription authentication/limits and concurrency must be observed at the worker boundary, with backpressure in the durable queue.

# Powerlifting rewrite inventory

Read-only inventory of `utils/powerlifting-app` at 2026-09-13. This is the
separate NoLift repository. Its vocabulary is defined by `CONTEXT.md`; the
architecture and existing guarantees are in `docs/ARCHITECTURE.md`,
`docs/FORMULAS.md`, and ADRs 0001 (every capability is a Fission nano-function)
and 0002 (Authentik identity provider).

## Constraints and invariant behavior

- Preserve existing DynamoDB data and keys. The stores are `if-health`
  (program, glossary, max/weight data, cached report references), `if-sessions`,
  `if-user`, `if-powerlifting-analysis-cache`, `if-powerlifting-user-competitions`,
  `if-powerlifting-master-competitions`, `if-powerlifting-master-federations`,
  `if-powerlifting-goals`, and `if-powerlifting-budget`; S3 buckets are
  `powerlifting-session-videos` and `powerlifting-budget-media`.
- Authenticated requests resolve `mapped_pk || pk`; anonymous requests resolve
  to `operator` and are read-only. Grants are enforced by backend middleware and
  handlers. Authentik is the identity provider; Discord OAuth remains supported.
- Dates are `YYYY-MM-DD`, timestamps ISO8601, and weights are stored as kg.
  Convert Python floats to `Decimal` before every DynamoDB write.
- Program versions, stable Session identity (`date` plus index), and planned vs
  executed exercise data are compatibility requirements. Analysis windows and
  caches are part of the observable API.
- Current transport is Express `/api/*` -> `invokeLambda` (Fission HTTP) or
  `invokeToolDirect` (IF `/v1/chat/completions` with direct-tool header). The
  frontend is `frontend/src/api/*` and pages/components. The rewrite should
  expose one typed operation definition to HTTP and MCP.
- No AWS deletion, deployment, or Git write was performed for this inventory.

## Sixteen replacement services

Each row names the replacement operation prefix. Inputs include `pk`/actor
context where applicable; results preserve current JSON/domain types; errors
are typed (`unauthenticated`, `forbidden`, `not_found`, `validation`,
`conflict`, `dependency_unavailable`, `internal`) rather than raw Fission
responses. The operation registry must provide the same input/result/error
schema to HTTP and MCP.

### 1. Program — `program.*`

- Source: `backend/src/controllers/programController.ts`,
  `setupController.ts`, `blockNotesController.ts`, `dietNotesController.ts`,
  `supplementController.ts`; routes `backend/src/routes/programs.ts`,
  `setup.ts`, `blockNotes.ts`, `dietNotes.ts`, `supplements.ts`.
- Existing functions: `getProgram`, `listPrograms`, `updateMetaField`,
  `updateBodyWeight`, `updatePhases`, `updateLiftProfiles`, `batchCreateWeek`,
  `updatePlannedExercises`, `archiveProgram`, `unarchiveProgram`,
  `getBlockNotes`, `updateBlockNotes`, `getDietNotes`, `updateDietNotes`,
  `getSupplementPhases`, `updateSupplementPhases`, setup status/initialize.
- Existing calls: `program_get`, `program_list_full`,
  `program_update_meta_field`, `program_update_phases`,
  `program_update_lift_profiles`, `program_archive`, `program_unarchive`,
  `health_setup_status`, `health_setup_initialize`, `block_notes_get`,
  `block_notes_update`, `health_get_diet_notes`, `health_update_diet_note`,
  `health_delete_diet_note`, `health_get_supplements`,
  `health_update_supplements`, plus `pod_sessions.session_*` for program merge.
- Replacement operations: `program.get/list`, `program.update_meta`,
  `program.update_body_weight`, `program.update_phases`,
  `program.update_lift_profiles`, `program.batch_create_week`,
  `program.update_planned_exercises`, `program.archive/unarchive`,
  `program.setup_status/initialize`, `program.block_notes_get/update`,
  `program.diet_notes_get/update/delete`, `program.supplements_get/update`.
- Storage: `if-health` program version/meta/phase/block-note/diet/supplement
  items, with sessions merged from `if-sessions`; templates use
  `if-health-templates` and must retain lineage.

### 2. Sessions — `session.*`

- Source/controller `backend/src/controllers/sessionController.ts`; route
  `backend/src/routes/sessions.ts`; shared persistence
  `backend/src/services/sessionStore.ts`.
- Functions: create, delete, get, update/replace, reschedule, complete,
  status update, add/remove exercise, update exercise field; AI note drafting
  and auto-regulation are direct IF tools from the same route.
- Existing calls: `session_create`, `session_delete`, `session_get`,
  `session_replace`, `session_patch`; range/list variants exist in
  `lambda/pod_sessions/handlers` (`health_get_sessions_range`, `session_list`,
  `session_list_full`, `session_replace_all`).
- Replacement: `session.create/delete/get/list/update/replace`,
  `session.reschedule`, `session.set_status`, `session.complete`,
  `session.add_exercise/remove_exercise/update_exercise`,
  `session.draft_notes`, `session.autoregulate`.
- Storage: `if-sessions`; updates invalidate merged program caches and analysis.
  Preserve session identity, per-set status/reasons, and planned/logged split.

### 3. Competition — `competition.*`

- Source/controller `backend/src/controllers/competitionController.ts`; route
  `backend/src/routes/competitions.ts`; frontend calls in
  `frontend/src/api/client.ts` and competition pages/stores.
- Functions: user competition list/patch/complete; legacy versioned list/update/
  complete; projection snapshot and attempt calculation.
- Existing calls: `health_list_competitions`, `health_get_competition`,
  `health_create_competition`, `health_update_competition`,
  `health_delete_competition`, `health_complete_competition`,
  `health_snapshot_competition_projection`, `calculate_attempts`.
- Replacement: `competition.user_list/get/update/delete/complete`,
  `competition.list/update/complete`, `competition.calculate_attempts`,
  `competition.snapshot_projection`.
- Storage: user records in `if-powerlifting-user-competitions`; directory links
  and legacy records may also be in `if-health`. Preserve independent Event,
  Entry, results, attempts, target/projection, and post-meet lifecycle.

### 4. Federation — `federation.*`

- Source/controller `backend/src/controllers/federationsController.ts`; route
  `backend/src/routes/federations.ts`; frontend federation store/page.
- Existing calls: `federation_master_list`, `federation_master_update`,
  `federation_user_library_get/set`, and legacy `health_get_federation_library`,
  `health_update_federation_library`.
- Replacement: `federation.master_list/update`, `federation.library_get/set`.
- Storage: master directory `if-powerlifting-master-federations`; user library
  currently `if-health` (`federations#v1`) and/or configured user federation
  table. Admin-only master writes remain authorized.

### 5. Glossary — `glossary.*`

- Source/controller `backend/src/controllers/exerciseController.ts`; route
  `backend/src/routes/exercises.ts`; frontend glossary pages/components.
- Existing calls: `exercise_get_glossary`, `exercise_search`, `exercise_upsert`,
  `exercise_remove`, `exercise_archive/unarchive`, `exercise_set_e1rm`; direct
  IF tools `glossary_estimate_e1rm/fatigue/muscles`.
- Replacement: `glossary.list/get/search/upsert/delete/archive/unarchive`,
  `glossary.set_e1rm`, `glossary.estimate_e1rm/fatigue/muscles`,
  `glossary.generate_text`.
- Storage: `if-health` glossary item(s), schema in `backend/src/db/schema_glossary.json`.
  Preserve e1RM method/value and fatigue/muscle metadata.

### 6. Goals — `goals.*`

- Source/controller `backend/src/controllers/goalsController.ts`; route
  `backend/src/routes/goals.ts`; `frontend/src/store/goalsStore.ts` and GoalsPage.
- Existing calls: `goals_list`, `goals_replace` (health aliases also exist).
- Replacement: `goals.list`, `goals.replace`.
- Storage: dedicated `if-powerlifting-goals`; replace is a validated atomic
  collection update and invalidates program/analytics caches.

### 7. Budget — `budget.*`

- Source/controller `backend/src/controllers/budgetController.ts`; route
  `backend/src/routes/budget.ts`; frontend `src/store/budgetStore.ts` and
  `src/components/budget/*`.
- Functions/calls: config get/put, item list/create/update/delete, summary,
  priority timeline, AI advisor; photo upload/delete is controller S3 work.
  Existing Fission names are `budget_get_config`, `budget_put_config`,
  `budget_list_items`, `budget_create_item`, `budget_update_item`,
  `budget_delete_item`, `budget_get_summary`, `budget_priority_timeline`,
  `budget_advisor`.
- Replacement: `budget.config_get/put`, `budget.item_list/create/update/delete`,
  `budget.mark_cut`, `budget.summary`, `budget.priority_timeline`,
  `budget.ai_advisor`, `budget.photo_upload/delete`.
- Storage: `if-powerlifting-budget`; media S3 `powerlifting-budget-media`.
  Preserve mandatory/important/optional priority and cut-without-delete behavior.

### 8. Calculations — `calculation.*`

- Source: `lambda/pod_calc/handlers/*`; callers are frontend `client.ts`,
  tool callers, and analytics/competition logic.
- Functions: `calculate_dots`, `estimate_1rm`, `days_until`, `ipf_weight_classes`,
  `kg_to_lb`, `lb_to_kg`, `pct_of_max`.
- Replacement: `calculation.dots`, `calculation.estimate_1rm`,
  `calculation.days_until`, `calculation.ipf_weight_classes`,
  `calculation.kg_to_lb/lb_to_kg`, `calculation.percent_of_max`.
- Storage: none. One deterministic implementation must serve HTTP, MCP,
  analytics and frontend-facing results; preserve formula/version semantics from
  `docs/FORMULAS.md`.

### 9. Performance — `performance.*`

- Source/controller `backend/src/controllers/maxController.ts`; route
  `backend/src/routes/maxes.ts`; maxes frontend page.
- Existing calls: `max_history_get/add`, `max_target_get/update`,
  `health_get_current_maxes`, `health_update_current_maxes`.
- Replacement: `performance.max_history_get/add`, `performance.target_get/update`,
  `performance.current_maxes_get/update`.
- Storage: `if-health` max history and current/target max fields. Preserve range
  windows and invariant that identical method/date range yields identical Max.

### 10. Weight Log — `weight.*`

- Source/controller `backend/src/controllers/weightController.ts`; route
  `backend/src/routes/weight.ts`; frontend WeightTracker and client.
- Existing calls: `weight_log_get/add/remove` plus legacy `weight_get_log`,
  `weight_add_entry`, `weight_remove_entry`.
- Replacement: `weight.list`, `weight.add`, `weight.remove`.
- Storage: weight log in `if-health` under the program partition; kg-only writes,
  date uniqueness and cache invalidation are observable.

### 11. Templates — `template.*`

- Source/controller `backend/src/controllers/templateController.ts`; route
  `backend/src/routes/template.ts`; frontend `src/components/templates/*` and
  client.
- Existing calls: `template_list/get/create_from_block/create_blank/update/copy`,
  `archive/unarchive`, `publish/unpublish`, `evaluate`, `apply`,
  `apply_confirm`; import upload/status.
- Replacement: matching `template.list/get/create_from_block/create_blank/update`,
  `template.copy/archive/unarchive/publish/unpublish/evaluate/apply/confirm_apply`,
  `template.import_upload/status`.
- Storage: configured templates table (`if-health-templates`); applying creates
  a Program and records lineage. AI evaluation is an IF queued operation.

### 12. Imports — `import.*`

- Source/controller `backend/src/controllers/importController.ts`; route
  `backend/src/routes/import.ts`; frontend `src/components/import/*`.
- Existing calls/direct tool: `import_parse_file`, `import_list_pending`,
  `import_get_pending`, `import_apply`, `import_reject`.
- Replacement: `import.parse_file`, `import.list_pending`, `import.get_pending`,
  `import.apply`, `import.reject`.
- Storage: pending import records in `IF_HEALTH_TABLE_NAME` (default `if-health`), matching the original `pod_import/handlers/import_get_pending/core.py`; generic proposal configuration does not select the import table.
  then writes target Program/Glossary/Sessions only on explicit apply. Parsing
  can be asynchronous; never silently apply or replay uncertain mutations.

### 13. Profile — `profile.*`

- Source/controllers `profilesController.ts`, `settingsController.ts`,
  `onboardingController.ts`, `authController.ts`; routes `profiles.ts`,
  `settings.ts`, `onboarding.ts`, `auth.ts`; frontend API settings/profiles/
  onboarding and corresponding pages.
- Existing calls: `profile_search/get_current/get`, settings get and all
  nickname/profile/ranking/age/avatar/tag operations, onboarding role/profile/
  athlete basics, and grant operations.
- Replacement: `profile.search/get_current/get`, `profile.settings_get`,
  `profile.update_nickname/profile/ranking_location/age_class/avatar`,
  `profile.tag_add/remove/approve/propose`, `profile.onboarding_status`,
  `profile.onboarding_set_role/profile/athlete_basics`.
- Storage: identity/profile in `if-user`; avatar objects in configured profile
  media storage. Auth/session middleware and Authentik/Discord flows remain.

### 14. Lift Profiles — `lift_profile.*`

- Source: `programController.updateLiftProfiles`, `exerciseController` estimate
  methods, analytics route; AI lambdas in `lambda/pod_lift_profile_ai/handlers/*`.
- Existing calls: `program_update_lift_profiles`,
  `lift_profile_review/rewrite/estimate_stimulus/rewrite_and_estimate`,
  `fatigue_profile_estimate`, `muscle_group_estimate`, glossary e1rm estimate.
- Replacement: `lift_profile.update`, `lift_profile.review/rewrite`,
  `lift_profile.estimate_stimulus`, `lift_profile.rewrite_and_estimate`,
  `lift_profile.estimate_fatigue/muscles`, `lift_profile.estimate_accessory_e1rm`.
- Storage: profiles inside the versioned Program in `if-health`; AI outputs are
  proposals until accepted. Preserve stimulus coefficient/confidence/reasoning
  and deterministic INOL use.

### 15. Analytics — `analytics.*`

- Source/services `backend/src/services/analysisCache.ts`, `blockAnalytics.ts`,
  `blockAnalysisExport.ts`; analytics route; frontend `src/api/analytics.ts`,
  `src/components/analysis/*`.
- Existing functions: manifest, queue/fetch/invalidate sections, weekly bundle,
  regenerate, markdown, weekly analysis, block list/analysis/regenerate,
  block evaluation/correlation/export, comparisons, correlation, program
  evaluation, fatigue/muscle AI, glossary text, lift-profile AI, budget timeline,
  and stats (`powerlifting_filter_categories`, `analyze_powerlifting_stats`,
  `powerlifting_ranking_percentile`). Lambda names are in `pod_analysis` plus
  `get_analysis_markdown` and `pod_budget.budget_priority_timeline`.
- Replacement: `analytics.manifest`, `analytics.sections_queue/get/invalidate`,
  `analytics.weekly/bundle`, `analytics.regenerate`, `analytics.markdown`,
  `analytics.blocks/list/get/regenerate`, `analytics.block_evaluation`,
  `analytics.correlation`, `analytics.compare`, `analytics.export`,
  `analytics.program_evaluation`, and `analytics.stats_*`.
- Storage: deterministic and AI cache material in `if-powerlifting-analysis-cache`
  (7-day windows; budget AI 48h); source reads `if-health`, `if-sessions`,
  glossary and weight log. Preserve section keys/windows, cache-only AI reads,
  explicit refresh, block-note fingerprint, exports and frontend-derived trend
  behavior documented in ARCHITECTURE.

### 16. Videos — `video.*`

- Source/controller `backend/src/controllers/videoController.ts`; routes
  `backend/src/routes/videos.ts`; standalone lambdas `video_upload`,
  `video_remove`, `video_library_get`, `video_update_metadata`,
  `video_update_thumbnail`, and S3 trigger `video-thumbnail/index.py`.
  Frontend callers are VideosPage, VideoGrid, VideoPlayerModal and session
  video components.
- Replacement: `video.library`, `video.upload`, `video.remove`,
  `video.update_metadata`, `video.update_thumbnail`.
- Storage: video/thumbnail objects in `powerlifting-session-videos`; attachment
  metadata on Session in `if-sessions` (source lookup may read `if-health`).
  Preserve upload MIME/size validation, thumbnail status and asynchronous
  thumbnail generation.

## Cross-cutting callers and known defects to repair

- HTTP registration is centralized in `backend/src/server.ts` (`/api/auth`,
  settings, profiles, setup, grants, onboarding, programs, goals, federations,
  budget, sessions, exercises, maxes, weight, supplements, diet-notes,
  block-notes, competitions, videos, analytics, export, import, templates,
  stats). These are the complete backend consumer surfaces.
- Frontend transport is `frontend/src/api/client.ts`, `api/analytics.ts`,
  `api/settings.ts`, `api/profiles.ts`, `api/onboarding.ts`, `api/grants.ts`;
  cache behavior is `frontend/src/api/cache.ts`. Pages/stores/components under
  `frontend/src/pages`, `store`, and `components` call these modules.
- `backend/src/utils/lambda.ts` and `lambdaCache.ts` are the Fission forwarding
  seam; `backend/src/utils/agent.ts` is the IF direct-tool seam. Both must be
  replaced behind the same typed operation registry so callers do not fork
  schemas.
- Duplicates: legacy `health_*` and newer `pod_*` handlers coexist for Program,
  Sessions, Competition, Federation, Goals, Weight, Maxes and Supplements;
  `session_*` and `health_*` also duplicate CRUD. Consolidate aliases onto one
  implementation while retaining compatibility routes during migration.
- Broken/fragile behavior requiring explicit parity tests: competition controller
  mixes legacy versioned records and user competition records; frontend-derived
  top max intentionally differs from backend current max; AI reports are
  cache-only unless refresh is explicit; program-evaluation invalidation uses
  block-note fingerprint but not session changes; import parsing is direct-tool
  while other import operations are Fission; video metadata spans S3 plus two
  DynamoDB stores; and float-to-Decimal conversion must cover every Python
  write, including new paths.

## Lifecycle contract reminder

Every mutating operation returns a typed result or a typed error. AI/analytics,
template evaluation, import parsing and video thumbnail work may return a durable
job `{job_id,status}` with `queued|running|succeeded|failed|cancelled|unknown`;
clients need submit/status/result/cancel and artifact references. Cancellation
must be cooperative. If a worker disappears after a mutation may have happened,
report `unknown` and require reconciliation; do not automatically replay. Domain
AI calls enter IF's execution queue and active jobs must use deterministic tools
or native delegation without enqueuing a second AI job behind themselves.

## Verification status

This document is a static inventory only. No Fission call, AWS read/write,
deployment, HTTP canary, frontend build, or cross-node test was run here.


## Verified integration amendments

- Program batch-week creation and planned-exercise updates remain compositions of scoped Sessions operations; body-weight update composes the existing two metadata fields. Their backend caller mappings are `programController.batchCreateWeek/updatePlannedExercises/updateBodyWeight`; they do not introduce duplicate storage implementations.
- Global mutable Store singletons were removed from domain handlers because concurrent requests could retarget another Athlete's partition. DynamoDB analysis/report caches remain the authoritative persisted caches. Stores are scoped per invocation.
- Domain AI uses a running service continuation: an active IF job receives `needs_inference`, delegates its supplied report prompt/schema to a native Specialist, and answers via `domain_resume`. No nested top-level job is submitted. Lost continuations return `uncertain`; they cannot be replayed automatically.
- Local subscription canary passed (Sol, single-stream completion, durable claim/result). Local HTTP/MCP calculation parity/authentication checks passed. These do not establish cluster or laptop acceptance.


Parity clarifications from implementation review: Athlete Goals (`goals_list`/`goals_replace`) remain distinct from versioned Program Goals (`health_get_goals`/`health_update_goals`); they preserve their existing tables and vocabulary. The Goals screen saves Athlete Goals once. `program_update_lift_profiles` is owned by Lift Profiles while retaining its name and ProgramStore binding. Four glossary estimation/text operations are owned by Glossary while retaining their existing AI handler modules.
