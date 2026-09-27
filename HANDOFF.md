# IF and Powerlifting rewrite handoff

## Completed production visibility and UI restoration — 2026-09-16

The latest user requirements supersede the earlier combined-role layout:
separate Athlete and Coach views chosen after sign-in; no Coach roster on an
Athlete profile; profile visibility separate from page preferences; profile,
inbox and roster management grouped in Settings; tags restored to selected pills
with a plus modal, approved catalog choices and submitted/pending feedback.
Also fix empty Competition view and unavailable videos. Preserve the earlier
master-federation dropdown, manual-estimate removal, top-banner removal and
Back/context-restoration work. Final frontend is `b9d2ac18…` generation 14,
Federation service `97de3419…` generation 12 and analytics reports `2f9ea229…`
in deployment generation 22. All are Ready. Terra accepted source, mocked checks
and normal-authentication live checks, including 23 master Federation choices
for a Coach with zero personal-library entries. Workspace checks and the actual
ProgramStore empty-next-Block preservation regression pass. See the scoped
`profile-ui-*` release, review and inventory records under
`deploy/rewrite/powerlifting-backlog/`. The gateway remains `b688…`; the separate
gateway candidate was unused because analytics runs in the reports sidecar.

Verified production issue: current pointer selected v021 with zero Sessions.
All 453 unique Sessions remain under v020 (407 status=completed, 46 planned;
the earlier 417 figure counted a legacy boolean). Six Blocks, 92 legacy-current
Sessions, date span 2023-05-10 through 2026-08-22, and 41 video references remain.
The operator Competition table has 196 records. Only four raw value paths differ
between v020/v021: sk, meta.updated_at, meta.version_label, added template_lineage.
Both Program records otherwise match recursively. An older Template-apply handler
replaced the full session set; predecessor code, timestamp and record shape support
that provenance, but the exact old live image has not been reconstructed.

Private 0600 forensic snapshots are `/tmp/operator-training-if-health-20260915.json`,
`/tmp/operator-training-if-sessions-20260915.json` and
`/tmp/operator-training-programs-20260915.json`. Never copy their raw contents
into release docs. Safe count/hash manifests are alongside them.

Implementation Luna `profile_federation_master_dropdown` applied the Terra-reviewed
conditional one-item pointer repair back to v020. The allocation version remains
21 and revision is now 1. Independent hashes verify both Program records and all
453 Session rows are unchanged; v021 and its lineage remain preserved. See
`deploy/rewrite/powerlifting-backlog/production-visibility-recovery.json`. Normal
operator browser verification remains unavailable. An extra in-pod verification
probe caused one Program pod OOM/restart; the pod recovered and probes stopped.
Read-only auditor `audit_operator_training_data` must not implement. Thread limits
prevent new/revived implementation agents; do not adjust limits. Root coordinates
and writes docs only. The latest UI fixes, historical Block labels and preservation
regression are complete. Remaining acceptance limits are owner/operator browser
and video playback, the pending Cloudflare allowance, genuine operator tag approval
and full Discord consent. No Git writes, AWS resource deletion or second environment.

## Completed profile setup corrections — 2026-09-16

The operator requires federation choices from the existing master catalog before
personal libraries are populated and removal of manual estimated-1RM checkboxes
from onboarding/basics editing. Fresh Luna `profile_federation_master_dropdown`
owns product implementation and rollout; Terra `review_profile_federation_master`
owns source/live review. Root owns durable docs and manifest evidence.

Live master federation table has 23 rows with a hash-only federation-ID `pk` and
no sort key. The old `pk=operator` query returned no rows. The corrected scanner
retains pagination and canonical IDs; absent optional fields are omitted to meet
the output schema. Master catalog caching was invalidated narrowly after the fix.
No new table or per-Athlete library import is needed. Removing estimate controls preserves
existing metadata: the backend currently turns omitted flags into false, so
blind payload deletion would erase it. Reuse the automatic logged-training e1RM
path without inventing estimates for empty records. Apply/test approval persists;
no Git writes, AWS deletion or duplicate environment. The reviewed pointer repair
above is the sole operator-record mutation; Programs and Sessions remain unchanged.

## Completed Discord redirect repair — 2026-09-15

