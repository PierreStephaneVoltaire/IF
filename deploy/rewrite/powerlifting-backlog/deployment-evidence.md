# Deployment evidence

## Profile and Settings correction — 2026-09-16

Frontend `b9d2ac18…` generation 14, Federation service `97de3419…` generation 12
and analytics reports `2f9ea229…` in deployment generation 22 are deployed and
Ready. All 18 portal Deployments are Ready. Gateway, analytics FNS and protected
IF runtimes remain unchanged. Terra accepted source, contract-faithful mocked
checks and normal Authentik live checks for separate Settings, selected-role views,
tags, Competition rendering, 320/375 pixel layout and mobile navigation. A Coach
with zero personal-library entries sees all 23 master Federation options. Routed
analytics returns six Blocks; the reports module matches the reviewed compiled
hash. Workspace build/typecheck and focused tests pass.

See [release](profile-ui-release.json), [review](profile-ui-terra-review.md),
[check results](profile-ui-terra-live.json) and [inventory](profile-ui-runtime-inventory.json).
Rollout manifests contain the exact new pins and prior frontend/Federation
rollback pins. The initial Packer build also updated the frontend `latest` tag;
no deployment references that tag, and no AWS object was deleted. Archived Block
labels and cached report presentation are corrected in the reports sidecar. The
final frontend query-only correction preceded its final artifact gate and was
subsequently accepted; the other scoped rollouts followed their review gates.
Operator browser data and video playback remain unverified. Mocked checks,
live checks and the original external acceptance limits remain separately recorded.

## Production visibility recovery — 2026-09-16

A reviewed conditional pointer-only repair restored the operator's current
Program from empty v021 to v020. All 453 Sessions, both Program records, 41 video
references and 196 Competition Entries were retained. Independent snapshot
hashes verify Programs and Sessions are unchanged. The pointer's allocation
version remains 21; its revision is now 1. Canonical statuses remain 407 completed
and 46 planned. Normal operator browser verification remains unavailable.

The [sanitized recovery record](production-visibility-recovery.json) and
[Terra review](production-visibility-recovery-review.md) distinguish storage
evidence from browser acceptance. An additional in-pod verification probe caused
one Program pod restart from memory exhaustion; the pod recovered, and that
probe was stopped. The earlier zero-restart inventory is historical.
Federation, role, Settings, tags, Competition loading and historical Block-label
corrections have separate implementation/deployment evidence above.

## Current Discord callback repair — 2026-09-15

Gateway `b688e943a910ec37b23285f75586f0a7b8f2c346c08653e1509b6b5520130f62`
is Ready at generation 31. Direct Discord login again uses its original configured
application callback alongside Authentik. Luna implemented and deployed; Terra
accepted source and live checks. Actual Passport tests, workspace checks, direct
client/callback browser verification, invalid-state rejection and a fresh
Authentik login pass. Live Discord consent/identity completion remains unverified.
All 18 portal Deployments are Ready; frontend and domain-service pins are unchanged.
See [repair evidence](discord-login-correction.md), [release](discord-login-release.json)
and [independent review](discord-login-review.md). The previous gateway pin and
Discord authorization-dispatch acceptance below are historical.

## Prior entry and mobile correction — 2026-09-15

The operator's correction is implemented, deployed and accepted by Terra.
Current gateway is `8740348739cfbce86ef59e800e6c80146dc36897067a57dbcc9413d100ff5b4e`
(generation 30); frontend is `5bb25bdb27864d990ecd2b4587a458226eb9f1cc86aedb7396b076afa45c64fe`
(generation 12). All 18 portal Deployments are Ready. Both login choices,
dedicated guest landing, scoped notices, compact mobile context and corrected
Dashboard width have live evidence. Fresh Authentik login and actual Discord
authorization dispatch pass; a completed Discord identity login is not claimed.

The [scoped record](entry-mobile-correction.md), [sanitized evidence](entry-mobile-summary.json)
and [final review](entry-mobile-review.md) supersede the earlier frontend/gateway
pins and guest-entry acceptance below. Domain-service pins and earlier feature
checks retain their original dates and scope. The Cloudflare and operator-tag
external acceptance limits remain unchanged.

