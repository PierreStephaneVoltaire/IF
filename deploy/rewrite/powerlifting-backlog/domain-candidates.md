# Powerlifting domain image candidates

Prepared 2026-09-14 for Terra review. Terra accepted these immutable candidates in existing ECR repositories only. No deployment, Kubernetes mutation, Terraform apply, image pin, or CloudFront change was performed. The frontend candidate was built and published under a unique tag; no `latest` tag was overwritten.

## Published candidates

| Component | Existing ECR repository | Immutable tag | Published digest | Build recipe | Base |
| --- | --- | --- | --- | --- | --- |
| Sixteen Python services | `if-powerlifting-fns` | `backlog-20260914-services-refresh` | `sha256:c3f5af1b70570d87fcf0044a302b980d3c90b0549cf9e323f36ee0b5ecd04d92` | `services/Dockerfile` | `python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea` |
| Analytics Node sidecar | `if-powerlifting-app-backend` | `backlog-20260914-analytics-refresh` | `sha256:60c83f4c17f59b32ac19e7b1da5894d4ee2fdc9b17e1e2d0942ce1c3987cc69e` | `services/analytics.Dockerfile` | `node:24-bookworm-slim@sha256:2fe369e969550cde8e867afc3fe370b260140cab4a23d467074295b42163d553` |
| Gateway backend | `if-powerlifting-app-backend` | `backlog-20260914-backend-refresh` | `sha256:27c6ddb82e236602a05ddb3c4af6a854bb31c29dbfeba1a97865802be5c4b1b9` | `docker/powerlifting-backend.pkr.hcl` | `node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` |

The tracked gateway Packer recipe requested `public.ecr.aws/docker/library/node:20-alpine` and received HTTP 403. A temporary recipe changed only that base to the already-local official `node:20-alpine` digest above. It retained the tracked recipe's build steps and was removed after the build. Packer push processing was excluded; only the immutable gateway tag was pushed manually, so no ECR `latest` tag was created.

The refreshed API candidate is tracked separately at `if-agent-api:backlog-20260914-api-refresh@sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f`. Its operations manifest changed, so the API was rebuilt with the same pinned source recipe and a temporary digest-pinned Python base workaround.

## Deployment mapping

The services candidate is shared by each existing domain Deployment:

`pl-program` (`program`), `pl-sessions` (`sessions`), `pl-competition` (`competition`), `pl-federation` (`federation`), `pl-glossary` (`glossary`), `pl-goals` (`goals`), `pl-budget` (`budget`), `pl-calculations` (`calculations`), `pl-performance` (`performance`), `pl-weight-log` (`weight-log`), `pl-templates` (`templates`), `pl-imports` (`imports`), `pl-profile` (`profile`), `pl-lift-profiles` (`lift-profiles`), `pl-analytics` (`analytics`), and `pl-videos` (`videos`).

`pl-analytics` keeps the Python `analytics` container on the services candidate and maps its `reports` container to the Analytics sidecar candidate. `powerlifting-app-backend` maps its `backend` container to the gateway candidate. The sixteen services retain `PL_DOMAIN`, `IF_API_URL=http://if-agent-api:8000`, the existing AWS credential file paths, and `powerlifting-app-secrets`; analytics retains loopback `ANALYTICS_NODE_URL=http://127.0.0.1:8091`, and the sidecar retains `ANALYTICS_NODE_PORT=8091`.

## Live rollback references

Read-only pod inspection captured these running image digests immediately before publication. Each digest was confirmed `ACTIVE` in its existing ECR repository.

| Workload | Running rollback digest |
| --- | --- |
| API | `if-agent-api@sha256:e2025f76d6111589c07b665ef491829bf8302778ef311f0dc70a1d53bfddf2a8` |
| Codex worker | `if-agent-api@sha256:ca816dfdbe7b6083d55adb61c5123434d7de28c7b10d7affb805d43f010c5636` |
| Sixteen Python services | `if-powerlifting-fns@sha256:1aed2fdbb71a750576d478700be761490e5d5ef8f26ff5d6709423b2b9984bcd` |
| Analytics sidecar | `if-powerlifting-app-backend@sha256:138fadf8bf38298c1de9b88bae9b88b46fd207bcd10e242c9d7dfd7e9e24b10a` |
| Gateway backend | `if-powerlifting-app-backend@sha256:40a54ba282e28a8f5cbc8cbc0201c328a0f2b132129d95721477fe8fbb9b687d` |

The older documented Analytics and gateway rollback digests were not present in ECR when checked. The live digests above are the compatible rollback references for this candidate set; verify them again immediately before any protected rollout.

The live Analytics rollback index was subsequently recovered from the node's k3s containerd cache and preserved as `/tmp/if-analytics-image.ZIonqN/analytics-rollback.oci.tar`. Its historical top-level digest remains `sha256:138fadf8bf38298c1de9b88bae9b88b46fd207bcd10e242c9d7dfd7e9e24b10a`, but its cached attestation child `sha256:b0ca641f650a411cef395108ca90663e1effbd3b71678f5b595fa39a47198363` is missing, so ECR cannot accept that exact index. The existing runnable AMD64 child was published with identical config and layers as `rollback-20260914-analytics-amd64@sha256:a81b36df0c9b717db2d882f9d1434eae0b2061ad318ffda601fa55dbc90f4c17` and verified `ACTIVE`; this compatible platform digest is the accepted recovery mapping and is the Analytics rollback digest in `domain-rollout-manifest.json`. See [rollback-recovery.md](rollback-recovery.md), [analytics-dist-manifest.txt](analytics-dist-manifest.txt), and [analytics-candidate-dist-manifest.txt](analytics-candidate-dist-manifest.txt).

