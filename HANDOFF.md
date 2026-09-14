# IF and Powerlifting rewrite handoff

The operator asked to finish the rewrite and controlled main-node deployment/testing, then stop before laptop deployment and provide operator steps. The reviewed two-stage API deployment is explicitly approved. The original k3s localhost kubeconfig works; the cluster is running and the supplied AWS credentials are valid.

## Requested plan and completion

1. Record laptop work separately, without credentials, so it does not block main-node work. The handoff is `/tmp/if-laptop-handoff.md`; runnable steps and manifests are in `deploy/laptop/`.
2. Freeze the shared contract, executable schemas and complete capability/caller inventory. `docs/contracts/rewrite.md` and its JSON inventories cover 3,951 baseline Python functions, 200 typed operations and 169 literal backend callers.
3. Replace IF execution with pinned Python Codex SDK, the existing ChatGPT subscription, Sol coordination and scoped native Specialists. Main-node storage, identity, memory, Directives, Reflection, Heartbeat, channel listeners, registry/outbox and durable queue are retained. One top-level job and at most two children execute on the separate worker; cancellation/status/streaming/artifacts are implemented. No paid fallback exists.
4. Replace Powerlifting with sixteen Services/Deployments: Program, Sessions, Competition, Federation, Glossary, Goals, Budget, Calculations, Performance, Weight Log, Templates, Imports, Profile, Lift Profiles, Analytics and Videos. Existing storage/versioning/ownership/calculation/report behavior is preserved; AI operations continue through the single IF job without recursive queueing. Backend/frontend use the authenticated API gateway.
5. Use Luna writers and independent Terra reviews; fix parity/runtime findings and audit remaining execution paths. The reviews and fixes are complete, including Program/Session aliases, Heartbeat storage, shared Discord gateway, slash imports/autocomplete, native provider configuration and retired code.
6. Verify offline and on the accessible main node, then hand off laptop deployment. Offline: 32 IF tests; 92 Powerlifting tests plus 7 subtests; 6 backend forwarding tests; typechecks and required build. Main-node general/native/scoped/report, persistence, queue, memory, Directive and portal checks have passed. See `docs/contracts/acceptance.md` for exact evidence and limits.

## Current deployment

The approved API deployment completed; its final image is `sha256:d5bd14ff1e1dd67d87ea52cc6347697afd8fc5795757245d430c260cf75f4ffb`. API/worker and both portal deployments are Ready with zero restarts; all sixteen domain Deployments are Ready. Temporary diagnostics were removed, and one worker remains active on the main node. Final evidence is `/tmp/if-final-main-node-acceptance.json`. Active cancellation and a subsequent native calculation passed; cancellation also passed on the final worker image, with Tini as PID 1 and zero defunct child processes.

Published immutable images: worker `sha256:854cdab74660235823c651a8404569d99211704fa48dff3c848bde03be592879`, services `sha256:7240ef2dfafa7da711fb6cd955058b9ed14a174f020f649037de2cf2edd85358`, backend `sha256:1dafe860d461f573fc1255dc273a0a08657936ed987f945d803ab5fa677e303e`. `deploy/kustomization.yaml` pins worker/services/Analytics; laptop manifests use the same worker digest and the refreshed `ecr-registry` secret.

Four obsolete execution Directives were atomically revised to v002. All original v001 records, content and metadata remain; active-version lookup passed. The private guarded proposal/rollback is `/tmp/if-execution-directive-migration-v3.json` and `/tmp/migrate_if_execution_directives.py`.

The exact old Fission functions/triggers/package/environment and 71 reviewed compute objects were retired. Its namespace, CRDs, Helm archive and Bound 5 GiB storage PVC/PV remain, along with all AWS resources. Legacy source is recoverable in `/tmp/if-legacy-retired-20260913/`. No Git writes or AWS deletion occurred; existing Authentik/Postgres edits and both repositories' data were preserved.

## Deferred work and limits

Stop before laptop work. Follow `deploy/laptop/README.md`: join/label the laptop, prepare its own login PVC, complete subscription login, let the main worker finish, move one replica, verify cross-node traffic/artifacts/cancellation and resource headroom. Sol/native Specialist execution moves with the worker; API, queue, memory, conversations and outbox stay on the main node. Rollback restores the main-node selector and retained login PVC.

No Discord test destination was authorized, so actual test message reception/delivery is unclaimed. Alpha Vantage has no usable credential. Full OAuth/browser mutation workflows and forced subscription exhaustion were not tested. All laptop acceptance remains deferred. These are explicit limits, not evidence of missing k3s/AWS access.

The Meta-channel classifier schema error was corrected and deployed on 2026-09-14 UTC. All 35 IF tests pass. The deployed classifier returned a greeting through the live subscription queue and persisted the batch/intent in a synthetic channel; no test Discord message was sent. Latest evidence: `/tmp/if-meta-acceptance.json`. Docker pruning reclaimed 36.96 GB after the build triggered disk pressure; the API/worker recovered and node pressure cleared. See `deploy/rewrite/api-plan-review.md` for the incident and rollout record.
