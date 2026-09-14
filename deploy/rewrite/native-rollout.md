# Native conversation rollout — 2026-09-14

The operator explicitly approved this rollout. The native API/host, sixteen services and portal frontend/backend are deployed and passed live acceptance. Eleven report requests arrived during image publication; all completed under the old runtime before the API/worker switch. The disconnected legacy source was then removed; both cleanup images are deployed and verified. All 20 affected Deployments are ready. Final image references are in [native-published-images.json](../../docs/contracts/native-published-images.json). See [native-conversations.md](../../docs/contracts/native-conversations.md) for the contract and actual versus offline evidence.

## Reviewed protected scope

The saved review plan is `/tmp/if-native-api-review.tfplan`; its sanitized actions are `/tmp/if-native-api-actions.json`. Plan/state JSON and rollback snapshots remain private. The plan uses `deploy/rewrite/models.tfvars.json` so existing model configuration is preserved.

| Resource | Change |
| --- | --- |
| `kubernetes_config_map.if_agent_api_config` | Add the host Service URL and operator Discord ID `400750817382236160`. |
| `kubernetes_deployment.if_agent_api` | Update the source checksum and recreate the API using the published image. |
| `kubernetes_secret.ecr_registry` | Refresh existing registry credentials. |
| `null_resource.packer_build_main_api` | Replace the local build trigger and publish the API image. |
| `null_resource.rollout_restart_main_api` | Replace the local rollout-status trigger. |

There are no AWS resource deletions, database/volume removals, Authentik/Postgres changes, or model ConfigMap changes in this plan. The two replacements are Terraform local execution triggers. Do not use an untargeted apply or the broader historical `apply-api.sh` for this scope.

Approval for this main-node rollout is recorded in the conversation. For the approved rollout, publish first, then review/apply the remaining targeted rollout. A fresh plan is required after the build updates state; do not apply the old combined review plan afterward.

```bash
terraform -chdir=terraform apply -input=false \
  -var-file=../deploy/rewrite/models.tfvars.json \
  -target=null_resource.packer_build_main_api

terraform -chdir=terraform plan -input=false \
  -var-file=../deploy/rewrite/models.tfvars.json \
  -target=kubernetes_config_map.if_agent_api_config \
  -target=kubernetes_secret.ecr_registry \
  -target=kubernetes_deployment.if_agent_api \
  -target=null_resource.rollout_restart_main_api \
  -out=/tmp/if-native-api-rollout.tfplan

terraform -chdir=terraform apply -input=false \
  -var-file=../deploy/rewrite/models.tfvars.json \
  -target=kubernetes_config_map.if_agent_api_config \
  -target=kubernetes_secret.ecr_registry \
  -target=kubernetes_deployment.if_agent_api \
  -target=null_resource.rollout_restart_main_api
```

## Coordinated switch

The API, host and domain callers must switch in one maintenance window because their execution protocols changed. Before stopping the old worker, verify its SQLite queue and active implementation tasks are empty, and let the delivery outbox drain. Both accepted-work lists were empty during the final read-only check; check again immediately before switching. Do not discard an accepted job to make the check pass.

1. Retain the rollback images below locally, privately snapshot the live configuration and back up the existing SQLite database with SQLite's backup API. Preserve existing volumes and historical DynamoDB records. The baseline configuration snapshots are in `/tmp/if-native-rollback-20260914/`.
2. Build/publish the API with the first targeted command. Publish the locally verified worker, shared services and Analytics images into the existing repositories using unique `native-20260914-*` tags. Resolve their ECR digests and replace the three pins in `deploy/kustomization.yaml`. Main-node and prepared laptop manifests pin the published native host image. Laptop manifests were updated only; keep the laptop undeployed.
3. Build the Powerlifting gateway backend and frontend using their existing `utils/powerlifting-app/docker/powerlifting-{backend,frontend}.pkr.hcl` templates. The required workspace build/typechecks passed. The portal release uses thin overlays of the preceding Packer images, preserving their Node runtime and dependencies while copying the verified compiled outputs; Dockerfiles are in `/tmp/if-native-{backend,frontend}.Dockerfile`. Use `/api` for both frontend API variables and the existing CloudFront media origin. Keep these separate from root Terraform portal builds.
4. Recheck accepted work and resources. Stop the idle old worker with its narrowly named Deployment. Apply the reviewed API targets, then `kubectl apply -k deploy` using the newly pinned digests. This creates the host Service and state PVC and leaves its Deployment at zero replicas. Before accepting new work, inspect the retained legacy database again for any input accepted during the stop. If any appeared, restore the old API/worker long enough to drain it; do not leave it stranded. Activate exactly one worker replica. The main-node selector remains `sirsimpalot-g5-5000`; limits remain 2 CPU / 3 GiB RAM.
5. Update only `powerlifting-app-backend` and `powerlifting-app-frontend` to their new immutable image digests. The sixteen services and Analytics sidecar come from `deploy/rewrite/powerlifting.yaml`. Keep the existing authenticated gateway and credentials.
6. Wait for all affected Deployments and run the deployed acceptance below. Retain the rollback window until acceptance is complete.