## Prior full-backlog checkpoint — 2026-09-15 10:45 UTC

The approved release is applied in the existing environment. Luna implemented,
deployed and tested; Terra reviewed the changes. The current inventory records
all sixteen domain services, gateway and frontend Ready with observed generations
and zero restarts. The final scoped portal rollouts preserved the IF API and
single native Codex worker. Historical pins and unfinished-work statements below
are superseded by this checkpoint and its linked evidence.

### Current immutable pins

| Runtime | Repository | SHA-256 digest |
| --- | --- | --- |
| Gateway | if-powerlifting-app-backend | d4cbce473ab1dd4f6d7f4e7105dbc47f8da362a708f179af43b000369e056cd0 |
| Analytics, Profile, Videos | if-powerlifting-fns | 17a58b454b834eccf2f3033598fc5718c15cd4cf2d66b2516cfcd0af9a0076ba |
| Analytics reports sidecar | if-powerlifting-app-backend | c868c906c383fd5afd6018e78ce774c5af19354b98b68521fa379da3a5d1b510 |
| Program, Templates | if-powerlifting-fns | da1aca5eeeb67bad1c6334f58f32d6ac6504551af34fa57bbc3c62d9076f426a |
| Performance | if-powerlifting-fns | 6d0a745a531b1deba442b263f3bd65013deb69228f9138e35c16885c7b01016a |
| Other ten domain services | if-powerlifting-fns | 008f6c22e6d99c087e8ba3e0ecf1324ce8da8d2f2b198acba2148af2e0282da4 |
| Frontend | if-powerlifting-app-frontend | a7aad69a7c399a115bc4c5b69510ef8a419728d1d86cf0ab1766c72b9d405bd6 |
| IF API | if-agent-api | 3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f |
| Native worker | existing worker | ca816dfdbe7b6083d55adb61c5123434d7de28c7b10d7affb805d43f010c5636 |

The ECR registry is `429310424269.dkr.ecr.ca-central-1.amazonaws.com`.
[Full runtime inventory](final-runtime-inventory.json) and
[manifest reconciliation](manifest-reconciliation-summary.json) record container
names, generations, exact references and protected runtime checks. Kubernetes
image IDs may be platform/configuration digests; the table lists ECR manifest
pins. Executable rollout and rollback manifests retain the reviewed mixed groups.

### Verification

- **Local regressions:** 253 service tests and 16 subtests passed, with nine
  warnings. Workspace typechecks, required builds and focused checks passed before
  their scoped deployments. Terra independently reran eight rollout tests and
  matched the package hash. The manifest self-test and dry run cover 18 portal
  patches; the dry run made no mutations.
- **Live HTTP/MCP:** 16/16 services and 22/22 selected signed operation checks
  passed. Source review covers all 221 manifest operations with no permission-map
  gaps. These counts are separate from browser, identity and processing tests.
- **Training:** sixteen Block transition checks cover complete, start-next,
  combined, settings, unfinished status, replay and revision conflicts.
  Template append/replace/new-Block preserve logged work, independent Competition
  Entries and distinct Session identities. Exact raw HTTP/MCP replay performs no
  second mutation; changed payload with the same key is rejected.
  [Block proof](live-block-summary.json), [Template proof](live-template-replay-summary.json).
- **Identity, navigation and offline:** genuine Authentik logins and later profile
  edits pass. Forged identity and mismatched OAuth state are denied. Real browser
  checks cover role landing, guest Search/About/back restoration, Athlete context,
  same-day Session selection, logged edits, 44px targets, scroll, authored-note
  ownership, retained conflict drafts and delegated-cache removal after revocation.
  [Frontend proof](live-final-frontend-summary.json),
  [revocation proof](live-frontend-revocation-summary.json),
  [blocked sync and actual Attempt conflict](live-offline-conflict-summary.json),
  [onboarding/social proof](live-onboarding-social-summary.json).