The user reported Discord's invalid redirect URI. Live inspection found the same
Discord client sent with the Authentik-source callback instead of the configured
`https://dev.nolift.training/api/auth/discord/callback`. Fresh Luna
`finish_discord_oauth_regression` completed the direct Passport OAuth2 repair;
Terra accepted source and live checks. Gateway `b688e943…` is Ready at generation
31, with frontend and domain services unchanged. Four real-strategy tests and
workspace checks pass. Independent live browser checks confirm the original
Discord client/callback with no invalid-redirect message before consent, reject
invalid state, and complete fresh Authentik login with `/me` 200. Full Discord
consent/identity completion remains unverified. The compiled live auth hash
matches reviewed source. [Current evidence](deploy/rewrite/powerlifting-backlog/discord-login-correction.md)
supersedes the prior Discord acceptance and gateway pin below.

## Completed login/landing/mobile correction — 2026-09-15

Luna implemented, deployed and tested; Terra accepted the scoped correction.
Gateway `87403487…` generation 30 and frontend `5bb25bdb…` generation 12 are Ready.
All 18 portal Deployments remain Ready. Dedicated guest landing and both login
choices are restored, informational read-only banners are removed, and small-screen
context/navigation plus Dashboard sizing are fixed. Actual Discord authorization
dispatch, a fresh Echo Authentik login, invalid-state rejection and genuine browser
checks pass. No completed Discord identity login or fully reverified cross-Athlete
round trip is claimed. Unrelated avatar/ranking responses are in `bug.md`.

Current evidence: [entry correction](deploy/rewrite/powerlifting-backlog/entry-mobile-correction.md),
[sanitized summary](deploy/rewrite/powerlifting-backlog/entry-mobile-summary.json),
[review](deploy/rewrite/powerlifting-backlog/entry-mobile-review.md) and
[inventory](deploy/rewrite/powerlifting-backlog/entry-mobile-runtime-inventory.json).
Executable manifests match the current immutable pins and retain rollbacks.
No Git writes, AWS deletion, second environment or operator-data changes occurred.
The earlier full-backlog checkpoint below is historical for gateway/frontend pins.
Cloudflare allowance and operator-only tag acceptance remain external limits.

## Prior applied release — 2026-09-15 10:45 UTC

Apply/test approval is already granted. Root coordinates and updates evidence;
Luna implements/applies/tests and fresh Terra reviews. Single existing environment;
no Git writes, AWS resource deletion, operator-data changes or extra Codex host.
Cloudflare allowance remains pending and genuine operator access is unavailable.

Current truth is [release evidence](deploy/rewrite/powerlifting-backlog/deployment-evidence.md)
and the [backlog delivery table](utils/powerlifting-app/POWERLIFTING_FEATURES_BACKLOG.md).
The chronological entries below are historical, including their approval,
old-image, limitation and unfinished-work statements.

The final inventory records all 18 portal Deployments Ready, zero restarts;
16 domain services pass 22 selected HTTP/MCP checks. The local service suite
passes 253 tests and 16 subtests. Executable manifests match the mixed live pins:
gateway d4cbce47; Analytics/Profile/Videos 17a58b45; Analytics reports c868c906;
Program/Templates da1aca5e; Performance 6d0a745a; other ten domains 008f6c22;
frontend a7aad69a. API 3076896f and native worker ca816dfd remain unchanged by
these final scoped portal rollouts. Full immutable digests are in the inventory.

Block/Template replay, real report generation/cache, genuine onboarding, distinct
Coach/Handler races, browser offline/authored-note checks, max response repair,
180/181-second media processing, removal and Program/native read coherence pass.
Exact unused local Docker builds were pruned after ECR and container-use checks.
The actual concurrent media race, Handler/Coach/native Lift Profile context,
deployed numeric bar/unit guidance and final Terra review pass. The remaining
external acceptance is Cloudflare 500 MiB and genuine operator approval/catalog/
approved-tag AND/OR. No additional approval is needed for the already applied work.

Isolated Luna/Echo/River records retain test history. Four Echo report Sessions
and report-source peer reads remain; its conceptual Handler relationship was
restored under request 5dfac996fe9644c0989befc2aa086c23. Twenty-one search fixtures
are private again. New owned media is removed through app operations; copied
operator media is read-only. Raw copied Programs and credential/session files
remain private in /tmp and must not enter release documentation.

## Historical handoff entries

## Social live acceptance closure — 2026-09-15

