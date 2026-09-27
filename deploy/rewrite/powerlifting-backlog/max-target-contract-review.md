# `max_target_update` ready review — 2026-09-15

## Accepted implementation

The handler now returns the existing manifest's target record from the committed
mutation: version, committed `sk`, three targets, recomputed total, commit-time
`updated_at`, and revision.  `ProgramStore._commit_source_sync` is the correct
source for `sk` and timestamp: it assigns both before the transaction and stores
them in the idempotency result.  No result schema was broadened.

The shared result addition is safe for current callers: the two other
`update_meta_fields` operations have permissive object result schemas.  The
focused required selection passes 17/17 in `/tmp/if-rewrite-venv` from the
nested repository.  The deployed target remains `pl-performance`; it is still
the prior image, observed generation 10/10 and Ready 1/1.

## Required acceptance and one compatibility limit

Run one fresh-key authenticated PUT, GET readback, and same-key replay on a
dedicated acceptance Athlete after deploying `pl-performance`.  The current
unit regression uses a fake committed store, so it does not prove the real
ProgramStore idempotency marker round trip; add that direct regression when
practical.

The legacy-marker compatibility repair is accepted.  `created_at` is the same
single `now` value used for the Program and pointer commit in the original Dynamo
transaction, so replay backfill of `updated_at` is the committed timestamp, not
an invented value.  The selected program key is also the exact key used to make
the marker.  No result schemas changed.  The actual legacy-shape replay
regression passes.  Deploy `pl-performance`, then run the fresh PUT/GET/same-key
replay acceptance.
