# IF and Powerlifting rewrite contract

The execution sections below describe the preceding deployed version. The [native conversation contract](native-conversations.md) defines the new implementation awaiting protected rollout.

Status: implementation contract, 2026-09-13. This supersedes Powerlifting ADR-0001's execution substrate, not its requirement for HTTP/MCP parity. Root docs/adr is empty in this checkout; ADR-0002 referenced by root AGENTS.md is unavailable.

## Ownership and persistence

IF owns Conversations, scoped Facts, identity, Directives, Reflection, Heartbeat, channel listeners, execution registry and outbox on the main node. The worker owns only temporary execution workspaces and persistent subscription login. Existing DynamoDB keys, tables, Program versions and Session identities remain unchanged. Existing data and historical versions are retained; obsolete execution wording in four Directives is revised atomically as new versions.

Powerlifting owns Athlete data. Its authenticated browser gateway derives Person/Athlete scope and checks existing grants. Internal services require X-Internal-Token and an explicit Athlete scope for private operations; body ownership must agree with that trusted scope. Public directory/profile operations retain their existing visibility checks. Never trust a browser-supplied ownership header or accept an empty internal token. IF memory/artifact operations bind scope to the authenticated job, never to model-supplied paths.

## Executable definitions

`app/src/execution/schemas.py` defines IF submission, job, error and artifact JSON schemas. `utils/powerlifting-app/services/contract.py` defines typed Operation records; `services/operations/*.json` holds the single operation inventory, input/result JSON schemas and handler bindings consumed by both HTTP and MCP. Contract checks validate all schemas and handler coverage. Existing domain result bodies are preserved; transport adds a uniform error and asynchronous job envelope.

`app/src/flow/classification_schema.py` defines Discord batch output. Every object declares its fields, requires them and forbids additional properties; optional values are nullable. The schema preserves social replies, new tasks, implementation controls, clarification, ignore, planning details, topic updates and conflicts. `app/tests/test_channels_rewrite.py` checks the schema passed by the actual classifier; `scripts/test_if_classifier_live.py` verifies greeting/task classification through the subscription worker without Discord delivery.

## IF execution

POST /v1/jobs accepts a scoped request and idempotency key; GET /v1/jobs/{id} returns status; GET /v1/jobs/{id}/result returns completion or 202 while pending; POST /v1/jobs/{id}/cancel requests cancellation. Artifact IDs are scoped to job ownership. GET /v1/jobs/{id}/events streams durable events with a resumable cursor. Existing /v1/chat/completions non-streaming and OpenAI SSE responses remain available as consumers of the same queue.

Lifecycle: queued -> running -> succeeded | failed | cancel_requested -> cancelled | uncertain. A queued cancellation is immediately cancelled. Expired worker leases become uncertain, never automatically replayed. An interrupted mutation is uncertain unless completion is confirmed. Claiming is atomic and globally permits one running top-level job; user priority precedes background priority, FIFO within priority. Duplicate idempotency keys with different requests conflict. Authentication failures and subscription limits are explicit terminal errors; no paid API fallback.

Sol coordinates using the available model list, original persona and core Directives. Native Specialists receive their own prompt/context, applicable Directives and permitted tools. Maximum two native children; no recursive queue submission from an active job. Thinking workflows use native delegation with bounded children. User requests, summarization, Reflection and Heartbeat share execution; background work cannot occupy additional top-level slots. Status, reception and cancellation do not require inference.

The main node retains durable request/results/events, conversation storage, memory, execution records and delivery outbox. Workers use scoped HTTP tools and artifacts, not a cross-node shared filesystem. Completion is persisted before delivery; delivery is idempotent through the existing outbox. Worker loss is reported without guessing whether side effects occurred.

## Powerlifting services

Exactly sixteen independently configured Services and Deployments: program, sessions, competition, federation, glossary, goals, budget, calculations, performance, weight-log, templates, imports, profile, lift-profiles, analytics, videos. Each exposes GET /health, GET /openapi.json, POST /operations/{name}, and MCP at /mcp. Operation input and result schemas are identical across HTTP and MCP. Unknown operation: 404; invalid input: 422; missing/bad authentication: 401; scope violation: 403; version/idempotency conflict: 409; unavailable subscription: explicit job error; unexpected execution failure: 500 without credentials.

Domain AI requests submit to IF and return a job reference. During an active job, native delegation performs AI work using deterministic domain tools; it must never enqueue another top-level AI job and synchronously wait for itself. Preserve structured reports, cache keys/invalidation, historical windows, exports, Program lineage/versioning, stable Session IDs, planned versus executed exercises, and shared calculation methods. Convert every Python float recursively to Decimal before DynamoDB writes.

