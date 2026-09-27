# Profile federation review

Status: source accepted; live acceptance pending scoped deployment.

Live evidence: `if-powerlifting-master-federations` has a hash-only `pk` schema and 23 global catalog rows. Rows expose federation IDs in `pk`; the observed live rows do not contain `sk`. The current source query for `pk=operator` therefore returns an empty directory. The catalog must be listed independently of a Person's `federations#v1` library, with pagination, and its identity must be the existing compatibility key: `FED#` suffix when a legacy `sk` exists, otherwise `pk`.

Acceptance criteria:

- An authenticated onboarding Person sees active master catalog options before any personal library exists, can select more than one, and saves canonical catalog IDs without duplicate values.
- An unavailable or failed catalog request is distinct from an empty catalog; it is visible and retryable. Archived records do not appear.
- Existing saved federation IDs remain selected, and profile submission remains bound to the authenticated actor with normal Discord and Authentik flows unchanged.
- The manual estimated-1RM checkbox control is absent from onboarding and later basics editing. Existing `training_maxes_estimated` metadata is not erased by an edit; new no-data users gain no invented estimate flags. The canonical session/competition e1RM path is unchanged.
- Loading, failure, and selected-option layouts remain usable at 320px and 375px.

Not yet accepted: source review, compiler/tests, scoped deployment, normal authenticated browser checks, isolated-record checks, and mobile checks.

Source review evidence: the change uses a paginated master-table scan, removes the manual checkbox UI, retains loaded historic estimate flags only for submission, and marks catalog failure separately. `python3 -m pytest services/tests/test_federation.py -q` passed (4 tests); `git diff --check` passed. Workspace `npm run typecheck` cannot start because the checkout lacks ambient `react` and `serve-static` type definitions, affecting all workspaces before this change is checked.

Remaining implementation limitation: catalog failure is visible but has no in-place retry; a page reload restores it. This is not a source rejection for the narrow fix, but browser acceptance should verify the failure state remains usable.

## Operator program recovery review

The conditional repair changed only `operator/program#current`: its `ref_sk` now points to `program#v020`; its monotonic version remains 21 and revision is 1. The repair preconditions passed before the write: v020 and v021 matched their forensic snapshots, v020 had 453 external Session rows, and v021 had none.

Post-write verification: both Program records still hash-match their raw DynamoDB snapshots; all 453 external Session rows hash-match the snapshot as a canonical set. `program_get` creates a fresh ProgramStore for each request and resolves the current pointer again before listing Sessions. `video_library_get` also reads the current pointer per request. Neither path retains a process-level v021 result after the pointer change.

Verification limit: no normal authenticated session mapped to the production operator was available, so no claim is made that the operator's browser payload has been observed. A normal isolated Authentik browser session still returned a successful current-program response. A direct in-pod operator handler probe exceeded the Program pod's 256MiB memory limit, caused one OOM restart, and was not repeated. The replacement pod was Ready and its health endpoint returned 200 afterward.