Terra accepted the two `pl-profile` fixes and 18 focused tests. The shared services image was built and pushed as `sha256:8bc0af43eaa46cf47521f461888134916bbfae9df70a927c5d3ae3fdaaff9ba3`; only `pl-profile` was rolled, and its pod is Ready on that exact digest. Real OIDC sessions for isolated `live-acceptance-luna` and `live-acceptance-river` verified: repaired Coach approval returned 200 with expiry `2026-10-03T23:59:59.999999+00:00`; approval replay returned 200; River's selected Luna program returned 200 while the grant was active; a racing peer approval produced one 200 and one 409; an unconfirmed second Coach request returned 422 `current_relationship_confirmation_required`; same-recipient replacement approved and then revoked successfully; revocation removed program access with 403; and the peer grant was revoked with access remaining 403. A stored 2025-10-04 competition produced an approved relationship expiring 2025-10-11, listed inactive and denied program access, proving no untied 60-day fallback. Publication GET, update, idempotent replay and restore all returned the schema projection `{domains, revision}` with statuses 200. Details and IDs are in `/tmp/social-live-acceptance-checkpoint.json`.

The distinct rival-Coach replacement scenario is limited by the two isolated test accounts; same-recipient replacement and transactional racing were exercised. Cloudflare's 500 MiB request allowance upgrade remains pending, so full-size video acceptance is still blocked. No source operator or Echo records/media were changed.

## Current authorization and live execution — 2026-09-15

Live social acceptance checkpoint 2026-09-15T06:45Z: Luna/River OIDC sessions are valid. Relationship request `09b9ea61ea0a427681826da2178082a6` was created idempotently with stored competition `6ed42c82-1ee3-4cee-8846-5459e1936ec2` (2026-09-26), producing expiry 2026-10-03T23:59:59.999999+00:00. Approval currently fails live with HTTP 500 because `utils/powerlifting-app/services/relationships.py` writes reserved DynamoDB attribute `permissions` without an expression alias. Publication GET currently fails live with HTTP 500 because `utils/powerlifting-app/services/publication.py` returns persisted `idempotency_key` and `updated_at` fields rejected by the `settings_publication_get` result schema in `utils/powerlifting-app/services/operations/profile.json`. Other live checks passed: favorite no-access, request idempotency, cancellation/history, private note/share/detach, normalized deduplicated pending tag, self-approval denial, public profile/search, and private restoration. Full details: `/tmp/social-live-acceptance-checkpoint.json`.

Latest verified checkpoint: gateway `e96ebc034ddc3d4655b2b326158917b4a6a6251f490ab38bb20a4b2aa91c70c1` is live, and real Luna Passport login succeeds. `/tmp/live-acceptance-luna-storage-state.json` is now authenticated (private `0600`). A route-specific Powerlifting HTTPS header fixed secure-cookie issuance; sending a validated random authorization state fixed the callback. Terra accepted both. `/tmp/oidc-luna-auth-evidence.json`, `/tmp/public-boundaries-live-acceptance.json`, and `/tmp/native-backlog-live-acceptance.json` record real login, public/forged/media-boundary denial, and native tool/idempotency/continuation passes. Block/training live acceptance is active under Luna `blocks_live_execution`; Echo media execution follows, with harness corrections required by Terra. Remaining features need live acceptance. This checkpoint supersedes the earlier unresolved-login descriptions below.

The user explicitly approved the reviewed applies and testing at 04:52 UTC and said six hours remained. Do not ask for the same approval again. Root coordinates; Luna implements/applies/tests and Terra reviews. All original no-Git-write, no-AWS-resource-deletion, single-environment, and no-extra-Codex-host constraints remain.

The ECR retention updates and API/foundation apply completed. API digest `3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f` is live and healthy; all three relationship indexes are ACTIVE. After the initial gateway rollback, Luna corrected Authentik's route-specific forwarded scheme and removed the broken internal OIDC fetch rewrite. Terra accepted the correction; public discovery returns the exact HTTPS issuer. Corrected gateway digest `e9d0b285d9c891686432e8a3d41a99ea4cb188bb732c0a3627146edcc26516fe`, all sixteen domain service candidates, and the frontend candidate are now deployed and Ready. The media plan applied; CloudFront invalidation `IE71FSYP9K4VCIH1WBN5OVU3WM` was started. Execution evidence is in `deploy/rewrite/powerlifting-backlog/deployment-evidence.md` and JSON; current worker checkpoints are `/tmp/oidc-rollout-checkpoint.json` and `/tmp/oidc-rollout-image-verification.json`. Authenticated feature acceptance is still in progress; readiness is not feature acceptance.

Real Authentik test accounts `acceptance-luna-20260915`, `acceptance-echo-20260915`, and `acceptance-river-20260915` exist with isolated `if-user` mappings `live-acceptance-luna`, `live-acceptance-echo`, and `live-acceptance-river`. Normal OIDC login succeeded on the old gateway but `/api/auth/me` hits the old username-based settings failure. The reviewed copy helper copied 701 records to Luna without modifying operator source. The 16-service/20-check smoke is OLD-image baseline, not candidate acceptance. Echo is reserved for `prepare_live_media_tests`; do not race its test credential/session setup. Cloudflare upgrade is still pending; full 500 MiB acceptance waits, other tests continue after corrected gateway rollout.