- **Relationships:** distinct Coach and Handler approvals produce one 200 and one
  409. Confirmed replacement, old-Coach denial, independent peer reads, rejection,
  cancellation, stored competition expiry and replay-deduplicated notifications
  pass. [Coach race/replacement](live-distinct-coach-summary.json),
  [Handler race/restoration](live-handler-race-summary.json).
- **Reports:** public/OIDC generation succeeded through the existing native worker.
  Repeated owner and exactly scoped read-only delegate reads return the identical
  cached response hash and generation; cache-record count stays 148. Delegate
  generation returns 403 and unknown caches return 404 without jobs. A narrower
  source scope correctly cannot reuse the broader report. Historical Markdown/XLSX
  exports and backend CSV/native parse/review/apply passed separately.
  [Public report proof](live-public-report-summary.json).
- **Maxes and Program freshness:** target-max write/read/replay/restoration passes.
  A signed normal native-domain current-max mutation and restoration appear at
  the identical ordinary portal URL immediately, with source revisions 64/65/66;
  ready media remains unchanged. This is typed-service mutation plus authenticated
  portal read evidence, not a claim that Codex generated the mutation.
  [Target max proof](live-performance-summary.json),
  [Program coherence proof](live-program-cache-coherence.json).
- **Media:** ordinary backend-only uploads, authorized GET/HEAD/Range, failed-file
  retry and duplicate confirmation pass. A 180-second recording becomes ready;
  a 181-second replacement fails while preserving the old ready video. Successful
  replacement keeps its assigned target revision. Ready notifications deduplicate;
  owned removal and replay clear only the intended media.
  [Media proof](live-final-media-summary.json). The corrected actual concurrent
  race records B ready while A is processing, then A completing without replacing
  B. [Concurrent processing proof](live-stale-media-race-summary.json),
  [final Terra review](final-release-review.md).
- **Lift Profile context and guidance:** ten failure nodes and 160-character input
  pass; 11 nodes and 161 characters are rejected. Distinctive nodes appear through
  genuine Handler and Coach profile-context reads and signed native HTTP/MCP.
  Revoking the test Coach grant returns 403. On the deployed browser page, bar/unit
  interactions change guidance from 120.0 kg to 100.0 kg to 120.4 kg and controls restore.
  Profiles restore after tests and per-set failure-reason data is preserved.
  Older simulated 130/230/custom-50 assertions are not deployed evidence.
  [Lift Profile proof](live-lift-profile-context-summary.json).

The gateway retains its existing AWS credentials under `/home/nodejs/.aws` with
narrow read access. The thumbnail Lambda duration fallback is applied and active.
CloudFront distribution `EYF8UFQTP2DCE` is disabled; invalidation
`IE71FSYP9K4VCIH1WBN5OVU3WM` is complete. Dedicated tag/notification tables and
relationship inbox/sent/roster indexes are active. No AWS resources were deleted.

### Fixtures, cleanup and remaining acceptance

Source operator records and copied media were preserved. Isolated test partitions
retain revision/relationship history and four Echo report Sessions. Created Coach
grants were revoked, the conceptual Echo Handler was restored, and all 21 search
fixtures are private again. New owned media is removed through existing app
operations. Credentials and raw private Program responses are excluded from this
release folder. Exact unused task Docker images were removed after verifying ECR
publication and no Docker container references; k3s containerd, rollback archives
and unrelated images remain. [Cleanup proof](final-local-image-cleanup.json).

The **500 MiB public-route test awaits the Cloudflare allowance upgrade**.
**Positive operator tag approval, catalog migration and approved-tag AND/OR
acceptance await genuine operator access**, which the user confirmed unavailable.
Neither is marked verified. The final Terra review accepts the concurrent
processing and actual Lift Profile context/guidance proof and finds no material
source-level authorization, data-loss or integration regression within its
reviewed scope. The per-feature backlog records each item's actual evidence.

## Historical deployment sequence


