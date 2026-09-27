# Final rollout-boundary review — 2026-09-15

## Gateway AWS credential mount: accepted, with a shell-probe caveat

The applied JSON patch is source-conformant and narrowly scoped: it adds only
`AWS_SHARED_CREDENTIALS_FILE` and `AWS_CONFIG_FILE`, and changes the existing
`aws-credentials` read-only mount from `/root/.aws` to `/home/nodejs/.aws`.
The live `powerlifting-app-backend` keeps digest
`sha256:176eafe171ece074a53d1e26f474a37fa71cd3f388977db512461f340af44026`;
no other resource was changed.

The live pod is Ready and runs as UID/GID 1001.  Its environment and one
read-only hostPath mount match Terraform.  The host ACL is limited to UID 1001
read access on `credentials` and `config`; it does not grant the directory or
other AWS files.  Safe zero-byte opens of both mounted files succeed as UID
1001, and the gateway's actual AWS SDK default provider resolves with IMDS
disabled and all standard ambient credential variables absent.  The prior
`test -r` result was a shell-probe artifact, not an access failure.  No
credential values were read or printed.  The earlier ordinary media upload,
confirm, HEAD and Range acceptance remains valid.

Keep the current paths, existing mount and two-file ACL scope.  A future
credential check should use a zero-byte open or SDK resolution, not `test -r`.

## Active correctness blockers

- `max_target_update` now correctly projects the committed target record and
  uses `ProgramStore`'s commit-time `sk` and `updated_at`; focused source tests
  pass 17/17.  The shared added result keys are compatible with its sibling
  permissive result schemas.  Before release acceptance, add or run a real
  `ProgramStore` first-write/replay regression: the current fake-store test does
  not exercise marker replay.  A pre-fix marker from the former committed-then-
  500 path has no persisted commit timestamp, so it cannot be converted into an
  exact historical success response.  Treat that known key as recovered by
  readback; use a new key for the one-write/replay acceptance.  Future markers
  already retain the committed top-level timestamp and stable target metadata.
- `analytics.blocks_get` remains an active read/cache boundary repair: cached
  reads must require read permission without generation, and the sidecar must
  forward cache-only.  Current gateway logs show cache-only Block requests
  returning 404.  The new analytics deployment is now observed 18/18 and Ready
  1/1, and legacy weekly returned 200, but neither closes Block cache nor real
  report generation/dedup/reference acceptance.

## Acceptance gaps, not new rollout defects

- Real report generation/cache/dedup/reference acceptance remains pending.
- Program/Template HTTP and MCP replay evidence is deployed and healthy (16/16
  service harness checks), and frontend session navigation acceptance is
  complete.  The only remaining Template gap is the specified repeated-target
  matrix.
- The real concurrent stale-processing media race is untested.  The Cloudflare
  allowance and 500 MiB media test remain deferred; positive operator tag/catalog
  acceptance remains unverified because operator access is unavailable.

## Boundary findings

The live topology is the intended single portal gateway/frontend plus exactly
sixteen `pl-*` domain deployments (Valkey excluded); no second service or host
was found.  Existing deployed evidence covers signed-principal/forged-principal
denial and public/media boundaries.  No additional authority bypass was found
in this bounded review.  The documented weekly GET projection snapshot side
effect is permission-checked and is not an authority bypass.