Worker/domain build commands already verified locally:

```bash
docker build -f docker/codex-worker.Dockerfile -t if-codex-worker:native .
docker build -f utils/powerlifting-app/services/Dockerfile \
  -t if-powerlifting-services:native utils/powerlifting-app
docker build -f utils/powerlifting-app/services/analytics.Dockerfile \
  -t if-powerlifting-analytics:native utils/powerlifting-app
```

The production API Packer build/push and final targeted rollout passed. Image content hashes were compared with source separately from import smoke checks. API smoke checks mounted the existing Specialist directory, matching deployment. The two superseded local API build candidates were removed after verification; all six pinned local rollback images remain.

The host requires both `if-codex-login` (1 GiB at `/var/lib/codex`) and new `if-codex-state` (5 GiB at `/work`). The first retains subscription authentication and native thread state; the second retains `host/turns.sqlite3` and Conversation workspaces. `/work` must not revert to `emptyDir`. `INTERNAL_API_TOKEN` comes from the existing secret; `IF_API_URL=http://if-agent-api:8000` and `IF_CODEX_HOST_URL=http://if-codex-worker:8001` provide the two-way bridge. No paid API credentials are required.

## Deployed acceptance and cleanup

Record these independently from local canaries: a real authorized Discord input/edit and outbox recovery; two concurrent Conversations and a third busy response; status/cancel while full; host Pod restart with completed-response recovery and interrupted work marked uncertain; refreshed scoped Directives; a report reference through cache completion; a template import through review/apply; authenticated browser status/export reads. Do not test mutations against existing Athlete records. Discord canaries require an explicitly authorized destination before sending.

```bash
kubectl top nodes
kubectl get pods,pvc -n if-portals -o wide
kubectl logs -n if-portals deployment/if-agent-api --tail=80
kubectl logs -n if-portals deployment/if-codex-worker --tail=80
kubectl exec -i -n if-portals deployment/pl-calculations -- python - \
  < scripts/test_powerlifting_services_live.py
```

After deployed acceptance, the unused classifier/planner, implementation-task workers, queue polling/lease APIs, obsolete execution helpers and their old tests/configuration were removed. Historical job lookup/storage and outbox machinery remain. The retired source is privately backed up in `/tmp/if-native-retired-source-20260914/`. All 39 current IF tests pass after cleanup.

## Rollback

The verified pre-switch images are below, all in `429310424269.dkr.ecr.ca-central-1.amazonaws.com`. Retain them before publishing because existing ECR lifecycle policies limit history.

| Component | Repository and digest |
| --- | --- |
| API | `if-agent-api@sha256:d5bd14ff1e1dd67d87ea52cc6347697afd8fc5795757245d430c260cf75f4ffb` |
| Old worker | `if-agent-api@sha256:854cdab74660235823c651a8404569d99211704fa48dff3c848bde03be592879` |
| Sixteen services | `if-powerlifting-fns@sha256:7240ef2dfafa7da711fb6cd955058b9ed14a174f020f649037de2cf2edd85358` |
| Analytics sidecar | `if-powerlifting-app-backend@sha256:86392cf5556d31f063b83a73cb493cf4c14a1e7cff2d969b2bf70b2a910a502e` |
| Gateway backend | `if-powerlifting-app-backend@sha256:1dafe860d461f573fc1255dc273a0a08657936ed987f945d803ab5fa677e303e` |
| Frontend | `if-powerlifting-app-frontend@sha256:77ca2a7676531ce8157707610479ddeb11eae3761f3a14950736e9741fc8050d` |

Drain native turns first. Restore the previous API image/configuration and worker/domain/portal digests together; restore the old worker Deployment spec from the private snapshot. A protected API rollback also requires operator authorization. Preserve both new PVCs and all old databases. Native turn records cannot become legacy queued jobs. Inspect uncertain side effects before an explicit retry. Never run a broad apply/delete or replay accepted mutations. Reconcile Terraform through a reviewed targeted plan afterward.

Laptop deployment is intentionally stopped. Its separate state/login requirements, placement commands, rollback and outstanding cross-node checks are in `/tmp/if-laptop-handoff.md` and [deploy/laptop/README.md](../laptop/README.md).
