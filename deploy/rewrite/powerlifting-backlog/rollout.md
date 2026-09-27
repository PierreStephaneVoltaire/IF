# Bounded Powerlifting rollout

`rollout_powerlifting.py` is the only mutation tool in this directory. It is
manifest-driven and allowlists exactly `powerlifting-app-backend`, the sixteen
`pl-*` Deployments, and the reviewed `powerlifting-app-frontend` Deployment. It
never patches `if-agent-api`, the Codex worker, Terraform, AWS, or a host. It uses immutable ECR digests, changes
only named container images, and adds one restart annotation per Deployment so
Secret values reload even when an image digest is unchanged.

The candidate record must be marked `accepted` by Terra and must retain the
manifest timestamp and digests. A candidate older than seven days, with a
changed timestamp, mutable image reference, changed repository, or unaccepted
status is refused. The current record is Terra `accepted`; protected deployment approval is still required before execution.

After the protected API plan has been reviewed and applied, the API must be
ready on its reviewed immutable digest before this cutover starts. The script
checks API rollout status, its immutable image, and its `/health` endpoint
before any portal mutation. It updates the gateway first,
waits for readiness and its `/health`, then updates `pl-analytics` as one
two-container change and continues through the remaining services. Every
service keeps `IF_API_URL=http://if-agent-api:8000`; the service HTTP/MCP hook
runs after all readiness checks. There is no direct service path that bypasses
the API during the protocol cutover interval.

## First-time secrets

`PL_PRINCIPAL_SECRET` and `SESSION_SECRET` are first-time portal Secret values.
Read-only inspection on 2026-09-14 found neither key in
`powerlifting-app-secrets`; they are not existing live values and this package
does not rotate them. The protected, targeted Terraform plan must create each
once, then every consumer must keep the same Secret name and value through the
API rollout, this portal rollout, and rollback. The rollout script checks for
the three required Secret keys and stops before changing a Deployment when one
is missing. Secret values never belong in this repository or command output.

## Dry-run and execution

From the repository root, after Terra accepts refreshed candidates:

```bash
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py --execute
```

The first command prints the bounded mutation commands without Kubernetes
mutation, together with a safe summary of the execute-time read-only checks:
API rollout/health, exact digest and Ready state, Secret key presence, and all
live container allowlists. It omits captured JSON and Secret values, so it is a
reviewable command assembly rather than an exact transcript of those internal
reads. The second performs that validated sequence, including the summarized
internal reads, and waits at most five minutes for each readiness check. Forward
rollout refuses the current unaccepted record; rollback recovery intentionally
uses only the recorded rollback references.

Rollback is deliberately scoped to an affected Deployment and requires the
explicit execution flag:

```bash
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py --rollback --deployment pl-analytics
python3 deploy/rewrite/powerlifting-backlog/rollout_powerlifting.py --rollback --deployment pl-analytics --execute
```

`pl-analytics` rolls both `analytics` and `reports` back together. Rollback
preserves Secret names and values, accepts either the recorded new API digest or
the recorded API rollback digest as the protocol precondition, verifies
readiness and the service hook, and must be followed by a new reviewed targeted
Terraform reconciliation. The rollback digests are recorded in
`domain-rollout-manifest.json`; verify they remain active in ECR immediately
before execution.

The frontend candidate is accepted in the bounded manifest and is selected by
the same reviewed `--execute` command after the protected API preflight passes.
This script cannot publish or build it.

## Reproducible package manifest

The package hash covers exactly these nine normalized, sorted paths:

```text
package-lock.json
package.json
tsconfig.json
backend/package.json
backend/tsconfig.json
frontend/package.json
frontend/tsconfig.json
packages/types/package.json
packages/types/tsconfig.json
```

Run `deploy/rewrite/powerlifting-backlog/check-package-manifest.sh`. Its exact
command is `printf '%s\n'` over that list, `LC_ALL=C sort`, one `sha256sum` per
file, a second `LC_ALL=C sort`, then the final `sha256sum`; the recorded value
is `01cadfabe453e595e784818526c39a52f1af99f93a1c32aeb7e0c3997c90916d`.
