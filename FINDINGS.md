# POWERLIFTING PORTAL NO-DATA INVESTIGATION - FINDINGS

Started: $(date)
Goal: Find WHY the Analysis/Dashboard pages return no data in the live app.
Architecture constraint: Fission functions scale-to-0 (always cold start), ALL data/functionality comes from them.
Priority: Powerlifting portal operational.

## ENVIRONMENT
- Cluster context: default
- Namespace with app: if-portals
- App pods:
  - directives-portal-backend-86cb997fdb-2gffb (Running 5h43m)
  - directives-portal-frontend-ff6df8b8c-ckhnv (Running 161m)
  - if-agent-api-54cb9b7f9f-zqvz6 (Running 161m)
  - if-mcp-* (various, Running 5h35m)
- Fission pods (fission ns):
  - buildermgr-646dd6fcf4-4nrdx (77m)
  - executor-78644574d4-pfhkf (77m)
  - kubewatcher-5896669568-6vpgk (77m)
  - mqtrigger-keda-59559bd9d6-dq99r (77m)
  - router-695bdcd9cd-57p2r (77m)
  - storagesvc-6b747d4b76-bnm2f (77m)
  - timer-9b7df69bb-97rb5 (77m)
  - webhook-795594d7b9-2lc7d (77m)

## STEP-BY-STEP LOG

### STEP 1 - ENVIRONMENT MAP (done)
- Powerlifting portal pods (priority):
  - powerlifting-app-backend-65f844f75-x2q5g (10.42.0.75:3005)
  - powerlifting-app-frontend-fb9b6c7f5-wwjkn (10.42.0.252:3001)
- Fission functions live in namespace `if-portals` (not `fission`).
- Fission router = fission/router-695bdcd9cd-57p2r (fission ns).
- ~95 pl-fn-* fission functions registered, including analysis-related:
  pl-fn-analysis-section, pl-fn-analyze-powerlifting-stats, pl-fn-analyze-progression,
  pl-fn-analyze-rpe-drift, pl-fn-weekly-analysis, pl-fn-regenerate-analysis,
  pl-fn-get-analysis-markdown
- newdeploy-* services = fission executor warm pods (per-function). Many created ~130-140m ago.
- pl-fission-tools-257337765 pod (2/2 Running 81m) — likely shared env builder/tools.
### STEP 2 - LOG REVIEW (done)
- powerlifting-app-backend logs: ONLY /health (kube-probe) + /metrics (prometheus, 404).
  NO real user API requests in last 100 lines. Backend is healthy (200) but unused.
