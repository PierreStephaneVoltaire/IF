# Rollback image recovery and retention preparation

Prepared 2026-09-14 at 19:30 America/Toronto; recovery completed 2026-09-14 at 19:37 America/Toronto. Candidate publication and rollout remain paused.

## Live evidence

The single node is `sirsimpalot-g5-5000` (`192.168.2.56`). Read-only inspection found no `if-portals` events. Both affected workloads are Ready:

| Workload | Container | Running image digest |
| --- | --- | --- |
| `pl-analytics` | `reports` | `if-powerlifting-app-backend@sha256:138fadf8bf38298c1de9b88bae9b88b46fd207bcd10e242c9d7dfd7e9e24b10a` |
| `powerlifting-app-backend` | `backend` | `if-powerlifting-app-backend@sha256:40a54ba282e28a8f5cbc8cbc0201c328a0f2b132129d95721477fe8fbb9b687d` |

The services run `if-powerlifting-fns@sha256:1aed2fdbb71a750576d478700be761490e5d5ef8f26ff5d6709423b2b9984bcd`. The API runs `if-agent-api@sha256:e2025f76d6111589c07b665ef491829bf8302778ef311f0dc70a1d53bfddf2a8`.

## ECR evidence

The exact Analytics rollback index was absent from `if-powerlifting-app-backend`. The recovered runnable AMD64 child is now present and `ACTIVE`; the API, services, and gateway rollback digests and all four refreshed candidate digests were reverified `ACTIVE` after recovery. Current lifecycle policies remain:

| Repository | Current policy | Consequence |
| --- | --- | --- |
| `if-powerlifting-app-backend` | `any` / `imageCountMoreThan` 5 | Evicted the untagged Analytics rollback index after candidate pushes |
| `if-powerlifting-fns` | untagged / `sinceImagePushed` 1 day | Tagged live and candidate indices remain selected out of this rule |
| `if-agent-api` | `any` / `imageCountMoreThan` 5 | Candidate and live references need the same tagged retention guard |

The node cache contains the exact OCI index and its runnable AMD64 manifest. The index was exported to `/tmp/if-analytics-image.ZIonqN/analytics-rollback.oci.tar` (89,369,600 bytes); the archive's top-level index blob hashes to `sha256:138fadf8bf38298c1de9b88bae9b88b46fd207bcd10e242c9d7dfd7e9e24b10a`.

The cached index also references attestation manifest `sha256:b0ca641f650a411cef395108ca90663e1effbd3b71678f5b595fa39a47198363`. That 564-byte blob is absent from containerd, so the original index cannot be republished and remains historical evidence only. ECR rejected the original index with `ReferencedImagesNotFoundException`; it was not retried.

The existing child manifest was published directly, without a build or layer rewrite, under the unique tag `rollback-20260914-analytics-amd64`:

| Historical index | Recovered ECR rollback child |
| --- | --- |
| `sha256:138fadf8bf38298c1de9b88bae9b88b46fd207bcd10e242c9d7dfd7e9e24b10a` | `if-powerlifting-app-backend:rollback-20260914-analytics-amd64@sha256:a81b36df0c9b717db2d882f9d1434eae0b2061ad318ffda601fa55dbc90f4c17` |

The recovered image is `ACTIVE` in ECR with `application/vnd.oci.image.manifest.v1+json`. Its config digest is `sha256:06ed17841e3c963f48bef3398d7889953e665f3945fdff710fa3ed4eeb5002f3`; its twelve layer digests, in order, are `sha256:a8ac7f6c67abc236e4c745052c404112b8fab6fe8ac3a329d1ef3b867ad67c71`, `sha256:9f6b7612ad6931b5ff604ab41e2dfed94aad78d11388cc8231d6a395a6aac9d9`, `sha256:6345e76995359217c142322a7de521f340a48752a39a3ae15493e095675bb403`, `sha256:cd1f23a0f33e8a977157cb897344282db05dc6325371f1395dc8831b717ca159`, `sha256:3477b72abf7bb02418a74d33b40c67c1357b466fd2c0d75c686bda5aa2d5d99e`, `sha256:b70cfa9f777822377e42f124012775b91282d2d26ca45603a723b00e464c56c9`, `sha256:6c8c9b820f19c5b4ac1ebcac5fa6cea58f2ddee04bd3a018d045d9a97a0fdc2b`, `sha256:ed75e924885bfc3908ee2643bf73f7791d479b785e0f5e88c66e54db16509dd2`, `sha256:920a47305e01fee6e33c5bad4a4a14a68aef3c156dbca8b9bf882ffed825eb61`, `sha256:60cd86a14d9b82afc7bc6e0a3a2f4fd95622c61d773441fb6907ca521841d02a`, `sha256:d622aadd14cf172019c055d137be5dc5a3d41c046d91b0ff3d41c8a6654b2166`, and `sha256:4f4fb700ef54461cfa02571ae0db9a0dc1e0cdb5577484a6d75e68dc38e8acc1`. The archive config and ECR manifest have the same canonical JSON and entrypoint `docker-entrypoint.sh` with command `node dist/analyticsSidecar.js`, proving the runnable child content was preserved.

