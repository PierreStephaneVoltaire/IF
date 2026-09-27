# Historical review iterations — superseded

Current acceptance is in profile-ui-terra-review.md. Earlier rejected or pending statements below retain their original scope.

# Profile UI Terra review

Status: source accepted on 2026-09-16. Digest-pinned rollout may proceed; normal isolated-auth browser verification remains required after deployment.

## Accepted prior source direction

- Onboarding reads the master federation catalog before a personal federation library exists.
- Manual estimated-1RM identification UI is removed; existing historical estimate metadata remains intact.
- The redundant global Athlete context strip is removed.
- Own-context restoration is route aware, preserving explicit delegated Coach/Handler flows.
- A dedicated Settings route separates profile/relationships/inbox from the page/display-preferences drawer.
- Competition reload/race work is scoped to the selected person/athlete context.

## Remaining source acceptance contract

- Role-specific onboarding and workspace rendering must follow `active_role`, including a role-aware fallback when backend next-step is already done or unexpected.
- Settings role switching must use the actual `person_pk`, persist only the Person-scoped view preference, and navigate to the selected role workspace. It must not alter role membership, permissions, identity, OAuth flow, or data partitions.
- Settings profile state must reload when a Back-to-Settings restoration changes context and must not submit a profile for the former athlete.
- Coach selected view must not show Athlete training, roster/grants controls, or require Athlete basics merely because the Person also has an Athlete role.
- The Settings tab control must remain usable at 320px and 375px widths.
- Main profile tag pills must show approved tags only. Pending/rejected associations remain retained as feedback/history but are not main pills. One searchable chooser/input must either choose an approved catalog tag or submit a normalized request for a new name; do not present competing approved/request tag inputs.
- Competition success, error, and finally completion must reject stale requests after a context switch; Back restoration must reload the new partition.

## Rejected-source findings

- Mocked browser tag flow reached Settings, typed a catalog-miss name, and POSTed successfully, but no pending feedback rendered. The non-operator catalog endpoint intentionally excludes pending entries; `ProfileTags` calculates pending feedback only by looking up saved tags in that approved-only catalog. Derive the caller's pending feedback from a safe association response or contract without changing approval permissions.
- Mocked browser verification found `/settings` absent from `routePermission`. It falls through to `unmapped:read` and renders the access-denied view, so none of the Settings behavior is reachable.
- `SettingsPage` fetches settings in an empty-dependency effect. A Back-to-Settings context restoration can leave the prior Athlete's settings in state and make a subsequent profile update apply with stale UI data. Reload/reset and reject stale completions for the selected context partition.
- `SettingsPage` renders `GrantsPanel` for every selected role. `GrantsPanel` identifies an Athlete owner from role membership, so a Person who is both Athlete and Coach can see Athlete grant administration in a selected Coach view. Render that administration only for the selected Athlete view.
- The tag picker uses Mantine `Select`; its `name` changes only in `onChange`, which is limited to catalog choices. A typed unknown name cannot be submitted. One controlled searchable input must retain a normalized typed value, add an approved match, or submit a missing name. Pending feedback must remain visible after a request succeeds.
- The full-width Settings segmented-control labels include `Relationships & roster`; source does not provide a compact/responsive representation for 320px.
- The initial multi-role chooser displays `user.active_role` while its local selected-view value is empty. Choosing the already active role may not fire `onChange`, leaving no way to continue with that role. It needs an explicit working selection/continue path and mocked-browser exercise.

## Final source and mocked-browser evidence

- Independent frontend typecheck and production build passed after the Settings route permission correction.
- Mocked Playwright checks passed at 320px and 375px for the direct Settings surface without horizontal overflow. This does not claim mobile navigation coverage.
- A desktop browser flow restored from a delegated Athlete to the own Settings context through the visible Settings navigation.
- A selected Coach view did not render Athlete grant administration.
- The chooser's explicit Continue action accepted the already active selected role and reached the role workspace.
- A typed normalized catalog-miss tag request POSTed, stayed visible as caller feedback after submission, and did not render as a main profile pill. The mock modeled the production catalog contract: approved entries plus the caller's own pending association.
- The earlier pending-tag mock rejection was withdrawn because its fixture omitted the caller-scoped pending row that the production handler returns.

