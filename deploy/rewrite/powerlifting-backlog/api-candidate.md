# Powerlifting single-environment API candidate

Prepared 2026-09-14 for Terra and protected operator review. Terra accepted the
API candidate and targeted plan; protected operator approval remains pending. This package does
not apply Terraform, restart a Deployment, change Kubernetes pins, invalidate
CloudFront, or alter AWS resources.

## Candidate

| Field | Recorded value |
| --- | --- |
| Existing repository | `429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-agent-api` |
| Immutable tag | `backlog-20260914-api-refresh` |
| Published digest | `sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f` |
| Build result | Packer completed and pushed to the existing ECR repository in exec session `27775` |
| Build source | `app/src/api/jobs.py` sha256 `5d82c5ff9556bb874eaefb2935dd928479d589e136da276047bb2546fe85cb37`; `app/src/api/powerlifting_principal.py` sha256 `a9af8d4f9f8855f4eab8567c8e299e6b6525d7bea76942478bc5882dc6928b84`; sorted `services/operations` manifest sha256 `16e606a690e8dc2bf58752ffdb8b4afc03d9faf958d18c97553aaf483f483036` |
| Build recipe | `docker/build.pkr.hcl` sha256 `237310633f6beff73204ca0ee8c228cb5785b2063145b10301324e8d7eccaf31` |
| Python base | `python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea` |

The tracked Packer recipe's public ECR base request returned HTTP 403. The
successful build used a temporary copy with only that base reference changed to
the digest-pinned Docker Hub image above. The tracked recipe was not edited, and
the temporary recipe was removed after the build. Rebuild after any accepted
source change and replace this record before review.

The live API pod currently runs
`if-agent-api@sha256:e2025f76d6111589c07b665ef491829bf8302778ef311f0dc70a1d53bfddf2a8`.
That is the immediate rollback reference. The previously documented known-good
reference is
`if-agent-api@sha256:1cce42753455237a897f61bd7b5713db2e5a7774c167d886745ce5aab9b5ddbd`.
Check that the selected rollback digest remains in ECR immediately before any
protected change.

## Checks already completed

The nested service suite passed 223 tests, root API access/tool tests passed 8
tests, and backend workspace `typecheck` and `build` passed. Live read-only
inspection found all sixteen Powerlifting Deployments, the gateway, API, worker,
Authentik, and Valkey ready, with no namespace events. These are mocked/local or
read-only checks; no deployed candidate check has occurred. The frontend was not
built because its AuthoredNotes source/test work remains under separate review.

## Terraform review records

The saved plans are action summaries only; their raw state and values are not
included here. The accepted API plan shows the deployment image pinned to the
candidate digest rather than `:latest` and remains pending protected approval.

| Plan | Action summary | Review condition |
| --- | --- | --- |
| `/tmp/powerlifting-backlog-foundation.tfplan` | 4 create, 4 update, 0 delete: the two Powerlifting tables; request table; app ConfigMap; API and app secrets; two generated passwords | Terra must verify table indexes, environment keys, and secret references. |
| `/tmp/if-release-api-foundation.tfplan` | 5 create, 6 update, 1 replacement delete: foundation resources, API Deployment/configuration/secrets, and local `null_resource.rollout_restart_main_api` bookkeeping replacement | Accepted by Terra; protected operator approval is required. The only delete is the local bookkeeping replacement; no AWS delete is permitted. |
| `/tmp/if-release-authentik-provider.tfplan` | 0 create, 0 update, 0 destroy: verified subject mapping is already present live | No apply required; retain the existing Authentik provider and database. |
| `/tmp/powerlifting-media.tfplan` | 0 create, 3 update, 0 destroy: CloudFront distribution disable configuration; thumbnail Lambda IAM policy; thumbnail Lambda function configuration | No apply. After backend readiness and separate approval, invalidate the existing distribution; do not delete the distribution or bucket. |

## Current digest-pinned plan readiness

The combined foundation and protected API plan is recorded in
[api-rollout-plan.md](api-rollout-plan.md), with a secret-free action summary in
[api-rollout-plan.json](api-rollout-plan.json). The reviewed image is the existing
ECR repository at
`429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-agent-api@sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f`.

The accepted plan preserves the no-delete scope, exact candidate digest, and
protected API-only mutation. No Terraform plan was applied during this publication.

## Protected rollout order

After the protected operator approves the accepted no-delete API plan, create
`PL_PRINCIPAL_SECRET` and `SESSION_SECRET` once: neither is
live in the current portal Secret, and neither is a rotation. Preserve their
names and values while the API, gateway, and services restart and during any
rollback. Apply the foundation resources first, then secrets/configuration, then
the API Deployment pinned by digest. Confirm API health and logs before running
the API-first gateway/services cutover in
[rollout.md](rollout.md); there is no direct service bypass. Keep the current
worker host and single environment; no new host, queue, Fission service,
database, or laptop deployment is part of this package.

The CloudFront disable and Lambda changes are a separate review. Wait for
backend/media readiness before any invalidation. The Cloudflare upgrade is
pending and the full 500 MiB test remains deferred; no chunked or direct-upload
fallback is authorized.

Rollback requires protected operator approval: restore the API to the live
rollback digest above, keep the secret keys/order unchanged, verify health, and
then reconcile Terraform with a new reviewed targeted plan. Do not use a broad
Terraform apply, Terraform destroy, AWS deletion, or Git write.
