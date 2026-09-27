# Final acceptance blocker review

Checked 2026-09-15 against the running `powerlifting-app-backend`, `pl-program`, `pl-analytics`, and `pl-sessions` pods, DynamoDB consistent reads, and the two final acceptance reports.

## Peer analytics read

This is not a grant-propagation bug and `grant_list` is the wrong direction.

- DynamoDB has the approved peer relationship `bf26b14dc5184bcaaef4bd9d66e8e1d7` under `Grant#live-acceptance-echo`.  Its grantee is Luna, its permissions are exactly `analytics:read` and `sessions:read`, and it has no expiry.
- The live `access_store.current_context('live-acceptance-luna', 'live-acceptance-echo')` returns both permissions.  The source and the deployed Program/Analytics service images use that same `Grant#<athlete>` query and `evaluate_facts` path.
- The older Handler grant is merely another record; it does not hide or replace the peer grant.  The legacy `lambda/pod_user/handlers/grant_list` endpoint is not consulted by authorization.
- A fresh authenticated Luna request to `/api/analytics/correlation?weeks=4&block=current&cacheOnly=true` returned 200.  It reported the expected cache miss; `cache_only=true` and the default request also returned 200 against the current deployment.

The prior 403 was a stale acceptance observation or a request that chose the generation/write route.  Reports are generation operations (`analytics:write`); cached report reads require only `analytics:read`.  Do not change access code.  Re-run the delegated proof with `cacheOnly=true`, record the 200/cache-miss result, then have Echo generate the report in Echo's own Athlete context before re-reading it as Luna.

Relevant paths: `services/access_store.py`, `services/access.py`, `backend/src/auth/scopes.ts`, and `backend/src/routes/analyticsService.ts`.

## Report-generation fixture

Echo's canonical `if-health` `program#v020` has no sessions.  Legacy `corr_report#...` cache records do not prove generation from current program data.

The smallest valid fixture is four completed `current`-block Sessions, one in each of four distinct weeks within the requested correlation window.  Each needs a valid ISO `date`, positive `week_number`, `completed: true` (or `status: logged/completed`), and at least one completed main-lift exercise plus one completed accessory exercise.  The correlation generator uses `name`, `sets`, `reps`, `kg`, and optionally `set_statuses`; it needs four distinct week numbers, not 701 copied legacy records.

Use Echo's normal authenticated session API, keeping every created Session in Echo's isolated partition:

1. Read the current Program revision and create four dated sessions with `POST /api/sessions/v020`, each including `expected_revision` and a unique idempotency key.
2. Complete each through `PATCH /api/sessions/v020/<date>/<index>/complete` with the returned current revision/envelope.
3. Echo calls `/api/analytics/correlation?weeks=4&block=current` once and waits for terminal generation; Luna calls the same URL with `cacheOnly=true` and selected Echo.

`program_evaluation` does not reduce this requirement: its full-block implementation also requires four completed current-block weeks.  The block-scoped evaluator bypasses that preflight but cannot serve as a meaningful acceptance proof of the public generation flow.

Relevant paths: `lambda/pod_analysis/handlers/correlation_analysis/correlation_ai.py`, `lambda/pod_analysis/handlers/program_evaluation/core.py`, `backend/src/routes/sessions.ts`, and `backend/src/controllers/sessionController.ts`.

## Onboarding and social fixtures

No fourth normal Person fixture exists: DynamoDB contains only Luna, Echo, and River acceptance People.  River is a verified normal Authentik Coach fixture and can be extended without an impossible cleanup requirement.  The normal browser/API sequence is:

1. `PUT /api/onboarding/role` with River's existing `coach` role plus `athlete`, active role `athlete`.
2. `PUT /api/onboarding/profile` retaining River's intended profile values.
3. `PUT /api/onboarding/athlete-basics` with valid basics; this durable isolated test history may remain.
4. Use River and Luna/Echo through the normal relationship endpoints for rejection/cancellation and the distinct-Coach replacement race.  Record IDs and final histories in the acceptance artifact.

For a fresh fourth Person, the existing normal provisioning mechanism is an Authentik API-created verified user followed by a browser OIDC login.  First login invokes `settings_create` and automatically calls `seedMasterCopiesForNewUser`; then use the three onboarding endpoints above.  Existing files show this pattern for Luna/River credentials and browser storage state, but there is no reusable fourth-user provisioning script.  Keep any credentials and storage state `0600`; do not copy program data from the Operator.  `master_copy_seed_user` copies directory data only, not training Sessions.

Relevant paths: `backend/src/services/userSettings.ts`, `backend/src/services/masterCopy.ts`, `lambda/master_copy_seed_user/core.py`, `backend/src/routes/onboarding.ts`, and `backend/src/controllers/onboardingController.ts`.

Cloudflare's 500 MiB limit and genuine Operator catalog approval remain external pending items; neither blocks the isolated fixture work above.