## Deployment evidence and live limit

- Read-only Kubernetes inspection found `powerlifting-app-frontend` generation 13 Ready 1 on `sha256:bb362bbb37e96396c9265d24bf51f13d816133c1cade2c6443ed971e64d0e2ff` and `pl-federation` generation 11 Ready 1 on `sha256:7a55a0f050ce1e7548ba2f41c649309edafeab996844543d02e208a3c8dc4f54`.
- An isolated Authentik Playwright run was started with the private acceptance identity but did not complete within the execution window. No normal-auth UI behavior, operator payload, tag approval, or operator session behavior is claimed from it.
- Reusing the existing private Echo storage state then verified `/api/auth/me` 200 and an authenticated Settings page at 320px and 375px without horizontal overflow. The same normal session read `/api/competitions` successfully with 196 rows.
- Live federation acceptance failed: authenticated `/api/federations` returned HTTP 200 with an empty `data` array and null error. The master dropdown must not be claimed accepted until this is diagnosed and corrected.
- The isolated Echo session exercised the visible mobile More menu and opened Settings. It also confirmed Settings/Profile separation, no global context strip, a Competition page that rendered its 196 returned records, and a read-only Videos surface.
- A temporary isolated tag request returned 200, appeared through the caller-scoped pending catalog contract, then was deleted through the normal API with 200 and confirmed absent afterward. No tag approval was attempted. Echo has only the Athlete role, so no normal-auth Coach/Handler chooser behavior is claimed.
- Existing private Luna state supplied multi-role coverage without any identity or role mutation: the live chooser selected Coach, Continue reached the Coach roster, visible mobile More navigation opened Settings, the role switch remained present, and the Coach roster showed no Athlete grant administration. River state was valid but single-role Coach.

## Historical pre-rollout note

The preceding pre-rollout language is superseded by the final live acceptance evidence below.

## Reconciled live acceptance

Frontend is Ready at generation 14 on `b9d2ac18f54463b2dd88d125f8fa92cb177dede6b0d048a552b03481aad72d2e`; federation is Ready at generation 12 on `97de3419f4c10df4cfcf52a628415332f74d159db2b8b6c4921ed36661547622`. An early cached federation response was empty and fresh read failed schema validation; both are resolved history. After the adapter release and narrow cache invalidation, authenticated master reads returned 23 rows on both fresh MISS and bare HIT. The real editable onboarding Profile step displayed 23 master options. Echo's separate personal library has six entries, so empty-library behavior was not exercised with a normal fixture.

Live normal-auth evidence covers Settings at 320/375, mobile navigation, Settings/Profile separation, tag request/pending/cleanup, Competition rendering, and a multi-role Coach chooser/roster path. These are live checks; the earlier local Playwright controls remain mocked evidence. Owner/operator browser data and video playback were not exercised.

## Final analytics evidence

`pl-analytics` has two containers: the unchanged FNS analytics container and the reports container on `if-powerlifting-app-backend@sha256:2f9ea2299d91289e699be33bf561f2cb3e16574f5579cad3ef49645562a4d262`. The reviewed local and live reports `dist/services/blockAnalytics.js` files have the identical SHA-256 `fff02acb50ba2e58f684a32c2a367cc7c4e47b546fece75c4e8eb4da4d0dbf44`. Normal authenticated `GET /api/analytics/blocks` returned 200 with six block entries and no error, demonstrating the routed reports path is live. No AI report generation was invoked.

River supplied the final empty-library acceptance case: normal authenticated `GET /api/federations?format=library` returned 200 with zero entries. Submitting River's unchanged Coach role advanced editable onboarding to Profile, where the master Federation MultiSelect displayed 23 options. No membership or library data changed.