- powerlifting-app-frontend logs: ONLY `GET /` (SPA index) from 10.42.0.1 (gateway).
  NO /api/* calls visible. Frontend serves static SPA; browser then makes API calls elsewhere.
  CONCLUSION SO FAR: Either (a) browser never reaches backend (wrong API base / CORS / 404),
  or (b) frontend calls fission directly bypassing backend.
- Source located: /home/sirsimpalot/Downloads/discord-ai-bot/utils/powerlifting-app
  - backend/ (TypeScript/Express, has dist/)
  - frontend/ (Vite SPA)
  - lambda/ (fission entrypoints + deploy scripts)
NEXT: read frontend API config + backend routes for analysis/dashboard.
### STEP 3 - ARCHITECTURE + REQUEST FLOW (done)
- Frontend: axios baseURL = VITE_API_BASE_URL || '/api'. SPA calls /api/analytics/analysis/sections/:key?asOfDate=..&window=..
- Gateway HTTPRoute `domain-powerlifting-app`: dev.nolift.training → /api → powerlifting-app-backend:3005, / → frontend:3001. ROUTING WORKS.
- Backend env: POWERLIFTING_LAMBDA_BASE_URL=http://router.fission.svc.cluster.local:80 (fission router). INTERNAL_API_TOKEN empty.
- Backend route /api/analytics/analysis/sections/:sectionKey reads DynamoDB cache (if-powerlifting-analysis-cache).
  If cache miss, async worker calls invokeLambda('analysis_section', {...}) → POST router.fission/analysis_section.
- Backend IS receiving requests (log shows /api/analytics/analysis/sections/overview?window=block etc.).
  Mostly returns 304 (ETag cache hit — payload exists in DynamoDB). responseTime ~500-600ms.
### STEP 4 - ERROR HUNT (done)
- Found a 502 in backend logs: responseTime 5895ms, 'failed with status code 502'.
  → Consistent with a fission cold-start timeout OR a 502 from invokeLambda.
- Backend calls invokeLambda('analysis_section', ...) but the registered fission function is named
  'pl-fn-analysis-section'. SUSPECTED MISMATCH (verifying next).
- Fission functions all use ExecutorType: newdeploy (scale-to-0 = always cold start). Matches the requirement.
### STEP 5 - FISSION ROUTER TEST (done)
- Fission HTTPTrigger pl-ht-analysis-section maps relativeurl '/analysis_section' -> fn 'pl-fn-analysis-section'.
  So backend invokeLambda('analysis_section') is CORRECT. NO name mismatch. Earlier hypothesis WRONG.
- TEST 1: POST http://router.fission.svc.cluster.local:80/analysis_section (from backend pod):
  HTTP 200 in 4.39s. Cold start worked. Function returned data.
- TEST 2: POST /pl-fn-analysis-section -> HTTP 404 (route uses relativeurl, not fn name). Expected.
- FunctionTimeout=900s, SpecializationTimeout=90s. MaxScale=3, MinScale=0 (scale-to-0 confirmed).
- CONCLUSION: Fission DOES fire and returns 200. The 502@5895ms is intermittent cold-start timeout
  (first request after idle > the Express/fetch timeout or a cold start racing the cache miss path).
### STEP 6 - ROOT CAUSE FOUND (done)
- TEST 1 response body: {"body":"{\"error\": \"No module named 'analytics'\"}","statusCode":500}
  The fission function analysis_section returns HTTP 500: cannot import module 'analytics'.
- The fission function IS FIRING (specializes, runs Python) but its OWN code fails to import 'analytics'.
- This is a PACKAGE/BUILD problem, not a networking/timeout/CORS problem.
- Manifest endpoint (/api/analytics/analysis/manifest) returns 200 OK. Sections status:
  - overview: complete (cached:true, generatedAt 16:19:52)
  - fatigue_readiness: complete (cached:true)
  - workload: complete (cached:true)
  - peaking: MISSING (cached:false)
  - alerts: MISSING (cached:false)
  - ai_correlation: MISSING (cached:false)
  - program_evaluation: MISSING (cached:false)
  → The missing sections are exactly the ones whose cache was never populated because the
    analysis_section fission fn now errors out (No module named 'analytics').
  → overview/fatigue_readiness/workload are stale cached values from before the package broke.
- ROOT CAUSE: Fission package pl-pkg-analysis-section (and likely others) is built without the
  'analytics' module on the import path. When scale-to-0 cold-starts it, import fails = 500.
### STEP 7 - PACKAGE CONTENTS VERIFIED (done)
- tool_id.txt in pod = 'analysis_section' (CORRECT).
- Pod deployarchive layout (confirmed on warm pod before it scaled to 0):
  /userfunc/deployarchive/main.py            (entrypoint = fission_entry.py)
  /userfunc/deployarchive/build.sh
  /userfunc/deployarchive/tool_id.txt         -> 'analysis_section'
  /userfunc/deployarchive/analysis_section/__init__.py
  /userfunc/deployarchive/analysis_section/handler.py
  /userfunc/deployarchive/analysis_section/core.py       <- line 103: from analytics import weekly_analysis_section
  /userfunc/deployarchive/analysis_section/analytics.py  <- the ACTUAL module location
  /userfunc/deployarchive/analysis_section/config.py     <- line 104: from config import IF_HEALTH_TABLE_NAME
  /userfunc/deployarchive/program_store.py               <- LAYER module (pl-program), at archive ROOT -> resolves
  /userfunc/deployarchive/programs/ sessions/ glossary/ ... (other layer modules at root)
  NO /userfunc/deployarchive/analytics.py  (confirmed: ls analytics/ returned nothing)
  NO /userfunc/deployarchive/config.py
- fission_entry.py adds '/userfunc' to sys.path. The archive is at '/userfunc/deployarchive'.
  Python can import top-level modules at /userfunc/deployarchive/* (program_store) and the
  package 'analysis_section' (analysis_section.handler etc.), but CANNOT import a bare
  top-level 'analytics' because that file lives at analysis_section/analytics.py.

### STEP 8 - ROOT CAUSE (FINAL, CONFIRMED)
ROOT CAUSE: Lambda tool source files use ABSOLUTE imports of sibling modules that are
NOT layer modules. The deploy archive packages each tool's files under a folder named
after the tool (e.g. analysis_section/), so sibling files are sub-modules of that package,
NOT top-level modules. Absolute imports like:
    from analytics import weekly_analysis_section   (analysis_section/core.py:103)
    from config import IF_HEALTH_TABLE_NAME          (analysis_section/core.py:104)
    from export import build_program_markdown
    from prompt_context import summarize_lift_profiles
    from correlation_ai import generate_correlation_report
fail with 'No module named X' because X is at <tool>/X.py, not at archive root.

Layer modules (program_store, programs, sessions, glossary, templates, imports, federation,
analysis_cache) ARE at the archive root (written by fission-deploy.py _build_archive via
fl.layer_modules), so 'from program_store import ...' WORKS. That's why SOME tools/data work
and others don't.

EVIDENCE CHAIN:
  Frontend /analysis page -> backend /api/analytics/analysis/sections/:key -> 304 (stale cache)
  OR cache-miss worker -> invokeLambda('analysis_section') -> fission router /analysis_section
  -> pl-fn-analysis-section cold-starts -> main.main -> importlib analysis_section.handler
  -> handler -> core.analysis_section -> 'from analytics import ...' -> ModuleNotFoundError
  -> returns {statusCode:500, body:{"error":"No module named 'analytics'"}}
  -> backend async worker fails silently (logs 502 @5895ms on one request) -> section stays
  'missing' in DynamoDB -> frontend shows no data for missing sections (peaking/alerts/ai/eval)
  while showing STALE 304 data for the 3 sections cached before the package broke.

### STEP 9 - FULL LIST OF AFFECTED FILES (same bug class)
Per-tool sibling absolute imports that MUST become relative (from .X import):
analytics (sibling, not a layer):
  lambda/regenerate_analysis/core.py:90
  lambda/regenerate_analysis/export.py:1834
  lambda/analysis_section/core.py:103
  lambda/export_program_markdown/core.py:100
  lambda/export_program_markdown/export.py:1834
  lambda/export_program_markdown/prompt_context.py:11, 1129
  lambda/get_analysis_markdown/core.py:89
  lambda/get_analysis_markdown/export.py:1834
  lambda/health_complete_competition/core.py:115, 181
  lambda/health_snapshot_competition_projection/core.py:114
  lambda/block_program_evaluation/program_evaluation_ai.py:18
  lambda/export_program_history/core.py:101
  lambda/export_program_history/export.py:1834
  lambda/export_program_history/prompt_context.py:11, 1129
  lambda/program_evaluation/program_evaluation_ai.py:18
  lambda/weekly_analysis/core.py:117
config (sibling, not a layer):
  lambda/regenerate_analysis/core.py:151
  lambda/analysis_section/core.py:104
  lambda/export_program_markdown/core.py:152, 181
  lambda/get_analysis_markdown/core.py:150, 260
  lambda/export_program_history/core.py:153, 182, 321
  lambda/correlation_analysis/handler.py:43
  lambda/program_evaluation/handler.py:54
  lambda/weekly_analysis/core.py:139
export (sibling):
  lambda/regenerate_analysis/core.py:149
  lambda/export_program_markdown/core.py:289
  lambda/get_analysis_markdown/core.py:148, 258
  lambda/export_program_history/core.py:297
prompt_context (sibling):
  lambda/export_program_markdown/core.py:182
  lambda/block_program_evaluation/program_evaluation_ai.py:20
  lambda/export_program_history/core.py:183
  lambda/correlation_analysis/correlation_ai.py:218
  lambda/program_evaluation/program_evaluation_ai.py:20
  lambda/block_correlation_analysis/correlation_ai.py:218
correlation_ai (sibling):
  lambda/correlation_analysis/handler.py:44
  lambda/block_correlation_analysis/handler.py:19
program_store (LAYER -> resolves OK, NO change needed) — listed only to document why it works.

NOTE: program_store import works because it is a layer module at archive root.
      The bug is ONLY for sibling .py files inside the per-tool folder.
      ALSO must check the *_ai.py / template_apply.py / training_weeks.py / e1rm_backfill_ai.py /
      muscle_group_ai.py / glossary_text_ai.py / budget_*_ai.py sibling imports (same pattern).

### STEP 10 - SECONDARY ISSUES NOTED (not chasing, per instructions)
- Fission executor logs: 'error creating deployment ... failed to create deployment within
  the timeout window of 120 seconds' for pl-fn-health-get-federation-library (recurring every
  ~6min). This is a SEPARATE fission reconciler issue for ONE function, not the analysis bug.
  Noted, not fixing now.
- /metrics returns 404 on the backend (Prometheus scraping nothing). Cosmetic. Noted.
- INTERNAL_API_TOKEN empty in backend env (no auth between backend and fission). Security note,
  not the cause of no-data. Noted.
- Stale 304 cache: overview/fatigue_readiness/workload show 'complete' from a pre-break build.
  After the import fix + redeploy, the regenerate endpoint must be hit to repopulate.

### STEP 11 - WHY THE SYMPTOMS MATCH
- 'No data on analysis/dashboard': the sections that were never cached (peaking, alerts,
  ai_correlation, program_evaluation) return status 'missing' -> frontend renders nothing.
- The 3 sections that DO show are stale ETag-304 cached values from before the package broke.
- Intermittent 502s = cold-start of a broken function timing out / returning 500.
- It is NOT: frontend timing out, CORS, gateway routing, backend-fission connectivity,
  or fission not firing. Fission fires fine; the function code itself is broken at import time.

## FIX PLAN
1. Convert all per-tool sibling absolute imports to RELATIVE imports (from .X import ...) in
   every affected file listed in STEP 9 (and the other *_ai.py / template_apply.py / etc.
   siblings). This makes them resolve as sub-modules of the tool package in the archive.
2. Rebuild + redeploy the affected fission packages (fission-deploy.py -> terraform apply,
   or the reset-fission-packages.sh script).
3. Trigger regeneration: POST /api/analytics/analysis/regenerate (or the per-section queue)
   so the now-working functions repopulate the 'missing' sections in DynamoDB.
4. Verify by re-hitting fission router /analysis_section directly (expect 200 + JSON payload,
   not the 500 'No module named analytics').
### STEP 12 - CORRECTED: tested a SPREAD of fission functions live (done)
Previous over-generalisation was wrong. Fission is NOT entirely broken. Tested live:
- analysis_section        -> 500 "No module named 'analytics'"        (BROKEN, sibling-import bug)
- weekly_analysis         -> 500 "No module named 'config'"            (BROKEN, sibling-import bug)
- budget_advisor         -> 500 "No module named 'budget_advisor_ai'"  (BROKEN, sibling-import bug)
- health_get_sessions_range -> 200 REAL DATA (sessions returned)     (WORKS — uses layer program_store + relative .core)
- health_get_program     -> 30s exec timeout (cold start; not fully confirmed but layer-only imports)
- powerlifting_filter_categories -> 200 but body="Dataset missing... openpowerlifting-*.csv" (RUNS, NO DATA)
- powerlifting_ranking_percentile -> 200 but body="Dataset missing... openpowerlifting-*.csv" (RUNS, NO DATA)

### STEP 13 - ARCHITECTURE IS HYBRID (answers 'why budget/sessions work, analytics/percentile dont')
The portal backend has TWO data paths:
  (A) Backend -> DynamoDB DIRECTLY via controllers (budgetController, sessionController, etc.)
  (B) Backend -> FISSION via invokeLambda / invokeToolDirect

Which pages use which:
  Budget page (list/config/items/photos): path (A) - backend DynamoDB direct.
     budgetRouter -> budgetController -> DynamoDB. This is why budget DATA shows.
     Only the budget AI advisor (POST /budget/ai-analysis -> invokeLambda('budget_advisor'))
     uses fission, and THAT is broken (No module named 'budget_advisor_ai'). So budget
     list works, budget AI advice is broken.
  Sessions page (list/save/exercises): path (A) - backend DynamoDB direct via sessionController.
     This is why sessions show. (Coach autoreg uses invokeSpecialistJson -> agent API, not fission.)
  Stats/Percentile card: path (B) - statsRouter -> invokeLambda('powerlifting_ranking_percentile').
     Function RUNS (imports OK) but returns 'Dataset missing' -> NO OpenPowerlifting CSV in pod.
     SANDBOX_PATH defaults to /tmp/sandbox; the stats fns glob /tmp/sandbox/openpowerlifting-*.csv.
     Pod has no such file. The pl-pandas layer README says it should read from S3 POWERLIFTING_S3_BUCKET.
  Analysis page: path (B) - analyticsRouter -> invokeLambda('analysis_section'/'weekly_analysis').
     BROKEN by sibling-import bug.

### STEP 14 - DESIGN NOT VIOLATED
The design (all features doable from Discord + portal; fission exposes as MCP; agent consumes)
is still the target. Fission IS used by the portal for: stats (categories/analyze/ranking_percentile),
analysis (sections/manifest/regenerate/blocks/comparison/correlation), competitions snapshot,
program cache invalidation, markdown export. These are exactly the features that are broken.
The DynamoDB-direct pages (budget list, sessions) are a DIFFERENT access path, not a violation.

### STEP 15 - TWO DISTINCT ROOT CAUSES (not one)
ROOT CAUSE A (analysis + weekly_analysis + budget_advisor + any tool importing a sibling
  analytics/config/export/prompt_context/correlation_ai/*_ai.py): ABSOLUTE imports of
  per-tool sibling modules. Fix: convert to RELATIVE imports (from .X import). No code
  duplication, no new layers - the file is already in the package, just import it correctly.
  program_store etc. stay absolute (they are layer modules at archive root and resolve).
ROOT CAUSE B (percentile/stats card): stats fns RUN but the OpenPowerlifting CSV dataset is
  not present at /tmp/sandbox/openpowerlifting-*.csv in the fission pod. This is a DATA/SEED
  issue (dataset not downloaded/mounted into the stats pods), NOT an import bug.
  Per pl-pandas README the dataset should come from S3 POWERLIFTING_S3_BUCKET. Need to verify
  whether the stats pod is meant to download it at cold start or it should be mounted.



### STEP 16 - OPL DATASET INVESTIGATION (parallel track)

**CONCLUSION (ROOT CAUSE B fully resolved):** The stats functions are NOT wired to
download the OpenPowerlifting CSV at all - neither in code nor via pod env/mount.
The README claim that they read the dataset from S3 (POWERLIFTING_S3_BUCKET) is
aspirational documentation that was NEVER implemented in the fission port. The CSV
is expected to be pre-materialised at /tmp/sandbox/openpowerlifting-*.csv, but there
is no mechanism anywhere (no boto3 download in core.py, no initContainer, no
sidecar, no ConfigMap/PVC mount, no CronJob, no fission secret carrying the bucket
name) that ever puts it there. The pod cold-starts with an absent /tmp/sandbox and
the background warm_cache() thread immediately FileNotFoundError's.

#### 2. fission-deploy.py wired an env var that (a) never reaches the pod and (b) nothing reads
- lambda/fission-deploy.py:41-43 defines STATS_ENV = [(POWERLIFTING_S3_BUCKET,
  ${var.powerlifting_s3_bucket})] and at line 267 conditionally injects
  [{ name = POWERLIFTING_S3_BUCKET, value = var.powerlifting_s3_bucket }]
  into podspec.containers[].env when s3_read is true.
- BUT the actually-applied terraform terraform/k8s-fission-powerlifting.tf:171-195
  explicitly DROPS this: the podspec there contains only name/image/imagePullPolicy/resources
  and a code comment (lines 174-178) states:
  > Function podspec (env, volumes, volumeMounts, envFrom) is NOT merged into
  >  the runtime deployment by the newdeploy executor.
  So the env/envFrom block from fission-deploy.py was intentionally removed
  because Fission v1.26 newdeploy ignores podspec env. The stats tools podspec in
  the live cluster has NO env block at all (verified below).
- Net effect: POWERLIFTING_S3_BUCKET is NEVER set on any pod, AND even if it were,
  core.py never imports boto3 to use it.

#### 1. What the code actually does (the 3 stats core.py files)
All three are byte-for-byte identical in the loader section:
- lambda/powerlifting_ranking_percentile/core.py:29-35
- lambda/analyze_powerlifting_stats/core.py:28-34
- lambda/powerlifting_filter_categories/core.py:27-33

    def _parse_csvs() -> pd.DataFrame:
        pattern = os.path.join(SANDBOX_PATH, "openpowerlifting-*.csv")
        csv_files = glob.glob(pattern)
        if not csv_files:
            raise FileNotFoundError(f"No powerlifting datasets found in sandbox matching: {pattern}")

- config.py:3 (each tool): SANDBOX_PATH = os.getenv("SANDBOX_PATH", "/tmp/sandbox")
- core.py imports ONLY os, glob, logging, threading, pandas, numpy and .config.
  **There is NO import boto3, NO download_file, NO get_object, NO S3 client
  anywhere in the stats tool folders.** Verified by:
  grep -rn 'download|get_object|download_file|list_objects|boto3|s3' over all
  three tool dirs -> only hits are the glob pattern + resources.yaml s3_read: true
  + layer list. Zero lines read from S3.
- warm_cache() is called at module import (core.py last line), spawning a
  daemon thread that runs _parse_csvs(). With no CSV present this sets
  _df_error = No powerlifting datasets... and handler.py returns
  ERROR: Dataset missing. {pattern}.
- handler.py:12-13 maps FileNotFoundError -> exactly the observed error string.

So the function is a pure local-filesystem reader. The pl_boto3 layer +
s3_read: true resources.yaml flag + POWERLIFTING_S3_BUCKET env wiring in
fission-deploy.py are ALL dead/unused for the stats path: nothing in core.py or
fission_entry.py ever calls boto3 to fetch the dataset.

#### 3. Live cluster proof (warm pod, post-trigger)
Triggered the function: POST http://10.43.228.243/powerlifting_ranking_percentile
(body squat_kg:100) -> HTTP 200 body:
{body:ERROR: Dataset missing. No powerlifting datasets found in sandbox matching: /tmp/sandbox/openpowerlifting-*.csv, statusCode:200}
This scaled up pod newdeploy-pl-fn-powerliftin-if-portals-88d7-5f05e7a7ddaa-7gcxtx
(container pl-fission-tools). Exec results:
- env | grep -iE 'S3|SANDBOX|POWERLIFTING|AWS|IF_TOOL' -> NONE. The only
  POWERLIFTING_* vars are auto-injected Kubernetes service vars
  (POWERLIFTING_APP_BACKEND_SERVICE_HOST etc.). There is NO POWERLIFTING_S3_BUCKET,
  NO SANDBOX_PATH, NO AWS_REGION/AWS_SHARED_CREDENTIALS_FILE, NO IF_TOOL_NAME.
  (Note: fission_entry.py is supposed to materialise /secrets keys into os.environ, but
  the secret keys present are only INTERNAL_API_TOKEN [empty] and OPENROUTER_API_KEY +
  the AWS credential FILES; there is no S3 bucket key in any secret to materialise.)
- ls -la /tmp/sandbox/ -> ls: /tmp/sandbox/: No such file or directory (dir absent).
- find / -name openpowerlifting-*.csv -> empty (no CSV anywhere in the pod fs).
- ls -laR /secrets/ -> secrets ARE mounted:
  /secrets/if-portals/pl-aws-credentials/{config,credentials} (valid AWS IAM creds
  for acct 429310424269:user/admin, ca-central-1) and
  /secrets/if-portals/pl-fission-secrets/{INTERNAL_API_TOKEN(0 bytes),OPENROUTER_API_KEY}.
  So AWS credentials needed to read the S3 bucket ARE delivered to the pod - they are
  simply never consumed by anything, because core.py has no boto3 code and
  fission_entry.py only sets AWS_SHARED_CREDENTIALS_FILE (line 45) but no stats
  module ever imports boto3 to use it.

Deployment pod-template env (kubectl get deploy ... -o jsonpath containers[*].env):
  runtime container pl-fission-tools env = [{name:RESOURCE_VERSION_COUNT,
  value:513960302}] only. No POWERLIFTING_S3_BUCKET, no SANDBOX_PATH, no envFrom.
  (The fetcher sidecar has only OTEL/FISSION_INTERNAL_AUTH env.)

#### 4. The fission-deploy.py env wiring is doubly-dead
- Dead reason #1 (cluster side): Fission newdeploy does not merge podspec env -> the
  generated terraform already removed env/envFrom from the podspec (k8s-fission-
  powerlifting.tf:183-195 has no env key). The fission_entry.py workaround only
  materialises /secrets keys, and POWERLIFTING_S3_BUCKET is not a secret key.
- Dead reason #2 (code side): even with the env var present, core.py has no boto3
  import / S3 download logic, so it could not act on the bucket name.

#### 5. No seed/download mechanism exists anywhere in the repo
Searched the whole powerlifting-app tree (excluding node_modules/.zip):
- grep -rln openpowerlifting -> only docs/READMEs, the 3 core.py glob lines, the
  resources.yaml descriptions, variables.tf (bucket name), and the frontend .tsx
  pages. NO script that downloads/seeds the CSV.
- find -iname '*opl*' -o -iname '*download*' -o -iname '*seed*' -o -iname '*sync*'
  -> master-sync (a DynamoDB streams replicator for competitions, unrelated),
  VideoPlayer*.tsx, node_modules. No OPL seeder.
- find -iname '*.sh' | xargs grep -l 'openpowerlifting|S3|sandbox|download' -> only
  pl-boto3/build.sh (builds the boto3 layer zip; not a dataset seeder).
- Terraform (terraform/*.tf): variables.tf:36-39 defines
  powerlifting_s3_bucket default powerlifting-openpowerlifting-dataset, but
  NO aws_s3_bucket resource is created for it and NO Lambda/job reads it.
  The only S3 buckets actually created are budget_media (budget.tf) and
  session_videos (videos.tf). The powerlifting_s3_bucket variable is consumed
  ONLY by fission-deploy.py's (now-stripped) podspec env injection. There is no
  terraform resource named for the OPL bucket, no lifecycle, no objects, no sync job.
- master-sync/handler.py is a DynamoDB-streams replicator (COMP_MASTER->COMP_USER),
  unrelated to the OPL CSV.
- No CronJob / Job / initContainer / sidecar in any of the fission Function specs or
  the Environment spec (kubectl -n if-portals get environment pl-fission-tools -o yaml
  -> only builder/runtime images + resources + terminationGracePeriod; no mounts).

#### 6. Intended mechanism (from docs) vs reality
- pl-pandas README (lambda/layers/pl-pandas/README.md:14):
  These lambdas read the OpenPowerlifting CSV dataset from S3
  (POWERLIFTING_S3_BUCKET) and compute ... which require pandas + numpy.
- HEALTH_LAMBDA_MIGRATION_PLAN.md:137-142 Stream B - OpenPowerlifting stats
  (pandas/numpy layer + S3 dataset warm-start) lists the 3 handlers as done but
  line 142 [ ] Warm-start strategy for stats lambdas ... document in handler README
  is UNCHECKED. There is no warm-start/dataset-fetch implementation - it was a
  planned TODO that was never built.
- The original AWS-Lambda design assumed the CSV would be ETL'd into the S3 bucket
  powerlifting-openpowerlifting-dataset and a warm-start layer/initializer would
  download it to /tmp/sandbox. In the fission port, the S3 bucket was never created
  and the warm-start fetch code was never written; the functions were copied
  verbatim as pure local-glob readers with the S3 step silently dropped.

#### 7. Exact break + concrete fix (investigation only - NOT applied)
BREAK: Two-part:
  (i) No code path downloads the CSV. core.py only globs /tmp/sandbox; it never
       calls boto3/S3, so /tmp/sandbox is never populated.
  (ii) The POWERLIFTING_S3_BUCKET env var that docs imply drives a download is not
       delivered to the pod (Fission newdeploy ignores podspec env; the generated
       terraform stripped it) and, even if delivered, is unread by the code.

MISSING PIECES (one or more must be supplied):
  A. An S3 bucket actually containing openpowerlifting-*.csv. terraform/variables.tf
     names powerlifting-openpowerlifting-dataset but no aws_s3_bucket resource
     exists for it and no objects are uploaded. Either create the bucket+objects in
     terraform, OR point at an existing bucket, OR place the CSV another way.
  B. A download step in the stats code. The 3 core.py files need a cold-start S3
     fetch (boto3 client.list_objects_v2 on POWERLIFTING_S3_BUCKET, download_file
     into SANDBOX_PATH) before _parse_csvs(), OR the dataset must be mounted.
  C. The bucket name must reach the pod. Because Fission newdeploy ignores podspec
     env/envFrom (per k8s-fission-powerlifting.tf:174-178 comment), the bucket name
     must be delivered via the Fission-native secrets mechanism (add a key e.g.
     POWERLIFTING_S3_BUCKET to the pl-fission-secrets Secret, which fission_entry.py
     already materialises into os.environ at lines 29-37), NOT via podspec env.
     (AWS creds are already correctly delivered this way via pl-aws-credentials and
     fission_entry.py lines 41-48 set AWS_SHARED_CREDENTIALS_FILE/AWS_REGION.)

CONCRETE FIX (sketch, not applied):
  1. terraform: add aws_s3_bucket (or data source) for the OPL dataset + upload the
     openpowerlifting-*.csv objects (e.g. via a terraform aws_s3_object or an ETL
     job outside terraform).
  2. Add POWERLIFTING_S3_BUCKET=bucket as a key in the pl-fission-secrets Secret
     (so it is mounted at /secrets/if-portals/pl-fission-secrets/POWERLIFTING_S3_BUCKET
     and materialised into os.environ by fission_entry.py:37). Do NOT rely on podspec env.
  3. Add a download step to the stats core.py _background_load() (or a shared loader
     used by all 3): before globbing, if no CSV exists at SANDBOX_PATH, use boto3
     (creds already in env via AWS_SHARED_CREDENTIALS_FILE) to list+download
     openpowerlifting-*.csv from POWERLIFTING_S3_BUCKET into SANDBOX_PATH, then glob.
     Alternatively, mount the CSV via a shared PVC/ConfigMap/initContainer if a
     download-per-cold-start is undesirable for the ~100MB+ dataset.
  The pl_boto3 layer is already attached to all 3 stats tools (resources.yaml:2), so
  boto3 is importable; only the download code is missing.

DEAD-ENDS NOTED:
- POWERLIFTING_S3_BUCKET search in the codebase returned nothing via the scoped
  search tool (37-file limit); had to fall back to grep -r to find it in
  fission-deploy.py:42,267 and variables.tf:36.
- The fission Environment pl-fission-tools lives in namespace if-portals (not
  fission); initial kubectl -n fission get environment 404'd.
- INTERNAL_API_TOKEN in pl-fission-secrets is empty (0 bytes) - unrelated to this
  bug but means the X-Internal-Token gate in fission_entry.py:69-77 is disabled
  (_EXPECTED_TOKEN empty -> _check_token returns early). Not the cause of the
  dataset error (the function reached the handler and returned the dataset error).
### STEP 17 - IMPORT BUG FIX APPLIED (done)
Converted ALL per-tool sibling absolute imports to RELATIVE imports across 37 files
(63 line changes). No code duplication, no new layers - the files were already in each
package; the bug was only the import style. Layer-module imports (program_store, programs,
sessions, glossary, templates, imports, federation, analysis_cache) left as absolute
(they are at archive root and resolve).
Verification:
- grep for remaining absolute sibling imports: NONE LEFT.
- Python ast.parse on all 37 changed files: ALL SYNTAX-OK, zero errors.
- No layer file references the sibling modules (so no cross-dependency break).
- No __main__ entry paths in tool files (relative imports safe under importlib import).
Files changed (sample): analysis_section/core.py:103-104 now 'from .analytics'/'from .config';
weekly_analysis/core.py, regenerate_analysis/core.py, export_program_markdown/*,
get_analysis_markdown/*, budget_advisor/handler.py, correlation_analysis/*,
program_evaluation/*, block_*/*, glossary_*/handler.py, muscle_group_estimate/handler.py,
fatigue_profile_estimate/handler.py, template_apply*/core.py+template_apply.py, etc.
NEXT: rebuild fission packages + redeploy affected functions, then trigger regeneration.
### STEP 18 - REBUILD + DEPLOY (in progress)
- fission-deploy.py rebuild DONE. Verified terraform/fission-build/analysis_section.zip now contains
  'from .analytics import' (relative). Terraform pl_packages reads from this exact dir
  (k8s-fission-powerlifting.tf:138 filebase64(pl_build_dir/key.zip), pl_build_dir =
  utils/powerlifting-app/terraform/fission-build). So the rebuilt zips are the deploy source.
