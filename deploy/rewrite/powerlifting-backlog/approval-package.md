# Terra approval package

Prepared 2026-09-14. Release execution remains staged; the Terraform applies await operator approval. No Terraform apply, Kubernetes mutation, CloudFront change, lifecycle update, AWS deletion, or Git operation ran.

The protected approval request covers the targeted API/foundation plan and the three-update media plan. The two reviewed non-deleting ECR lifecycle updates and the portal rollout are already task-authorized steps in the coordinated sequence and remain staged until protected rollout approval. Authentik has no apply required.

The reviewed in-place retention payloads are [ecr-retention-api-policy.json](ecr-retention-api-policy.json) and [ecr-retention-backend-policy.json](ecr-retention-backend-policy.json). The saved Terraform retention plans are `UNAPPLICABLE` because the provider replaces the lifecycle-policy resource; do not apply `/tmp/if-api-ecr-retention.tfplan` or `/tmp/powerlifting-backend-ecr-retention.tfplan`.

The staged ECR updates use these exact existing repositories and region:

```text
aws ecr put-lifecycle-policy --repository-name if-agent-api --region ca-central-1 --lifecycle-policy-text file://deploy/rewrite/powerlifting-backlog/ecr-retention-api-policy.json
aws ecr put-lifecycle-policy --repository-name if-powerlifting-app-backend --region ca-central-1 --lifecycle-policy-text file://deploy/rewrite/powerlifting-backlog/ecr-retention-backend-policy.json
```

The regenerated targeted API/foundation plan is `/tmp/if-release-api-foundation.tfplan`, pinned to API digest `sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f`. It has 5 creates, 6 updates, and one destroy that is only `null_resource.rollout_restart_main_api` bookkeeping replacement. It has no AWS deletes, Packer rebuild, worker, volume, Postgres, laptop, new environment, unrelated lifecycle, or broad resource scope. Review `/tmp/if-release-api-foundation-plan.log`; the command is:

```text
terraform -chdir=terraform apply -input=false /tmp/if-release-api-foundation.tfplan
```

Authentik requires no apply: the refreshed provider review has zero changes, and the verified subject mapping is already present live. The refreshed media plan is `/tmp/if-release-media.tfplan` and has exactly three updates: the CloudFront distribution disable, thumbnail IAM policy, and thumbnail Lambda configuration. Its sanitized log and approval command are recorded in [release-plan-summary.json](release-plan-summary.json).

The frontend candidate is documented in [frontend-candidate.md](frontend-candidate.md). Terra accepted it and it is enabled in the bounded rollout manifest at digest `sha256:881e0d6d146e20e5dfcd7a666ba14c83af3cb58be8741b71aade6640d129b38c`, with live rollback `sha256:b06fbfb3d24f6f7230504629c58062c03509ba5d03fac4a602947156545273fe`; both are `ACTIVE`. Execution remains pending the required protected Terraform approval.

After protected approval, run the sequence in this order: apply the two staged ECR lifecycle updates; apply the reviewed foundation/API plan; verify API readiness and rollback references; run the bounded portal rollout dry-run, then its explicit execute command (which selects the accepted frontend along with the gateway and sixteen services); verify portal readiness and the service hook; apply the reviewed media plan and perform its existing-distribution invalidation after gateway readiness; then record deployed acceptance. Authentik needs no apply. Preserve candidate and rollback digests, Secret names/values, and existing host/repository topology. For recovery, use the bounded rollback command below and follow with a new targeted Terraform reconciliation.

```text
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py --execute
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py --rollback --deployment pl-analytics
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py --rollback --deployment pl-analytics --execute
```

Acceptance remains pending for deployed acceptance, the Cloudflare request allowance upgrade, and the 500 MiB post-deployment media test. Social review is closed: its 18 scenario checks plus aggregate include the mounted regression, with the eight state outcomes verified and no unhandled, browser, or expected-response errors. Local offline checks passed (25); live revocation/conflict acceptance remains pending. Candidate review is accepted, while protected deployment approval remains pending.
