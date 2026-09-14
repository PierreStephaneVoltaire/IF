# Native Codex conversation contract — 2026-09-14

The operator approved and deployed the native runtime on the main k3s node. All 20 affected Deployments are ready; deployed native canaries passed. The disconnected queue/classifier/planner source has been removed after acceptance; both cleanup images are deployed and verified. This document supersedes the execution sections of [rewrite.md](rewrite.md); its historical acceptance record remains intact.

## Runtime

The API retains listeners, scoped Facts and Directives, history, domain access, artifacts and the Discord delivery outbox. Its isolated worker is now an authenticated HTTP host for `openai-codex==0.154.0`. It admits two top-level Conversations and two native children per Conversation, with no waiting execution queue. Capacity exhaustion returns 429 before accepting work. Status, events and cancellation remain available.

Each authenticated Person and stable Conversation ID maps to a persistent native thread. A follow-up starts a new turn on that thread or steers its active turn. Independent requests without a Conversation ID receive distinct IDs; message content never supplies identity. Sol with medium reasoning is the coordinator default; an explicit `gpt-6-astra` request is accepted only when the subscription catalog supports it. Specialists default to Luna for straightforward work and Terra for analysis/review. The host validates model and reasoning choices against that catalog. It requires ChatGPT subscription authentication and provides no paid API fallback.

Native children start with fresh context. Native hooks enforce registered Specialist roles and tool scopes, and signed MCP credentials bind every call to a live turn. Ambient shell/filesystem access is disabled. Scoped tools provide history, attachments, artifact writing and thinking skills. Facts, signals and refreshed Directives use the authenticated Person/Conversation scope. Reflection and Heartbeat use the same host with idle-only admission.

Host state is `/work/host/turns.sqlite3`, with persistent workspaces in `/work/host/conversations/`. `CODEX_HOME=/var/lib/codex` retains authentication and native thread state. Both volumes are required for restart recovery. The API's existing history volumes are retained; safe legacy history is copied once into canonical Person/Conversation directories, and native history is bootstrapped once with its original roles. Ending a Conversation resets its native binding and retains history.

The host journals accepted inputs, steering acknowledgements, events, native IDs, artifacts and delivery state. Reusing an accepted idempotency key does not execute again; changing its request conflicts. An ambiguous steering/dispatch acknowledgement remains uncertain. Reconciliation reads persisted native turns, recovers completed responses and preserves canonical domain results. Interrupted or unknown work is never automatically replayed. Turn credentials are revoked on cancellation or completion.

Discord inputs submit directly, preserving message/edit IDs and attachments. `sir_simpalot` (ID `400750817382236160`) maps to the existing `operator` Person. Other users have independent Person scopes. Slash status/cancel/end commands address the same Conversation as ordinary messages. Completed deliveries are durably enqueued using the native execution reference before acknowledgment, allowing API restart recovery without duplicate enqueue.

## API

All private calls require `X-Internal-Token`; Person-facing calls also require `X-Person-Pk`. Browser traffic continues through the authenticated `/api` gateway.

| Interface | Behavior |
| --- | --- |
| `POST /v1/chat/completions` | OpenAI-compatible response/SSE, stable optional `conversation_id` or `chat_id`; independent ID otherwise. Explicit errors terminate streaming cleanly. |
| `POST /v1/conversations/{id}/turns` | Messages, optional model/reasoning/Specialist/output schema, idempotency key. Returns the accepted reference immediately. |
| `GET /v1/conversations/{id}/turns` | Scoped native executions and thread/turn IDs. |
| `GET /v1/conversations/{id}/turns/{turn}/result` | 202 while active, 200 for terminal records; accepts native turn ID or acceptance reference. |
| `POST .../{turn}/cancel` | Native interruption without waiting for a capacity slot. |
| `GET .../{turn}/events?after=N` | Durable SSE with a resumable cursor. |
| `POST /v1/jobs` | Compatibility for named asynchronous domain operations only. No general inference or conversation submissions and no waiting queue. |
| `GET /v1/jobs/{id}` and `/result` | Native execution lookup, with historical SQLite job lookup retained. |
| `GET /api/analytics/generations/{id}` | Authenticated Athlete-scoped generation status/result. No generation side effects. |

A job-compatible acceptance reference exists before the SDK returns native IDs. Once started, records contain both `thread_id` and `turn_id`. Primary domain dispatch is journaled before calling its service; an ambiguous initial call cannot be replayed. Only the matching primary execution may supply its canonical final result or generation credentials.

## Powerlifting