- ECR lifecycle policies: applied successfully to the existing `if-agent-api` and `if-powerlifting-app-backend` repositories.
- API foundation: `/tmp/if-release-api-foundation.tfplan` applied successfully; Terraform reported `5 added, 6 changed, 1 destroyed`. The destroy was the reviewed `null_resource.rollout_restart_main_api` replacement. API digest `sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f` is ready and `/health` is serving.
- Request table: `if-powerlifting-requests` is active with `InboxIndex`, `RosterIndex`, and `SentIndex` active.
- Portal rollout: the first gateway candidate `sha256:27c6ddb82e236602a05ddb3c4af6a854bb31c29dbfeba1a97865802be5c4b1b9` failed startup with `OAUTH_JSON_ATTRIBUTE_COMPARISON_FAILED` and was rolled back. Terra diagnosed the public Authentik issuer scheme and custom internal fetch. A route-scoped `authentik-public` HTTPS forwarded-proto filter was applied, `AUTHENTIK_INTERNAL_URL` was removed, and the gateway now uses standard `openid-client` discovery with strict issuer, nonce, audience and subject validation.
- Final gateway image `sha256:e96ebc034ddc3d4655b2b326158917b4a6a6251f490ab38bb20a4b2aa91c70c1` is live. As verified at 07:25 UTC, all sixteen service Deployments use reviewed image `sha256:008f6c22e6d99c087e8ba3e0ecf1324ce8da8d2f2b198acba2148af2e0282da4`, Analytics reports uses `sha256:60c83f4c17f59b32ac19e7b1da5894d4ee2fdc9b17e1e2d0942ce1c3987cc69e`, and the frontend subsequently received `sha256:a0b96a7b99b871b89a2b3bcc2f1a5c96480f69a84268e6d274cd6fee635eea8f`. All 18 generations are observed with one replica Ready.
- Callback correction: the Powerlifting route now supplies HTTPS forwarded-proto so Express issues its secure session cookie. The reviewed Passport strategy sends a random state and retains openid-client validation, fixing Authentik's empty-state response. Real Luna OIDC login completed with the verified provider-subject and Person/Athlete mapping. Forged identity was denied and a mismatched callback state was rejected. Evidence: `/tmp/oidc-luna-auth-evidence.json` and `/tmp/oidc-callback-checkpoint.json`. Earlier gateway `e9d0...` remains historical.
- Media: regenerated targeted plan matched `0 add, 3 change, 0 destroy`; apply completed on existing CloudFront distribution `EYF8UFQTP2DCE` after IAM and thumbnail Lambda updates.
- CloudFront invalidation `IE71FSYP9K4VCIH1WBN5OVU3WM` completed for `/*`. API/backend health checks returned 200; health, OpenAPI and MCP transport checks passed for 16/16 services. The legacy data hook’s unsigned `operator` probe was denied by the deployed principal authorization and is recorded separately from acceptance. Remaining functional acceptance is in progress. Cloudflare allowance upgrade and the 500 MiB test remain deferred.
- Independent deployed public-boundary acceptance passed for known private profiles, Programs, grants, notifications, authored originals, media GET/HEAD/Range, and forged HTTP/MCP principals. The old exact CloudFront media hostname no longer resolves and the exact S3 object denies anonymous access. Public profiles exposed no nonempty unpublished domain data. Evidence: `/tmp/public-boundaries-live-acceptance.json`.
- Independent native canary passed unauthorized denial, duplicate-job idempotency, a scoped kg-to-lb tool call, and a follow-up on the same native thread. The worker returned to zero active jobs. Evidence: `/tmp/native-backlog-live-acceptance.json`. This does not establish report generation/cache or import acceptance.

## Authenticated acceptance checkpoint, 07:30 UTC

