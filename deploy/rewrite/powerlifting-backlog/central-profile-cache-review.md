# Block cache-read 403 diagnosis

## Verdict

Confirmed: `pl-profile` is the central authorization boundary and it is running a stale permission map. This is the sole cause of Luna's cache-only block-analysis 403. No source change is required.

The minimal bounded fix is a single-container rollout:

```bash
kubectl set image -n if-portals deployment/pl-profile \
  profile=429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-powerlifting-fns@sha256:17a58b454b834eccf2f3033598fc5718c15cd4cf2d66b2516cfcd0af9a0076ba
kubectl rollout status -n if-portals deployment/pl-profile --timeout=5m
```

`17a58b...` is the accepted `live-20260915-shared-fixes-v3` image already running in `pl-analytics`; `domain-candidates.json` records overall review status `accepted`. Do not roll the other ten `services_other` deployments for this issue. They do not evaluate cross-domain operation access.

## Live proof

At diagnosis time:

| Boundary | Live image | Embedded `analytics.blocks_get` rule | Cache-only result |
| --- | --- | --- | --- |
| Gateway | `176eafe...` | forwards `cacheOnly` to `analytics.blocks_get` | request reaches Profile |
| Profile | `008f6c...` | `permission: analytics:write` only | denies Luna with 403 |
| Analytics | `17a58b...` | `permission: analytics:write`, `cache_read: analytics:read` | accepts the same cached request |

The two live embedded maps were read from `/opt/powerlifting/services/permissions.json`:

* Profile SHA-256: `8234e50fb1b9ed929b9ad342f3adac1f9cbc19a8871eeea7f851b102e144b8f7`.
* Analytics SHA-256: `659e7de29ad6f81da217e142c14d98fb35b83919ba3be5175a1bf3b72af8b31f`.

In both live images, `operation_permission()` recognizes both `cacheOnly` and `cache_only`. Evaluating the actual embedded code gives:

```text
Profile  008f6c: operation_permission(blocks_get, {cacheOnly:true}) -> analytics:write
Analytics 17a58b: operation_permission(blocks_get, {cacheOnly:true}) -> analytics:read
Analytics 17a58b: operation_permission(blocks_get, {cacheOnly:true, refresh:true}) -> analytics:write
```

Every non-Profile service delegates authorization to `http://pl-profile.../internal/access`; the gateway independently calls that same endpoint before dispatching an operation. Profile logs show the matching `/internal/access` 403s, while Analytics logs show the corresponding `POST /operations/analytics.blocks_get` never occurs for Luna. This excludes route classification, argument forwarding, cache state, and sidecar behavior as the cause.

The existing acceptance evidence matches the boundary finding: Echo gets current cached block analysis `200` and unknown block `404`; Luna gets both requests as `403`. The prior report-cache probes already established the grant has `analytics:read`, cache record count is unchanged at 148, and explicit generation remains correctly denied with `403`.

## Required post-rollout acceptance

Run the same authenticated Luna/Echo fixture harness that produced `/tmp/final-public-report-acceptance.json`, with no data writes. Required statuses:

| Probe | Expected |
| --- | --- |
| Luna `GET /api/analytics/blocks/current/analysis?cacheOnly=true` | `200` |
| Luna unknown-block cache-only request | `404` |
| Luna explicit generation (`cacheOnly=false` or `refresh=true`) | `403` |
| Echo current cache-only request | `200` |
| Echo unknown cache-only request | `404` |
| Generation-cache count | remains `148` |

Also read the new Profile container's embedded rule before acceptance: it must include `cache_read: analytics:read`. If the rollout image digest is not `17a58b...`, stop rather than testing a different artifact.

## Manifest follow-up

The accepted rollout manifest currently assigns `pl-profile` to `services_other` (`008f6c...`). Update that mapping in the next manifest reconciliation so a normal full domain rollout does not reintroduce the stale authorization map. This is metadata hygiene, not a prerequisite for the targeted repair above.
