# Unrelated findings retained for later

- Terraform validates, but local terraform.tfvars supplies four undeclared variables (including terminal_image and dynamodb_powerlifting_users_table). Review these independently of the rewrite; do not broaden the targeted deployment to Authentik/Postgres changes.
- The retained analytics formatter uses datetime.utcnow(), which emits Python 3.12 deprecation warnings. Its report behavior is covered by rewrite tests; modernizing date handling is separate work.
- The unused backend controller onboarding test still contains historical Fission setup. It is outside the backend's active test:forwarding script and has no runtime caller; migrate or retire it separately.

## Existing k3s controller reconciliation warnings

During the final API rollout, k3s logs repeatedly reported its bundled local-storage manifest trying to change the existing local-path StorageClass binding mode (immutable), plus stale Rancher CAPI owner references with an unavailable API mapping. The replacement workloads are healthy; these unrelated cluster issues were not changed. Worker login manifests explicitly use the existing local-path-wait class (WaitForFirstConsumer), matching the verified main login PVC and permitting correct laptop placement.

- 2026-09-14 read-only native-rollout baseline: old Pod `if-agent-api-fc6fbd5d8-fktk5` remains `ContainerStatusUnknown`; current Pod `if-agent-api-6b8887698c-nkr8c` is healthy. No events remained for the old Pod. Left unchanged because stale Pod cleanup is outside this implementation and targets the protected API.

- 2026-09-14 live portal baseline: existing pino HTTP request logs include Cookie headers. Redact authentication headers in a separate change; do not expose raw portal logs during diagnostics.

## Powerlifting block completion workflow

The user reported that they cannot complete a training Block and start the next. The frontend only exposes template application with a `new_block` strategy; first-block setup rejects an existing Program. `lambda/pod_templates/handlers/template_apply_confirm/core.py` replaces the session list in a new Program version and ignores its `target` argument. It does not name or complete the prior current Block inside the Program. A dedicated transition must preserve existing Sessions, phases, notes and historical windows. No operator training records were changed while investigating this report. Follow-up is in `todo.md`.

- 2026-09-14 final API startup: the optional Alpha Vantage MCP process raises `ValueError: ALPHAVANTAGE_API_KEY environment variable required`. The API completes startup and the native conversation canary passes. Missing integration credentials were left outside this deployment scope.
