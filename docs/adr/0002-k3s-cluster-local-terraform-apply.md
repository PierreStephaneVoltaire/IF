# Bare-metal k3s cluster with local Terraform apply

Date: 2026-07-03

## Status

Accepted

## Context

The IF agent and its portals run on a single-node bare-metal k3s cluster
(`sirsimpalot-g5-5000`). There is no CI/CD pipeline that deploys infrastructure:
the root `terraform/` is applied **locally**, by hand, against the k3s kubeconfig
on that same machine. AWS resources (DynamoDB, Lambdas, S3, API Gateway) are real
and live. Because the app is live in production, a broad `terraform apply` or
`terraform destroy` can take the service down.

## Decision

The cluster is k3s on bare metal, and infra changes are applied locally against
the local kubeconfig — this is the deploy workflow, not a gap to fill with CI.
To protect the live environment, non-targeted `terraform apply` and all
`terraform destroy` are forbidden to automated agents and enforced by a PreToolUse
hook (`.claude/hooks/guard-destructive.sh`) plus a `permissions.deny` list.
`terraform apply -target=...` is the only apply exception and requires explicit
operator approval. kubectl protection is **scoped to the IF agent API**
(deployment `if-agent-api` in `if-portals`, label `app=if-agent-api`): destructive
kubectl verbs are blocked only when they target `if-agent-*` / `app=if-agent-api`
or a broad `all`/`--all` blast in `if-portals`. Portal backends/frontends may be
mutated freely. `kubectl cordon/drain` are blocked unconditionally (single-node
cluster — they take down everything).

## Consequences

- No automated broad terraform changes: an agent cannot run `terraform apply`/
  `destroy` even if instructed to — the hook and deny list block them. Read-only
  `kubectl get/describe/logs/events/top` and `terraform fmt/validate/plan` remain
  available.
- The IF agent API cannot be nuked by an agent (`delete`/`scale 0`/broad `all` on
  `if-agent-*`), but portal backends/frontends can be redeployed at will — users
  tolerate brief portal downtime; the agent going down means no incoming messages
  get picked up.
- `kubectl rollout restart deployment/if-agent-api` (the terraform deploy path in
  `image.tf`) still works: the hook only intercepts Claude's Bash calls, not
  terraform's own local-exec provisioners.
- Deploys are a manual, operator-driven act, not an automated pipeline —
  deliberate for a single-operator, single-node setup.
- hostPath mounts resolve on the single node `sirsimpalot-g5-5000`; this is
  assumed, not portable to a multi-node cluster.