## Required protected restart order

1. The accepted API plan and these candidates remain pending protected operator approval; no plan was applied here.
2. Apply the foundation resources, then configuration and secrets. `PL_PRINCIPAL_SECRET` and `SESSION_SECRET` are first-time values for this portal and are not live in the current Secret; create them once through the reviewed protected Terraform plan. After creation, preserve their names and values through every restart and rollback. Never rotate them during this rollout, and do not create a new queue, host, database, or credential set.
3. Update the API to the accepted immutable digest, then verify API health and logs.
4. Restart `powerlifting-app-backend` on the gateway candidate and verify port 3005 health.
5. Restart `pl-analytics` so its Python container and Node `reports` sidecar switch together.
6. Restart the remaining domain Deployments in manifest order: `pl-program`, `pl-sessions`, `pl-competition`, `pl-federation`, `pl-glossary`, `pl-goals`, `pl-budget`, `pl-calculations`, `pl-performance`, `pl-weight-log`, `pl-templates`, `pl-imports`, `pl-profile`, `pl-lift-profiles`, and `pl-videos`. Confirm every readiness probe and service-to-API path before accepting the rollout.

Portal rollback is authorized through the bounded rollout script: restore the recorded rollback digest for the affected workload, preserve secret names and values, and verify health. Only a protected API rollback or Terraform reconciliation requires protected operator approval and a new reviewed targeted plan.

## Source and content hashes

Hashes use sorted `sha256sum` manifests, excluding generated Python caches, pytest caches, and `node_modules`.

| Input | SHA-256 |
| --- | --- |
| `services/` source manifest | `ca88c32edf4782413e8c183ab3d6e6536ffb44b6de7b18036829a8e2d27b51bf` |
| `lambda/` source manifest | `8b7060c1203f2c58b08a758ef62ea8ae693b18f9c90f19b918ed9ee5a842fa1e` |
| `backend/src/` source manifest | `ee593f04adafe95a46424f6962d59c723c662e71e330db8b95aa3bb80df6a3f0` |
| `backend/dist/` gateway build manifest | `8067636de1521c22370343b8240d800661b586381df8e5e5f1a52d728deba7d0` |
| `backend/dist/` historical rollback manifest | `63027ecd40744c0a5c37bbe1cb8e1f6cd2c597a99f8dda39eda7f212760893d6` |
| `backend/dist/` refreshed candidate manifest | `63027ecd40744c0a5c37bbe1cb8e1f6cd2c597a99f8dda39eda7f212760893d6` |
| `packages/types/` source manifest | `a8af254105823e020ce9337e762054e8fedd1bcfdfd4f5924ab166e33f2e8124` |
| `packages/types/dist/` build manifest | `67f32a2fa27f43fc7a6dd898eccc0f7e1d48cad28124b54d6e77e1783c269604` |
| sorted `services/operations/` manifest | `16e606a690e8dc2bf58752ffdb8b4afc03d9faf958d18c97553aaf483f483036` |
| exact nine-file package manifest | `01cadfabe453e595e784818526c39a52f1af99f93a1c32aeb7e0c3997c90916d` |
| `services/Dockerfile` | `5f8169e3b6de85d2153c326f86da5f2a7ff4c130dc807dd624f6684096668ade` |
| `services/analytics.Dockerfile` | `8754758cfaa388e57d79cb8f0645520f0ecf7924b06b3e5a48870a1b04d7eaa6` |
| tracked `docker/powerlifting-backend.pkr.hcl` | `89a8930119d4f712cde30b8eb73900f29c6e907d7369f15dd556cbb460c7a9a7` |

## Checks and limits

The nested service suite passed 223 tests; root API access/tool tests passed 8 tests; backend workspace `typecheck` and `build` passed. All four refreshed backend candidate pushes and the frontend candidate push were followed by ECR tag/digest/status verification and local image inspection. The API image contains the refreshed operations manifest; the service and gateway images contain the same operations files, the analytics image contains its rebuilt backend dist and operations files, and the frontend candidate contains the Terra accepted AuthoredNotes source. Live inspection was read-only apart from the authorized Analytics rollback recovery attempt; no deployed candidate acceptance has occurred. The frontend candidate is Terra accepted and enabled in the bounded manifest; deployment remains pending protected operator approval and deployed acceptance. Retention preparation and remaining approval prerequisites are recorded in [rollback-recovery.md](rollback-recovery.md).

The reproducible manifest commands were run from `utils/powerlifting-app`:

```text
printf '%s\n' package-lock.json package.json tsconfig.json backend/package.json backend/tsconfig.json frontend/package.json frontend/tsconfig.json packages/types/package.json packages/types/tsconfig.json | LC_ALL=C sort | while IFS= read -r f; do sha256sum "$f"; done | LC_ALL=C sort | sha256sum
find services -type f -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
find lambda -type f -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
find backend/src -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
find backend/dist -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
find packages/types -type f -not -path '*/dist/*' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
find packages/types/dist -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
find services/operations -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | LC_ALL=C sort | sha256sum
```

Temporary base-only recipes were removed after publication. Their hashes were `services/.Dockerfile.refresh` `f7ec008e54e82f193513562335cd4c008f5516b202f415f8a3c74db8c270d705`, `services/.Dockerfile.analytics.refresh` `557223461c2232f32755cb3194648ecfc98830e9865b77b1d35faea67588b014`, and `.powerlifting-backend-refresh.pkr.hcl` `d70422b9f501abb24c4bbffbebaa4666aba06b5831810fba19d11efe2ae77209`; the API temporary recipe used the same base-only substitution and was removed after the Packer run.
