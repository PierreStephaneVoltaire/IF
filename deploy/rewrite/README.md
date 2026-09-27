# Native conversation deployment status

The operator approved and deployed the native conversation runtime on the main node; real deployed conversation, report, import and restart canaries passed. Follow [native-rollout.md](native-rollout.md) and [the current contract](../../docs/contracts/native-conversations.md). The prior approval, queue topology, temporary workspace and rollback digest below describe the preceding deployment only. Do not use those historical commands for the new host.

---

# Rewrite deployment and operations

The operator approved the reviewed two-stage IF API deployment. The rewrite is running on the main k3s node, with final image/startup checks recorded in [acceptance.md](../../docs/contracts/acceptance.md). The supplied AWS credentials work and the existing localhost kubeconfig is correct. Existing Authentik/Postgres edits remain outside this deployment.

## Current layout

The API keeps Conversations, memory, Directives, channel listeners, the DynamoDB execution/outbox registry, the SQLite job queue and artifacts on the main node. A separate Codex worker uses the existing ChatGPT subscription. It runs one top-level job and at most two native Specialists. Background work queues below user requests. Lost leases and interrupted mutations become uncertain and are never automatically replayed.

Powerlifting has sixteen Services and Deployments, sharing a Python image with one typed operation inventory for HTTP and MCP. Analytics adds its existing Node report/cache implementation as a loopback sidecar. The browser uses the authenticated `/api` gateway. Existing DynamoDB tables, S3 objects and Athlete ownership are retained.

`deploy/kustomization.yaml` pins worker/domain/Analytics images in existing ECR repositories. All new workloads use `ecr-registry`, refreshed by the existing scheduled token job. The worker image lives under a separate immutable digest in the existing `if-agent-api` repository. It is not the API image.

## Inspect and verify

```bash
kubectl get nodes -o wide
kubectl top nodes
kubectl get pods,pvc -n if-portals -o wide
kubectl get events -n if-portals --sort-by=.lastTimestamp
kubectl logs -n if-portals deployment/if-agent-api --tail=80
kubectl logs -n if-portals deployment/if-codex-worker --tail=60
kubectl exec -i -n if-portals deployment/pl-calculations -- python - < scripts/test_powerlifting_services_live.py
```

Keep raw logs, Terraform state/plans, authentication material and credential files private. Test only synthetic mutations and authorized message destinations. The acceptance record distinguishes offline checks, live checks and untested workflows.

## Build and deploy later changes

```bash
docker build -f docker/codex-worker.Dockerfile -t if-codex-worker:rewrite .
docker build -f utils/powerlifting-app/services/Dockerfile -t if-powerlifting-services:rewrite utils/powerlifting-app
docker build -f utils/powerlifting-app/services/analytics.Dockerfile -t if-powerlifting-analytics:rewrite utils/powerlifting-app
```

Publish into the existing repositories and update immutable digests in `deploy/kustomization.yaml` and the laptop manifests. Before applying, let the active worker job finish. The manifests deliberately set replicas to zero so placement/login/readiness can be checked first:

```bash
kubectl apply -k deploy
kubectl scale -n if-portals deployment/if-codex-worker --replicas=1
kubectl rollout status -n if-portals deployment/if-codex-worker --timeout=180s
```

The protected API uses [apply-api.sh](apply-api.sh): publish its image first, then apply only the reviewed API/configuration/registry targets. Its Recreate strategy prevents concurrent writers on the shared persistent volumes. The image checksum triggers one rollout; the historical rollout resource waits for status. A future protected deployment still needs operator approval for its concrete reviewed scope. The current rewrite deployment is already approved; see [api-plan-review.md](api-plan-review.md).

Powerlifting portal builds remain separate from root Terraform portal builds. Use its nested Packer templates from `utils/powerlifting-app/docker/`. The frontend serves media through authorized `/api` GET/HEAD/Range endpoints. The approved media rollout disabled the retained CloudFront distribution and completed cache invalidation. Current image pins and acceptance limits are recorded in [Powerlifting deployment evidence](powerlifting-backlog/deployment-evidence.md). Do not combine root deployment changes with Authentik/Postgres edits or nested AWS Terraform changes.

## Authentication and configuration

The main worker's `if-codex-login` PVC contains the verified subscription login. The worker is pinned to the main node and limited to 2 CPU / 3 GiB RAM, with a 2 GiB temporary workspace. No paid API fallback is enabled. Missing/expired login and subscription limits produce explicit failures.

For a fresh login, adapt `login.yaml` to the published worker digest and `ecr-registry` pull secret, then complete its device-code flow. Use a fresh Pod name for another attempt; retain the PVC. Credentials and device codes never belong in handoff documents.

Yahoo MCP's compatible dependency is pinned and its protocol check passes. Alpha Vantage also has a verified compatible wrapper, but no usable credential was supplied. Configure `alphavantage_api_key` privately in the existing ignored settings and review a separate targeted API-secret/config rollout before using those finance tools. Do not invent a key or silently switch providers.

## Laptop migration

Follow [deploy/laptop/README.md](../laptop/README.md) and `/tmp/if-laptop-handoff.md`. Laptop execution was not deployed or tested in this session. The overlay uses its own `if-codex-login-laptop` PVC and node selector; the main-node local-path login volume cannot move between nodes. Verify cross-node service traffic, subscription login, artifacts, cancellation and available resources before accepting laptop execution.

## Rollback and retired infrastructure

For a planned worker rollback, finish the active job, scale the worker to zero, apply `deploy`, then activate one replica. Reconcile uncertain mutations before resubmitting. Keep both login PVCs, all queued jobs and all data volumes.

The preceding known-good API image is `429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-agent-api@sha256:1cce42753455237a897f61bd7b5713db2e5a7774c167d886745ce5aab9b5ddbd`. If an API rollback is required, the operator can run the following protected command after pausing the worker:

```bash
kubectl set image -n if-portals deployment/if-agent-api \
  api=429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-agent-api@sha256:1cce42753455237a897f61bd7b5713db2e5a7774c167d886745ce5aab9b5ddbd
kubectl rollout status -n if-portals deployment/if-agent-api --timeout=10m
```

Check that the digest is still present before rollback because the existing ECR lifecycle policy retains a limited history. Terraform should then be reconciled through a separately reviewed targeted plan. Previous portal settings are saved privately in `/tmp/if-portal-deployment-rollback.json`.

Fission's exact obsolete Functions/Triggers/Package/Environment and compute objects have been retired after live replacement checks. Its namespace, CRDs, Helm archive and Bound storage PVC/PV remain. Do not Helm-uninstall: that chart includes its storage PVC. `terraform/k8s-retained-storage.tf` retains namespace ownership and forgets the Helm release without destruction when that separate state scope is reconciled. AWS repositories remain declared to prevent deletion. Do not run Terraform destroy, broad cluster mutations, Git writes or AWS deletion.

Recoverable source and private resource backups are under `/tmp/if-legacy-retired-20260913/`, `/tmp/if-fission-retirement-backup.json` and `/tmp/if-fission-helm-manifest.yaml`. The four revised Directives have a guarded transactional rollback in `/tmp/migrate_if_execution_directives.py`; it preserves both historical versions.