## Recovered Analytics build manifest

The previous [analytics-dist-manifest.txt](analytics-dist-manifest.txt) is retained as the historical rollback provenance. The new candidate image `backlog-20260914-analytics-refresh` has a separately extracted [analytics-candidate-dist-manifest.txt](analytics-candidate-dist-manifest.txt), with aggregate SHA-256 `63027ecd40744c0a5c37bbe1cb8e1f6cd2c597a99f8dda39eda7f212760893d6`; its extracted files remain in `/tmp/if-analytics-recovery.t4EVwa/backend/dist`.

## Retention preparation

Lifecycle ownership is Terraform managed. The root IF stack owns API and services lifecycle resources in [terraform/image.tf](../../../terraform/image.tf); the portal AWS stack owns backend/frontend lifecycle resources in [utils/powerlifting-app/terraform/modules/ecr/main.tf](../../../utils/powerlifting-app/terraform/modules/ecr/main.tf).

The prepared changes add a priority-one tagged `imageCountMoreThan=999` guard for `if-agent-api` and `if-powerlifting-app-backend`, followed by the existing five-image rule. The frontend keeps its current rendered policy, and the services repository keeps its current untagged policy. The guard protects all tagged live and candidate references while deployment manifests continue to pin immutable digests; ECR also does not expire a child referenced by a manifest list before that list. ECR tags remain mutable; a tag is a retention selector, not an immutable identity.

The saved plans `/tmp/if-api-ecr-retention.tfplan` and `/tmp/powerlifting-backend-ecr-retention.tfplan` are **UNAPPLICABLE** because they replace the lifecycle-policy Terraform objects. Do not apply either plan. The exact policy payloads for a separately reviewed, non-deleting ECR `PutLifecyclePolicy` update are [ecr-retention-api-policy.json](ecr-retention-api-policy.json) and [ecr-retention-backend-policy.json](ecr-retention-backend-policy.json):

```text
aws ecr put-lifecycle-policy --repository-name if-agent-api --region ca-central-1 --lifecycle-policy-text file://deploy/rewrite/powerlifting-backlog/ecr-retention-api-policy.json
aws ecr put-lifecycle-policy --repository-name if-powerlifting-app-backend --region ca-central-1 --lifecycle-policy-text file://deploy/rewrite/powerlifting-backlog/ecr-retention-backend-policy.json
```

Neither policy command has run. These task-authorized non-deleting updates are staged for the coordinated release alongside the protected Terraform review; they are not an automatic bypass. ECR lifecycle matching and ordering follow the [AWS lifecycle policy properties](https://docs.aws.amazon.com/AmazonECR/latest/userguide/lifecycle_policy_parameters.html): the tagged guard is priority 1, the `any` rule is priority 2, and ECR requires `any` to be evaluated last. AWS documents that lifecycle expiration may occur within 24 hours after criteria are met; a manifest-list child cannot expire before its list.

The current AWS provider renders the policy text change as `1 to add, 0 to change, 1 to destroy` for the lifecycle-policy Terraform object. It does not plan an image, repository, or unrelated-resource deletion, but it is not an in-place resource action. No apply is authorized in this record; the operator must explicitly review that provider replacement before deciding whether to apply or use an equivalent controlled ECR policy update.

## Remaining approval prerequisites

1. The exact Analytics index remains historical because its attestation is missing; use the recovered AMD64 child only where the compatible platform digest is explicitly accepted for rollback.
2. Review the two prepared `PutLifecyclePolicy` payloads and the Terraform ownership/reconciliation implications before any retention update.
3. Re-verify all live, candidate, and recovered rollback digests as `ACTIVE` immediately before any future rollout.
4. Keep `domain-candidates.json` at `accepted`; Terra accepted the refreshed candidates, while protected deployment approval remains pending.