## Channels and consumers

Discord reception, task controls and outbox delivery remain main-node responsibilities. HTTP/OpenWebUI keep completion and streaming semantics; asynchronous consumers use the job APIs. Backend forwarding resolves operation names to the sixteen services; frontend stays behind its authenticated /api gateway and renders pending/cancelled/failed/uncertain states. Never expose internal service credentials to browser code.

## Acceptance and deployment

Offline parity/auth/storage/calculation/queue/cancellation/recovery tests, both frontend and backend typechecks, and npm run build are mandatory. Controlled sequential canaries: general IF conversation, a scoped deterministic operation, representative Powerlifting report. Resource measurement precedes a bounded main-node test worker; no stress or production-data mutation tests. Main-node and laptop acceptance are separate. The laptop handoff is /tmp/if-laptop-handoff.md. The local k3s service is running and the supplied AWS credentials are verified. Main-node results are recorded in acceptance.md. The operator approved the reviewed targeted API deployment; later protected changes still require a concrete scope review. Existing Authentik/Postgres edits and Terraform scopes are preserved.

## Capability inventory

The pre-conversion capability inventory is in [baseline-capabilities.md](baseline-capabilities.md). Its proposed implementation details are historical; the executable contracts and decisions below describe the implemented replacement. Legacy execution files are removed only after their replacements pass verification.

Exact Python function/caller index: `function-inventory.json` (baseline, before conversion); `function-replacements.json` maps all 3,951 baseline functions to current targets. `operation-callers.json` maps canonical domain operations and literal backend callers. Regenerate and validate them with `python3 scripts/map_rewrite_functions.py` and `node scripts/check_rewrite_contract.cjs`. Stable existing operation names remain canonical to avoid needless caller renaming; prefixes below describe ownership, not mandatory wire renames.

## Final implementation decisions

- Main-node `execution/store.py` uses SQLite WAL with atomic claims in the existing persistent data volume. Existing DynamoDB channel classification, task, run and outbox records remain in place. SQLite is the execution queue; the channel registry is not a second execution queue.
- `flow/runner.py` submits to Sol directly. Sol selects workflows and native Specialists within a single job; the old file-written planner, OpenCode subprocess and handoff-file loops are removed. Existing IFPlan fields remain compatibility metadata for channel consumers.
- Each execution has a fresh worker workspace. Inputs and outputs move through authenticated artifact IDs. Conversation history and memory stay on the main node and are provided as context or scoped tools. Worker workspaces are not persistent conversation storage.
- `agent/codex_specialists.py` preserves the 54 Specialist prompts and scoped Directives. The pinned SDK applies custom role instructions/models but does not apply per-role MCP configuration. `execution/tool_policy.py` enforces Specialist tools at the native pre-tool boundary; server-side scope checks remain authoritative for domain access. This boundary requires a passing native delegation canary before deployment.
- Powerlifting operation names remain stable. `services/operations/*.json` supplies HTTP and MCP schemas, execution kind, ownership and deterministic handler for all sixteen domains. Python storage constructors inherit authenticated Athlete context within dispatch, including nested export/report helpers.
- Public calculation outputs retain their original rounding. Internal analysis uses unrounded estimates from shared Python/TypeScript calculation helpers and a single constants file.
- Imports stage proposals for explicit review and apply. Apply claims a proposal conditionally before writes; failures after a claim become uncertain and are not replayed. Browser video upload uses service-issued presigned S3 PUT followed by authenticated confirmation.
- New manifests and images are prepared separately from the existing Terraform deployment. The approved targeted API deployment and exact Fission compute retirement follow controlled live checks. Retained AWS resources, PVCs, namespaces and historical records are excluded from removal.

## Native SDK compatibility sources

The runtime is pinned to `openai-codex==0.154.0`. Compatibility behavior is checked against the pinned [role override implementation](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/agent/role.rs), [native spawn implementation](https://github.com/openai/codex/blob/rust-v0.154.0/codex-rs/core/src/tools/handlers/multi_agents_v2/spawn.rs), and [hook configuration and trust documentation](https://learn.chatgpt.com/docs/hooks). The SDK merges supplied subprocess environment overrides with the parent environment; protected credentials are explicitly cleared at this boundary.

The worker uses the pinned SDK’s Landlock backend in unprivileged Linux containers because nested bubblewrap namespaces are blocked by the host container profile. Only the per-job workspace is writable; broad TMPDIR and /tmp roots are excluded. Specialist scope declarations are stored outside that writable root, and turns inherit the configured thread policy. The filesystem sandbox remains enabled; no privileged container or host profile change is required. Hosted read-only web search is a shared native capability; authenticated IF/domain MCP permissions are separately scoped per Specialist.
