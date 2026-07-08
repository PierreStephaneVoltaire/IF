# Bug List — Powerlifting Portal (serverless branch)

## Fixed
- [FIXED] `program_store.py` `_list_programs_sync` — `return results` was missing (dangling at wrong indentation). `program_list_full` returned `null`. Fixed by moving `return results` into the method.
- [FIXED] Dashboard.tsx — `LIFT_ROWS` in ranking percentile section only had squat, missing bench and deadlift. Added all three lifts.
- [FIXED] Dashboard.tsx — Three duplicate `dashboard-ranking-percentile` sections (lines 1130-1427) with only 1 lift each. Removed duplicates.
- [FIXED] ALL pod handlers (pod_sessions, pod_analysis, pod_budget, pod_competition, pod_federation, pod_glossary, pod_goals, pod_import, pod_lift_profile_ai, pod_maxes, pod_templates, pod_training_program, pod_user, pod_weight) — `json.dumps(result, default=str)` converted Decimal values to strings, causing frontend to receive kg values as strings instead of numbers. Fixed: replaced `default=str` with `default=_json_default` which converts Decimal to float/int.
- [FIXED] ALL sub-handlers (143 files in pod_*/handlers/*/handler.py) — same `default=str` issue. Fixed.
- [FIXED] `fission_entry.py` and `fission_server.py` — same `default=str` issue. Fixed.
- [FIXED] `session_store.py` `_public_session` — did not convert Decimal to float/int. Added `_sanitize_decimals` function.
- [FIXED] Terraform `pl_common_env` — missing `AWS_REGION` env var (fission pods had `IF_AWS_REGION` but Python code reads `AWS_REGION`). Added `AWS_REGION = ca-central-1`.
- [FIXED] Terraform `pl_common_env` — missing `POWERLIFTING_MASTER_FEDERATIONS_TABLE`, `POWERLIFTING_USER_FEDERATIONS_TABLE`, `POWERLIFTING_BUDGET_TABLE`, `POWERLIFTING_GOALS_TABLE` env vars. Added all.

## TODO: Deploy (needs CI rebuild after push)
- ECR images WIPED for: pod_glossary, pod_competition, pod_training_program, pod_maxes, pod_analysis
  CI pipeline will rebuild on next push. Code fixes are in place but NOT deployed yet.
- After CI rebuilds, restart the fission function pods to pull new images:
  kubectl rollout restart deploy -n if-portals -l functionName=pl-fn-pod-glossary
  kubectl rollout restart deploy -n if-portals -l functionName=pl-fn-pod-competition
  kubectl rollout restart deploy -n if-portals -l functionName=pl-fn-pod-training-program
  kubectl rollout restart deploy -n if-portals -l functionName=pl-fn-pod-maxes
  kubectl rollout restart deploy -n if-portals -l functionName=pl-fn-pod-analysis
  OR: kubectl rollout restart deploy -n if-portals -l executorType=container

## Deployed (terraform apply done)
- powerlifting_s3_bucket = "powerlifting-data-2b0f699b" added to terraform.tfvars
- terraform apply -target=kubectl_manifest.pl_functions completed (3 resources changed)
- pod_analysis env var POWERLIFTING_S3_BUCKET now set correctly
- pod_analysis restarted to pick up new env var

## Code Fixes Applied (NOT YET DEPLOYED — need ECR image rebuild + terraform apply)
1. `program_store.py` `_list_programs_sync` — `return results` was outside the method. FIXED.
2. `health_list_competitions/core.py` — `TypeDeserializer` used but never imported (crash on import). FIXED (removed unused line).
3. `pod_glossary` image missing `rapidfuzz` dep — OLD image built before rapidfuzz was added to requirements.txt. ECR wiped, CI will rebuild.
4. `pod_analysis` image missing `scipy` dep — OLD image built before scipy was added. ECR wiped, CI will rebuild.
5. `pod_competition` image missing `scipy` dep + stale routing table (health_list_competitions not in OLD routing). ECR wiped, CI will rebuild.
6. `programController.ts` `batchCreateWeek` — used `session_list_full` (loads all 453 full sessions, slow). CHANGED to `session_list` (summary, fast). This fixes the "session design crashes" issue.
7. `max_target_get/core.py` — target maxes stored as strings in DynamoDB, returned as strings. Frontend `typeof === 'number'` check fails, defaults to 0. FIXED: added `_to_number()` to convert strings/Decimals to numbers.
8. `program_get/core.py` — `current_maxes` stored as strings in DynamoDB. Frontend `positiveNumber()` checks `typeof === 'number'`, strings fail. FIXED: added `_coerce_current_maxes()` to convert string values to numbers.
9. ALL pod handlers + sub-handlers (143+ files) — `json.dumps(result, default=str)` converted Decimal to string. FIXED: `default=_json_default` converts Decimal to float/int.
10. `session_store.py` `_public_session` — did not sanitize Decimal. FIXED: added `_sanitize_decimals`.
11. `fission_entry.py` + `fission_server.py` — same `default=str` issue. FIXED.
12. Terraform `pl_common_env` — added `AWS_REGION`, `POWERLIFTING_MASTER_FEDERATIONS_TABLE`, `POWERLIFTING_USER_FEDERATIONS_TABLE`, `POWERLIFTING_BUDGET_TABLE`, `POWERLIFTING_GOALS_TABLE`.
13. Dashboard.tsx — `LIFT_ROWS` missing bench/deadlift + three duplicate ranking percentile sections. FIXED.

## Issues Resolved (no code change needed)
- `session_list_full` timeout was a kubectl exec test artifact (30s tool limit), NOT a backend issue. The backend's `invokeLambda` has no timeout and works fine.
- Videos endpoint (`GET /api/videos`) works — uses `video_library_get` fission function, returns data correctly.
- Competitions data exists in DynamoDB (if-powerlifting-user-competitions table has operator's COMP# items). Will work once pod_competition image is rebuilt.
- `current_maxes` at top level of program: `{'bench': '115', 'deadlift': '220', 'squat': '185'}` — values are strings but frontend handles this with `positiveNumber()` conversion.

## Possible Bugs (need investigation)
- Video upload (`uploadSessionVideo`) calls `listSessions` (which uses `session_list_full`) to find a session by date — loads ALL 453 full sessions. Performance issue, not a crash. Could be optimized with a `session_get_by_date` fission function.
- Video upload also needs the session's existing `videos` array, so a simple summary won't suffice. Low priority since video upload works, just slow.
- Fission pods use `pl_common_env` hardcoded env vars instead of inheriting from IF agent API configmap. User said they should inherit same env vars. Current env vars are correct values but injection method differs. Low priority — values are correct.
- Video fission functions (video_library_get, video_update_metadata, etc.) are deployed but have min_replicas=0 (non-pod functions). Cold start may cause first request to be slow. Not a bug, just latency.
- `POWERLIFTING_S3_BUCKET` env var only set when `s3_read: true` in resources.yaml. Only pod_analysis has this. Other functions that might need S3 access don't have it.