- Session identity: all sixteen services received the reviewed shared-store validation and deterministic per-application Template identity fix. Live duplicate Program writes and Block transitions return typed HTTP/MCP 409 without changing the revision; ambiguous legacy lookup returns 409 and a unique historical Session remains readable. Local suite: 236 tests and 16 subtests passed. The generic legacy smoke harness still has stale fixture/parser and internal-only operation assumptions; its whole-run result is not a pass. Evidence: `/tmp/session-uniqueness-checkpoint.json`.
- Block lifecycle: sixteen deployed checks cover complete, start-next, combined flow, stable Block identities, next-Block settings, unchanged unfinished archived status, replay and revision conflicts, plus MCP rename/reread. Sanitized evidence: [live Block summary](live-block-summary.json). The original run did not establish Session identity uniqueness; the subsequent shared-store fix and checks above address that defect.
- Relationships: twenty-one live assertions cover genuine Athlete/Coach onboarding, private favorites, requests/cancel/history, tied approval and expiry, replay, competing approvals, confirmed replacement, revocation, publication projection/replay/restore, search privacy and normalized pending tags. A distinct rival Coach account and positive operator catalog approval were not established by this run. Evidence: `/tmp/social-live-acceptance-checkpoint.json`.
- Authored notes and offline: twelve corrected browser assertions cover private note editing, partitioned drafts/queue, reconnect/reload, a real revision conflict without overwrite and context restoration. Separate live authorship checks cover private/shared revision separation, explicit author update, Athlete detach and revoked-author denial. The observed delegated-cache revocation defect has a reviewed source fix; frontend publication is complete and post-fix browser acceptance remains in progress. Earlier failed Attempt-modal probes and pre-fix revocation artifacts are not passing evidence.
- Media: real backend multipart upload, idempotent retry/confirmation, processing readiness, malformed-file failure and same-ID retry, lift-slot replacement, authorized HEAD/Range, anonymous/cross-Athlete denial and test-owned cleanup passed. Browser capture observed six mutating requests and zero storage requests or storage upload URLs. The thumbnail duration fallback was reviewed and applied as one in-place Lambda update. Real concurrent stale-processing acceptance was not run; CAS checks remain local/injected. Full 500 MiB public-route acceptance remains blocked by the pending Cloudflare upgrade. Evidence: `/tmp/live-acceptance-echo-checkpoint.json`.
- Exports/imports: real historical Markdown (31,721 bytes) and XLSX (257,433 bytes) exports returned valid attachments. Backend CSV upload, native parse, review, pending listing and apply succeeded on isolated Echo, with two stable imported Sessions and the prior Program version unchanged. Analytics alerts/result shape and gateway mapping of already-applied imports are open bounded fixes; full report/cache and repeated Template target acceptance remain in progress. Evidence: `/tmp/report-import-export-live-checkpoint.json`.

Private fixture responses, credentials and session files remain outside this release folder. Evidence references distinguish deployed checks from local/injected checks and pre-fix failures.

## Follow-up deployments and checks, 07:40 UTC

Frontend `sha256:a0b96a7b99b871b89a2b3bcc2f1a5c96480f69a84268e6d274cd6fee635eea8f` passed workspace typecheck/build and reached generation 9/9, one Ready replica and zero restarts on the exact image. The real post-fix browser run removed the revoked delegated cache, retained its draft and pending mutation, preserved the other partition, restored the Person's own context and denied revoked Program access with 403. The mutation stayed pending without replay; a blocked-status transition and remaining-peer/public-read matrix were not established by this run. Sanitized evidence: [frontend revocation summary](live-frontend-revocation-summary.json).

Analytics alone subsequently received reviewed shared candidate `sha256:ef34dcd974ba7ddf4644daf7335d66003294a615ffbcf31c2165c8dc8c68e0a0`, correcting `analysis_section.alerts` to the established array result. The other fifteen services retain `008f6c22…`. The weekly bundle now returns 200. Real report generation/cache/reference and Block-comparison acceptance remain active. The gateway import-error correction is local and awaiting independent review before publication.

Terra's [operation security review](operation-security-review.md) found no actionable source-level authorization defect: all 221 manifest operations are mapped, with signed principals, current Profile access, report read/write separation, filtered exports and authorized media/notes boundaries. This is source review evidence, not 221 live operation tests.