All sixteen services and their deterministic HTTP/MCP operation inventory remain. AI operations use native domain continuations, including imports, template evaluation, budget advice, glossary and lift-profile assistance. Active domain work delegates native children and resumes its existing execution; it never submits another top-level execution and waits for it.

Report generations live in the existing analysis-cache table under Athlete scope. Their reference hashes report type, input snapshot, historical window and source data. Current-program reports retain the source snapshot used for the hash; evaluations include federation data. Duplicate requests reuse a generation, and unchanged completed reports return its validated cache. Generation attempts prevent a late prior attempt from replacing a newer result. Failed/interrupted/lost work requires explicit retry. No new AWS resources are required.

Analysis manifests and section status read records without computing sections. Cache-only block/comparison requests also avoid computation. Browser report requests receive generation references and poll the authenticated gateway. Supporting reports retain cache markers and metadata across synchronous and asynchronous paths. Exports consume completed cached AI reports. Template imports retain progress and parsed results for review/apply; successful application preserves the job reference and draft template link.

## Verification

Run the focused suites and required builds:

```bash
PYTHONPATH=app/src /tmp/if-rewrite-venv/bin/python -m pytest app/tests -q
cd utils/powerlifting-app
/tmp/if-rewrite-venv/bin/python -m pytest services/tests -q
npm run typecheck
npm run test:forwarding --workspace backend
node --import tsx --test backend/src/routes/analytics.test.ts
npm run build
```

Results before retirement: 48 IF tests; 96 Powerlifting tests plus 7 subtests; 6 backend forwarding tests; 2 analysis status/cache tests; all workspace typechecks and the required build passed. API, worker, shared-service and Analytics images built and passed import checks; current source/compiled-output hashes matched their image contents. The audit excluded a stale local compiled file whose TypeScript source no longer exists.

Offline tests cover admission, concurrent Conversations, steering idempotency, cancellation, restart reconciliation, role-preserving history, scoped tools, refreshed instructions, canonical domain dispatch/results, report references/cache reads and import behavior. These are separate from real SDK canaries. After retiring obsolete queue/classifier tests and retaining historical lookup, scope and quota checks, all 39 current IF tests pass.

Actual main-node canaries used isolated local HTTP bridges and the real subscription SDK, native Specialists, deterministic domain handlers and synthetic Athlete report records. They did not send Discord messages or replace cluster workloads. Evidence is in [native-canary-results.json](native-canary-results.json), with private raw runs under `/tmp/if-native-canary-20260914`, `/tmp/if-native-extended-20260914` and `/tmp/if-native-final-20260914`. Verified: greetings without classification, same-thread follow-ups, two concurrent independent Conversations, Luna/Terra delegation, a scoped kg-to-lb tool, report generation/dedup/cache, steering, native cancellation, persisted response recovery and SDK restart thread reuse.

The newly deployed sixteen services passed all 20 read-only contract/parity checks (`/tmp/if-native-deployed-domain-contract.log`). Real deployed canaries also passed thread reuse, idempotency, two concurrent Conversations, capacity rejection, status while full, Person/token authorization, Luna/Terra delegation, a scoped calculation, steering, native cancellation, chat-completion SSE, report generation/dedup/cache, template import review/apply and duplicate-apply denial. An actual host Pod restart interrupted only a synthetic turn, marked it uncertain, and retained the earlier Conversation on its same native thread. See [native-deployed-results.json](native-deployed-results.json). The final cleanup images passed same-thread resumption, historical lookup, operator mapping and retired-code absence checks. All 20 affected Deployments are ready on their final versions; immutable image references are in [native-published-images.json](native-published-images.json). Main-node measurements before/following canaries were approximately 2.6–2.8 CPU cores and 15 GiB RAM used, with 42–50 GiB disk free. After final image publication and removal of superseded local API candidates, the node used 2.6 CPU cores and 13.6 GiB RAM, had 28 GiB disk free and reported no memory/disk pressure. All six rollback images remain.

Remaining external checks: Discord edits/outbox delivery using an authorized destination, browser interaction through the import review screen, and cross-node/laptop network, volume, authentication and resource tests. The import service review/apply path and host Pod restart were tested live. Auth/quota failure paths were tested offline; the account was not deliberately exhausted.

## Rollout and rollback

Follow [native-rollout.md](../../deploy/rewrite/native-rollout.md). No Git writes, AWS deletions, unrelated Authentik/Postgres changes or laptop deployment were performed. Unused queue polling/leases, classifier/planner modules, implementation workers, ephemeral execution helpers and their obsolete tests/configuration were retired after deployed acceptance. Historical SQLite job lookup and the DynamoDB delivery outbox remain. Retired source is privately preserved in `/tmp/if-native-retired-source-20260914/`.