- Current packages: 96 succeeded, 1 failed (analyze-rpe-drift), 1 none. All built from OLD source.
- Plan: delete only the packages whose tools I changed (targeted), re-apply from new zips so
  buildermgr rebuilds them. Avoid nuking all 98 (slow, builder collision risk).
### STEP 19 - IMPORT FIX VERIFIED WORKING (done)
budget_advisor -> HTTP 200 real JSON (was 'No module named budget_advisor_ai'). FIXED.
All 23 affected packages rebuilt succeeded. analysis_section now PASSES the analytics import
but hits a NEW (pre-existing, masked) error: 'No module named scipy'.
### STEP 20 - SECONDARY: scipy not installed in builds (note, fixing)
8 tools list scipy in requirements.txt: analysis_section, weekly_analysis, regenerate_analysis,
export_program_history, export_program_markdown, get_analysis_markdown, health_complete_competition,
health_snapshot_competition_projection. The fission_build.sh pip install has '|| true' guards that
swallow install failures, so builds 'succeed' but scipy is absent. scipy not in pl-pandas layer.
Likely cause: scipy C-extension build fails on the fission python-env (Python 3.13) - checking.
### STEP 21 - SCIPY ROOT CAUSE FOUND + FIXED
ROOT CAUSE of scipy-missing: fission-deploy.py _build_archive writes requirements.txt from
fl.requirements_for() which ONLY merged LAYER_PIP_REQS + EXTRA_TOOL_REQS - it NEVER read the
tool requirements.txt (build filter line 71 excludes .txt). So scipy (in 8 tools requirements.txt)
was silently dropped. FIX: patched fission_layers.py requirements_for() to read each tool requirements.txt
and merge (dedup). Verified analysis_section.zip now contains scipy. NEXT: redeploy 8 scipy packages.
### STEP 22 - SCIPY DEPLOY STATUS
- analysis_section, weekly_analysis, regenerate_analysis: rebuilt succeeded WITH scipy.
- export_program_markdown, get_analysis_markdown, health_complete_competition: pip install SUCCEEDED but build marked failed due to fission storagesvc connection refused during upload (transient). Retrying.
- analysis_section pod stuck Pending: 0/1 nodes available Insufficient cpu (cluster node CPU exhausted - scipy pods are heavier). Resource issue, not code.
### STEP 23 - STORAGESVC OOM FIX
storagesvc was OOMKilled (1Gi limit) during large scipy+numpy zip uploads. Patched deploy to 2Gi limit/1Gi request. New pod Running stable. Now retrying 3 failed package builds.
### STEP 24 - ALL SCIPY PACKAGES BUILT + ENV RESOURCES LOWERED
All 8 scipy packages now succeeded (storagesvc OOM fixed at 2Gi). Fission Environment CPU lowered
from 4000m request to 500m request (was blocking pod scheduling at 96pct node CPU).
Deleted analysis_section deployment so Fission recreates with sane resources.
### STEP 25 - ANALYSIS_SECTION FULLY WORKING (VERIFIED LIVE)
DIRECT fission call with args wrapper returned HTTP 200 with REAL analysis JSON (week 20, sessions, phases, exercises, RPE).
Fix chain verified: 1) relative imports 2) scipy via requirements_for 3) env CPU 4000m->500m 4) storagesvc OOM 1Gi->2Gi.
NOTE payload must be wrapped in args key (handler does event.get(args,event)).

### TODO (deferred - fission infra)
- fetcher sidecar OOMs at 1Gi when loading large scipy archives (env pod restart x5). Need to bump fetcher memory via fission poolmgr config or helm. Blocks health_snapshot_competition_projection build upload intermittently.
- analysis_section DIRECT fission call works (verified 200 + real data). Backend serves stale cache (payload.error cached as complete). Need cache invalidation to propagate fresh result.
- 7/8 scipy packages built OK; 1 (HS) intermittent upload failure due to env pod OOM churn.

### ARCHITECTURE PROBLEM (user raised)
Backend does DIRECT DynamoDB via controllers (budgetController, sessionController, etc) instead of routing to fission. Design intent: backend = router + auth only; functionality in fission functions. Need to migrate direct-DynamoDB routes to call fission functions instead.
