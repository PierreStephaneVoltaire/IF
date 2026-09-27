# Digest pinned API rollout plan

Terra accepted the refreshed API candidate and its targeted no-delete plan for protected operator review. No plan was applied; the reviewed raw plan remains private at `/tmp/if-release-api-foundation.tfplan`, and this record contains no secret values.

The plan pins the existing API repository to:

`429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-agent-api@sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f`

It combines the foundation resources and the protected API update in one state snapshot:

- 5 creates: two Powerlifting tables, two generated secret resources, and the create half of the rollout bookkeeping replacement.
- 6 in-place updates: the request table GSIs, Powerlifting app ConfigMap, API Deployment, ECR pull Secret, API Secret, and Powerlifting app Secret.
- 1 delete/create replacement: `null_resource.rollout_restart_main_api` bookkeeping; its provisioner only waits for API rollout status.

The API pod template now hashes the API Secret and image reference. Updating shared API environment values therefore refreshes the Secret, changes `checksum/secrets`, and rolls the Recreate Deployment. The rollout wait bookkeeping also keys on the image, API ConfigMap, and API Secret fingerprints.

The prior plan has no action for `null_resource.packer_build_main_api`, no AWS deletes, no volume or hostPath changes, and no portal Deployment changes. The refreshed plan must recheck those conditions. The generated `random_password` values are first-time `PL_PRINCIPAL_SECRET` and `SESSION_SECRET` values; neither exists in the current portal Secret and this is not a rotation.

The local mode check is [check-api-image-modes.sh](check-api-image-modes.sh). It verifies that the default latest mode uses the existing source/build checksum and that changing its source component changes the checksum, while the accepted digest mode derives its checksum from the immutable image without a build dependency. Run it again after the candidate digest is selected. If a raw plan display reports a missing provider schema, initialize the locked provider cache first with `terraform -chdir=terraform init -input=false -upgrade=false`, then run `terraform -chdir=terraform show -json /tmp/powerlifting-if-api-digest-foundation.tfplan`.

## Approval command

Run only after protected operator approval and final live rollback-digest verification:

```bash
terraform -chdir=terraform apply -input=false /tmp/if-release-api-foundation.tfplan
```

This command has not been run.
