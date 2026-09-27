# Current-max acceptance closure

## Result

The required mutation is the existing native `performance.health_update_current_maxes` operation. It is not internal-only: its operation contract has `ownership: athlete`; `services/permissions.json` maps it to `performance:write` without `internal_only`; and `services/app.py` exposes normal authenticated `/operations/{name}` and MCP transport. The normal portal has no route for it, which is why `PUT /api/maxes/:version` cannot satisfy this check.

`health_update_current_maxes` is the only checked writer that changes `Program.current_maxes` directly. It calls `ProgramStore.mutate_source`, so it requires the Program's current `meta.revision` and an idempotency key, commits through the normal revision/idempotency path, and returns the new current-max map. `max_target_update` changes target values; `max_history_add` writes only `max_history#{version}`; onboarding athlete-basics writes Person settings plus max history. Neither changes `program.current_maxes`. A logged Session has no writer that persists this field. `program_update_meta_field` can alter `meta.manual_maxes`, but it is a fallback only and cannot prove the requested first-precedence source changed.

## Minimal Luna path

Use the existing native-service harness transport in `scripts/test_powerlifting_services_live.py`: authenticated request to `http://pl-performance:8000/operations/health_update_current_maxes`, with the dedicated Luna Person and Athlete principal scoped to that operation. It needs the internal transport token and a freshly signed principal exactly as the existing harness's `headers(operation)` does; do not add a public backend route or use DynamoDB directly.

1. Read Luna's current Program through the ordinary authenticated portal `GET /api/programs/v020` (or the current alias that resolves to this Program). Record only: `meta.revision`, `current_maxes.squat`, the side form slot's ready `video_id`, status, and target/allocation revision.
2. Call `health_update_current_maxes` with `{squat_kg: 186, expected_revision: <read revision>, idempotency_key: <fresh key>}`. The authenticated service overwrites supplied `pk` with the Luna Athlete scope, so omit it. Assert returned squat is 186.
3. Re-read `GET /api/programs/v020`; assert `current_maxes.squat == 186`, then assert Lift Profile's preview source remains the first operand (`current_maxes`, not `meta.manual_maxes`) and the side slot's exact ready id/status/revisions are unchanged.
4. Restore only squat with the original value, a new Program revision, and a new idempotency key. Re-read the Program and assert the original value and the same ready slot fields. Retrying either request must reuse its exact idempotency key and return the same result; do not send a different payload under that key.

The frontend source confirms the hydration chain: `LiftProfilePage` reads `useProgramStore().program`; `loadProgram` hydrates it from `api.fetchProgram(version)`; the displayed value is `program.current_maxes[lift] ?? program.meta.manual_maxes[lift] ?? 0`. Updating `current_maxes` is therefore the authoritative, first-precedence test and produces a concrete UI-source assertion without writing a computed output.

## Portal cache observation

The native mutation does not pass through the backend's `invalidateAfter` middleware. A cached ordinary Program response therefore stays stale for the backend cache TTL of 604800 seconds (seven days), not a short cache window. Do not wait for it. Immediately make the same authenticated portal request with one new inert query value, for example `GET /api/programs/v020?acceptance_read=<fresh-uuid>`. The cache key is the complete URL, while the route ignores that query, so this is a normal read routed to the authoritative Program and proves the portal can observe the mutation. A normal `GET /api/programs/v020` remains unsuitable until cache expiry.

## Deployment attestation

Read-only live checks at 2026-09-15 show `pl-videos` Ready 1/1 on `sha256:17a58b454b834eccf2f3033598fc5718c15cd4cf2d66b2516cfcd0af9a0076ba`; its pod was pulled and started cleanly. The live container's `/opt/powerlifting/lambda/pod_videos/handlers/video_remove/core.py` has SHA-256 `789a45d13e59ed67376a4930e00942435ef494d41511a3f5544bf5d5cf377798`, exactly matching the reviewed workspace file. The supplied matching image composite hash `9e2c7fe6…1248070c` closes the source-to-image comparison for this artifact. `pl-performance` is independently Ready 1/1 on `sha256:6d0a745a531b1deba442b263f3bd65013deb69228f9138e35c16885c7b01016a`, so the 17a digest is a videos/analytics service image, not a replacement performance image.

The 17a rollout is real and newer than the prior 6c4 videos ReplicaSet. The review confirms the material difference in `video_remove`: when the removed id is both `video_id` and `pending_media_id`, it clears the whole first-pending slot; when it is only pending beside an older ready recording, it removes pending fields and restores the ready presentation. The focused tests cover ready removal, first-pending removal, old-ready removal while pending survives, pending removal while ready survives, repeat removal, and CAS retry. A fresh local run of `python3 -m pytest services/tests/test_videos.py -q` passed 19 tests. The service authorization also requires both videos and Lift Profile write permission for form-video removal, and all live evidence is scoped to Luna, so this change has no author or cross-Athlete privacy bypass.

## Remaining acceptance evidence

The current artifact now proves actual current-max mutation and restoration: Luna Program squat `135 → 136 → 135`, revisions `58 → 59 → 60`, with ready id `cfdfeff6-5ecd-5079-ad8c-17805c55abfe` and its ready status/revisions unchanged. The only current media gap is a successful valid replacement B proving the new target revision is exactly previous revision + 1. The existing 181-second B2 proves failure/retry preservation but does not replace the ready recording. A short fresh A/B run closes this: ready A, reserve valid B, assert B target revision = A revision + 1 while A remains published, confirm/process B to ready, then assert B is published at that same target revision.
