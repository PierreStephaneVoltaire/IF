# Bug List — Powerlifting Portal (serverless branch)

## Fixed
- [FIXED] `program_store.py` `_list_programs_sync` — `return results` was missing (dangling at wrong indentation). `program_list_full` returned `null`. Fixed by moving `return results` into the method.

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

## Code Fixes Applied (NOT YET DEPLOYED — need ECR image rebuild)
1. `program_store.py` `_list_programs_sync` — `return results` was outside the method. FIXED.
2. `health_list_competitions/core.py` — `TypeDeserializer` used but never imported (crash on import). FIXED (removed unused line).
3. `pod_glossary` image missing `rapidfuzz` dep — OLD image built before rapidfuzz was added to requirements.txt. ECR wiped, CI will rebuild.
4. `pod_analysis` image missing `scipy` dep — OLD image built before scipy was added. ECR wiped, CI will rebuild.
5. `pod_competition` image missing `scipy` dep + stale routing table (health_list_competitions not in OLD routing). ECR wiped, CI will rebuild.
6. `programController.ts` `batchCreateWeek` — used `session_list_full` (loads all 453 full sessions, slow). CHANGED to `session_list` (summary, fast). This fixes the "session design crashes" issue.
7. `max_target_get/core.py` — target maxes stored as strings in DynamoDB, returned as strings. Frontend `typeof === 'number'` check fails, defaults to 0. FIXED: added `_to_number()` to convert strings/Decimals to numbers.
8. `program_get/core.py` — `current_maxes` stored as strings in DynamoDB. Frontend `positiveNumber()` checks `typeof === 'number'`, strings fail. FIXED: added `_coerce_current_maxes()` to convert string values to numbers.

## Issues Resolved (no code change needed)
- `session_list_full` timeout was a kubectl exec test artifact (30s tool limit), NOT a backend issue. The backend's `invokeLambda` has no timeout and works fine.
- Videos endpoint (`GET /api/videos`) works — uses `video_library_get` fission function, returns data correctly.
- Competitions data exists in DynamoDB (if-powerlifting-user-competitions table has operator's COMP# items). Will work once pod_competition image is rebuilt.
- `current_maxes` at top level of program: `{'bench': '115', 'deadlift': '220', 'squat': '185'}` — values are strings but frontend handles this with `positiveNumber()` conversion.

## Possible Bugs (need investigation)
- Video upload (`uploadSessionVideo`) calls `listSessions` (which uses `session_list_full`) to find a session by date — loads ALL 453 full sessions. Performance issue, not a crash. Could be optimized with a `session_get_by_date` fission function.
- Video upload also needs the session's existing `videos` array, so a simple summary won't suffice. Low priority since video upload works, just slow.
- Fission pods use `pl_common_env` hardcoded env vars instead of inheriting from IF agent API configmap. User said they should inherit same env vars. Current env vars are correct values but injection method differs. Low priority — values are correct.