At 07:48 UTC the follow-up browser worker additionally verified revoked synchronization returns 403, marks the queued edit blocked and retains it; public profile/search and the Person's own partition remain readable. The actual Attempt modal retained the typed Attempt and stayed open with a conflict notice after a real stale-revision 409; restoring the server state succeeded and the queue cleared. Training navigation and Lift Profile checks remain active. Source: `/tmp/browser-profile-final-acceptance.json`.

Gateway `sha256:f38de3aa5fd1dd1f74b7e07d8789f2381909d75a96e315adcd1d5ca7e15c0e05` is subsequently deployed and Ready, preserving the validated OIDC implementation. The reviewed import adapter now preserves the domain error: genuine Echo OIDC replay returns 422 with no mutation. Analytics weekly bundle returns 200. Native internal report generation/dedup/cache/reference checks passed separately; public OIDC generation still needs a suitable logged historical fixture, and Block comparison has an unresolved edge 502 observation. Source: `/tmp/analytics-reports-deploy-checkpoint.json`.

Fresh final Terra review subsequently identified a report permission defect omitted by the earlier operation-map pass: `analytics.blocks_get` requires write permission even for existing cached Block analysis, and its sidecar path does not forward a cache-only mode. Read-only cached access must be corrected without allowing generation. Terra also observed Block-analysis invalid-result errors in the reports sidecar; this supersedes the earlier tentative edge-only explanation. Both findings are assigned to the analytics Luna worker for focused fixes, independent review and deployment. The earlier source-review verdict is retained with a supersession note.

The operator confirmed that operator access is unavailable right now. Positive catalog approval and approved-tag search acceptance therefore remain unverified; no approved vocabulary or operator identity was fabricated. This is separate from the pending Cloudflare allowance/full-size upload test.

The refreshed service harness passed its selected twenty low-level checks, but fresh Terra rejected removing exposed `program_list` from coverage: real HTTP and MCP calls fail on normal UUID-suffixed Program keys when `meta.version` is absent. This is a compatibility defect, superseding the earlier fixture-only characterization. A Luna worker owns the handler correction, restored HTTP/MCP assertions, review and rollout. The selected twenty checks are not final generic acceptance.

## Weekly and max-contract follow-up — 09:16 UTC

Analytics is Ready on service digest
`sha256:3ec0b8fb5db4add62e5f951b2f6608e16eb0838d6c84669db254580295381f23`
and reports digest
`sha256:c868c906c383fd5afd6018e78ce774c5af19354b98b68521fa379da3a5d1b510`.
The actual public weekly endpoint returns HTTP 200 with flat fields and no bundle
wrappers. The current Block cache returns 200 and an unknown key returns 404;
this owner-scope check alone does not establish delegated read-only access or
no-generation behavior. Those checks and a successful public native report are
still active. Existing empty-current-Program insufficient-data responses are
recorded as such, not as successful generated reports.

[Fresh boundary review](final-rollout-boundary-review.md) accepted the gateway's
existing mount and two-file ACL after safe zero-byte opens and actual AWS SDK
resolution. Its earlier `test -r` failure was a shell-probe artifact and is
withdrawn. [Max-target review](max-target-contract-review.md) accepted the handler
result and legacy replay backfill: the stored marker timestamp is exactly the
Program's original transaction timestamp. The performance-only rollout and
authenticated write/read/replay acceptance are active.

## Final acceptance diagnosis and manifest reconciliation — 09:26 UTC

Fresh Terra traced the earlier delegated report 403. The approved peer grant is
present and the live Profile evaluator returns its read permissions. A new
authenticated cache-only request succeeds. The legacy grant-list endpoint was
the wrong directional query for that diagnosis; no authorization patch is
needed. [Detailed diagnosis](report-acceptance-diagnosis.md). Actual owner
generation and delegated hit/miss/no-generation tests continue using four
completed Sessions across four weeks in the isolated Echo Program.

The executable rollout manifest and candidate record now represent the live
mixed image groups, including performance `6d0a745…`. JSON validation, rollout
self-test and an 18-deployment dry run pass, with no Kubernetes mutation. Current
image pins are retained, as are API/worker and rollback pins.
[Manifest reconciliation proof](manifest-reconciliation-summary.json).