Prepared credentials for all three test accounts are private `0600` files under `/tmp/live-acceptance-<name>-credentials.json`. The six-second Echo media fixture is `/tmp/live-echo-media-6s.webm`. The first candidate browser harness stopped at Authentik identification and did not establish a Passport session; its early 404 responses are not authenticated mapping evidence. Terra is tracing the full login callback. Luna `fix_oidc_resume_rollout` owns deployment and subsequent acceptance/fixes; root coordinates. Runtime thread limits currently reject additional Luna starts; do not alter limits or move implementation to root.

All approval-pending and old-image statements below this current section are historical. The user's latest explicit apply/test approval remains active.

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


## Powerlifting coordinator queue: worker slot limit

Fresh rollout-worker starts and an existing Luna follow-up were rejected by the collaboration thread limit after candidate review. The coordinator has not taken over implementation. The release package is now complete; retain this as historical coordination context.

Next bounded task: create the immutable gateway + sixteen-service rollout/rollback package in deploy/rewrite/powerlifting-backlog, correct first-time principal/session-key wording, and reproduce the nine-file package-manifest hash. Candidate images and the combined protected API plan have Terra review evidence; no apply or deployment has run. Frontend candidate waits for the active stable-ID/draft-race fixes and Terra review. Cloudflare upgrade remains pending.

## Powerlifting continuation: reviewed fixes and refreshed candidates

The earlier rewrite approval does not authorize the new backlog Terraform rollout. No backlog deployment, Terraform apply, retention-policy update, AWS deletion, or Git write has run. The user explicitly confirmed the Cloudflare request allowance upgrade is still pending. Root coordinates only; Luna implements and Terra reviews.

Fresh Terra reviews accepted Session stable identities across browser/HTTP/MCP, ambiguous date rejection, deleted-ID conflicts, and all four legacy handlers retaining the request-selected Athlete partition. Scoped Markdown caches retain delegated reuse while rechecking source grants and competition ties; private glossary/settings sources are projected before generation. The final coverage review found no additional missing core behavior across all 21 features, Blocks, offline edits, and media. Deployed acceptance remains pending.

Refreshed ECR candidates, with accepted provenance: API `3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f`; services `c3f5af1b70570d87fcf0044a302b980d3c90b0549cf9e323f36ee0b5ecd04d92`; Analytics `60c83f4c17f59b32ac19e7b1da5894d4ee2fdc9b17e1e2d0942ce1c3987cc69e`; gateway `27c6ddb82e236602a05ddb3c4af6a854bb31c29dbfeba1a97865802be5c4b1b9`. Latest publication checks: 223 service tests, eight root access/tool tests, backend typecheck/build. Tags are mutable; rollout pins immutable digests. Details are in `deploy/rewrite/powerlifting-backlog/`.

The executable 18-Deployment rollout/rollback package has eight passing mocked regressions and Terra closure for exact API preconditions, namespace/container allowlists including the frontend, atomic Analytics updates, executable partial-failure rollback, immutable candidate validation, and truthful dry-run preflight summaries. First-time principal/session secrets must be created once and preserved across rollback. Candidates are accepted and the frontend is enabled; protected Terraform deployment approval and deployed acceptance remain pending.

ECR retention removed the old Analytics index. The cached Linux/AMD64 child was recovered and published as `sha256:a81b36df0c9b717db2d882f9d1434eae0b2061ad318ffda601fa55dbc90f4c17`, with matching configuration and all twelve layers. Original index `138fad...` is historical because its attestation is missing. Terra `/root/review_recovery_retention` is reviewing the recovery and non-deleting policy payloads. Saved lifecycle Terraform plans that replace policy objects are UNAPPLICABLE under the no-AWS-deletions constraint. No policy update has run.

AuthoredNotes context guards and the social mounted regression are accepted by Terra. Social closure records 18 scenario checks plus aggregate with all eight state outcomes verified and no unhandled, browser, or expected-response errors. Local offline checks passed 25 checks; live revocation/conflict acceptance remains pending. Frontend publication is staged behind protected deployment approval.

Next: obtain the required protected approval for the digest-pinned API/foundation and media plans, then run the staged retention and bounded 18-Deployment portal rollout sequence. Record deployed acceptance and the full 500 MiB media test afterward; the latter waits for the confirmed external Cloudflare upgrade. Local disposable image cleanup is complete and recorded in the release package.
