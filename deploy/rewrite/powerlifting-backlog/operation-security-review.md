# Final operation-permission security review — 2026-09-15

Subsequent fresh review identified an omitted case: cached Block-analysis reads
use `analytics.blocks_get`, whose write-only permission/forwarding path rejects
read-only callers. That finding supersedes this review's broad no-defect verdict
for report cache handling. The analytics worker owns correction and acceptance.

## Verdict

No actionable source-level authorization defect found in this review. No deployment blocker for the reviewed operation boundaries.

## Source evidence

- The 221 operation names loaded from all sixteen `services/operations/*.json` manifests each have a `services/permissions.json` entry. The only two additional permission entries are the internal `domain_resume` and `generation_status` operations.
- Gateway invocation resolves the manifest operation, requires an `operationScope`, obtains current access from Profile, and sends a signed principal to the selected domain service: `backend/src/utils/lambda.ts:39-73`.
- Each service re-verifies the principal and replaces caller headers with verified acting-Person/Athlete claims before dispatch: `services/authorization.py:43-59`, `services/app.py:37-64`, and `services/dispatch.py:26-80`.
- Cache-only report reads use `cache_read`; generation uses the normal write permission: `services/access.py:26-46`. The markdown route passes `cache_only` and forces it for read-only callers: `backend/src/routes/analyticsService.ts:92-103`.
- Historical export is authorized as `program:read`; its program and analysis inputs are projection-filtered with current access before export: `backend/src/routes/export.ts:19-38`, `lambda/pod_training_program/handlers/export_program_history/core.py:325-338`, and `services/publication.py:58-85`.
- Profile and video media resolution verify that the referenced key is current and permitted before `GET`/`HEAD` Range streaming. Profile-avatar resolution independently recomputes access, including anonymous publication state: `backend/src/routes/profiles.ts:8-13`, `services/profile_media.py:5-13`, `backend/src/routes/videos.ts:65-77`, and `backend/src/controllers/videoController.ts:106-108`.
- The authored-note routes are not given a broad HTTP scope exemption: their controllers invoke mapped note operations, and note sharing computes permission from the requested context domain: `backend/src/controllers/authoredNotesController.ts:5-26` and `services/access.py:32-34`.

## Acceptance coverage limits

This was a source review, not new deployed HTTP/MCP evidence. It does not establish that every operation has been exercised against live Authentik sessions, nor replace the already-scheduled focused checks for delegated cache revocation, report/cache behavior, and remaining relationship/tag/notification scenarios. The pending Cloudflare allowance still prevents the 500 MiB upload acceptance test.