## Performance and onboarding/social writes — 09:34 UTC

The performance-only rollout is Ready on
`sha256:6d0a745a531b1deba442b263f3bd65013deb69228f9138e35c16885c7b01016a`.
Twenty-four focused tests pass. Actual target-max PUT, GET, exact replay, one
revision advance and target restoration pass.
[Performance deployment proof](live-performance-summary.json).

The earlier lift-media artifact overclaimed current-max persistence, failed
processing and retry coverage; those statements are withdrawn pending actual
checks. Fresh Terra confirmed the form-video delete 422 is a product defect: the
handler requires a Session for a Lift Profile allocation. The bounded fix and
actual 180/181-second, replacement, current-max and notification checks are active.

Actual River onboarding writes pass staged Athlete-role setup, incomplete-basics
status, dated kilogram maxes with explicit estimate flags, later basics and
profile/federation edits, and restored Coach role/profile. The isolated dated
basics remain as authorized test history. Real relationship rejection/cancel,
rejection replay and notification deduplication pass.
[Sanitized onboarding/social evidence](live-onboarding-social-summary.json).

Actual Echo public/OIDC report generation succeeded as job
`52b2095499d340f8acea78517ec957b3`, generation
`b9c0a41764a3d9dd84696979b66717d3c4a36b097e44fb092c7f0a93b59248f1`,
with matching saved source fingerprint. Delegate cache-hit and invalid-Block
handling remain under independent review; this success does not close those
checks. Four completed isolated fixture Sessions remain for the next checks.

## Distinct-Coach race and final media image — 09:47 UTC

The real three-Person Coach test used Echo as Athlete and distinct River/Luna
Coaches. Concurrent approvals returned 200/409, unconfirmed replacement returned
422, explicit replacement succeeded, the old Coach lost access with 403, and
Luna's independent peer read remained 200. Created Coach grants were revoked;
post-cleanup active Coach count is zero. Existing peer/Handler grants and Echo's
Program were preserved. [Race and cleanup evidence](live-distinct-coach-summary.json).

The accepted form-media removal fix is deployed to `pl-videos` on
`sha256:6c4e404b2a9f960431a61f77429d8782cde055f8d656188142ead4bf2a5398c2`.
The image contains matching hashes for the accepted form-removal and correlation
404 translations. Analytics will reuse this verified image while retaining its
reports sidecar. Actual media and final report-cache acceptance continue.

## Central permissions, media and Handler closure — 10:13 UTC

The remaining delegated Block 403 came from the central Profile deployment's
older permission map. Only Profile was updated to the accepted shared `17a58b…`
image. Genuine Luna with matching read scope now gets cached current Block 200
and unknown Block 404; generation remains 403. The owner and delegate read the
same saved `b9c0a417…` report; response hashes match and cache records stay 148.
[Report proof](live-public-report-summary.json),
[central evaluator diagnosis](central-profile-cache-review.md).

Live media now proves 180-second readiness, 181-second processing failure with
old-ready preservation, same-ID retry, exactly one ready notification, form
removal/replay 200 and cleared slot state. The actual native current-max writer
changes/restores `current_maxes` with increasing revisions while retaining the
exact ready recording. Source hashes for the final `17a58b…` form-removal edge
match the independently reviewed file; 19 video tests pass.
[Media proof](live-final-media-summary.json),
[source closure](media-source-closure-review.md).

The same run exposed seven-day Program HTTP caching after native writes. The
reviewed fix removes caching from the two Program GET routes, preserving write
invalidation, report caching and frontend offline data. Gateway deployment and
identical-URL live verification are active. A query-busted read is not accepted
as proof of this fix. [Review](program-read-cache-review.md).

Actual Handler approvals returned 200/409. The winner was revoked, the loser
cancelled, and the original Handler arrangement restored through normal requests
with the same competition tie; final active Handler count is one. River's Coach
role, peer grants and source Program were preserved.
[Handler race proof](live-handler-race-summary.json).
