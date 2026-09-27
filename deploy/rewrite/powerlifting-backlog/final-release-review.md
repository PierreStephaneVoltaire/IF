# Final release evidence review — Terra

Reviewed 2026-09-15. This is a read-only final review of the deployed gateway
coherence fix, release manifests, and supplied acceptance artifacts. It does
not treat a local suite, service hook, or ready pod as browser, Authentik, media
processor, or Cloudflare acceptance.

## Result

Accepted with the two explicit external acceptance limits below. No material
source-level authorization, data-loss, or integration regression was found in
the bounded review. The release evidence supports the deployed Program-read
cache fix, native current-Max and form-media flows, immutable current pins,
service readiness, the completed live stale-worker race, and the separately
recorded OIDC/browser journeys.

## Gateway cache coherence

`backend/src/routes/programs.ts` SHA-256 is
`55f57a5cd4c1eb93591b26d00976ca085b2142031576639fe281cd21b6b39e86`, the
same source attested by `/tmp/final-program-cache-coherence.json`. Both ordinary
Program GET handlers (`/api/programs` and `/api/programs/:version`) call their
controllers directly and have no `cacheGet` middleware. The route remains
behind the normal server mount and controller invokes the existing Program
operation. This removes the seven-day Valkey response-cache path only for those
two reads; it does not remove report caches, offline caches, or request/auth
checks. Other cache wrappers are still present on their own routes.

The deployed gateway digest is
`if-powerlifting-app-backend@sha256:d4cbce473ab1dd4f6d7f4e7105dbc47f8da362a708f179af43b000369e056cd0`.
The coherence artifact records the same unchanged ordinary authenticated URL
returning squat `185 -> 186 -> 185`, source revisions `64 -> 65 -> 66`, using
the normal signed `health_update_current_maxes` typed operation. It also records
the ready media slot unchanged across the Max mutation and restore. The source
writer uses `ProgramStore.mutate_source` with expected revision and idempotency;
the frontend's Max preview resolves `current_maxes` before `manual_maxes`.

## Form-media evidence

`/tmp/final-lift-media-acceptance.json` contains actual live evidence for:

- a 180-second form video reaching ready;
- a 181-second video failing with the three-minute-limit result, while the
  older ready media remains published;
- same-key retry/confirm replay without an additional ready notification;
- replay-safe removal of failed pending media and ready media, ending with an
  empty slot; and
- source current-Max mutation and restoration preserving the ready slot's id,
  processing status, target revision, and allocation revision.

The newer Program-coherence artifact additionally records a successful normal
replacement: old ready id remains published while the replacement is pending;
replacement becomes ready at target/allocation revision `2`; cleanup leaves an
empty slot. This supports the media revision invariant and owned cleanup.

The finalized stale-worker artifact is accepted. It records A in `processing`
while B became ready at `10:27:09Z`, then A completing at `10:27:27Z` without
displacing B. The final slot remains B at target revision `2`, allocation
revision `1`, and ready status; cleanup restores the empty fixture slot. The
three earlier unsuccessful timing attempts are not used as proof.

## Pins, tests, and readiness

The executable rollout manifest and candidates use immutable digest pins. The
current inventory matches the gateway digest above, videos
`sha256:17a58b45...`, performance `sha256:6d0a745a...`, API
`sha256:3076896f...`, worker `sha256:ca816dfd...`, and frontend
`sha256:a7aad69...`; protected API and worker are recorded unchanged and Ready.
The manifest reconciliation records all 16 services Ready with the 22-check
live hook passed and retained rollback pins. The final local candidate images
were pruned only after ECR verification and with zero local containers using
them.

I independently ran the non-mutating manifest package hash check (matched
`01cadf...916d`) and `test_rollout_powerlifting.py` (8 passed). The preserved
suite logs show `253 passed, 9 warnings, 16 subtests passed`; the live hook log
shows `16/16` services and `22/22` checks passed. These prove local regression
coverage and live typed-service reachability. The Program coherence scenario is
specifically signed native HTTP plus genuine OIDC-authenticated portal reads,
not a browser UI test. Separate artifacts record real Authentik login/callback
checks, frontend browser acceptance, onboarding/social writes, and revocation
behavior; this narrow review did not rerun them.

## Remaining limitations

1. No 500 MiB request was sent through Cloudflare, so the configured allowance
   is not end-to-end accepted.
2. Operator-specific acceptance remains unavailable where it requires the
   operator application identity. Do not synthesize it from the dedicated
   acceptance Athletes.
3. The earlier security closure remains a bounded source/inventory review. It
   is supportive evidence for permission and source-scope behavior, not a
   replacement for those external acceptance gaps.

## FEAT2 lift-profile context addendum

Accepted from the current `final-lift-profile-context-acceptance.json` evidence.
Echo's owner mutation wrote three distinctive squat failure nodes at revision
25 and restored the original empty nodes. Luna, with Echo selected, received
the exact nodes from the authenticated portal context read (`200`) and from
the signed native `handler_context` HTTP and MCP transports (`200`, MCP
`is_error: false`).

River's real tied Coach request and approval granted the recorded training
permissions. The same context read returned the exact nodes (`200`); after
Echo revoked that relationship, it returned `403`. The fixture's lift profile
was restored. The deployed browser page also exercised its real controls with
no API interception: its displayed guidance changed from `120.0 kg` with a
20 kg bar to `100.0 kg` with a zero bar and `120.4 kg` after choosing pounds
and entering 45 lb, then restored the controls.

The older `130/230/custom-50` numeric labels are local simulated API guidance,
not this live browser proof. They are not used for this acceptance finding.
