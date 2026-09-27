# Final scoped Terra review — 2026-09-16

Accepted with the limits below. This record consolidates Terra's independent
source, artifact and live findings; [earlier review iterations](profile-ui-terra-review-history.md)
are historical. Machine-readable results are in [live evidence](profile-ui-terra-live.json).

## Implementation and tests

Profile/privacy, relationships and inbox are in Settings, separate from the page
preferences drawer. Selected Athlete/Coach/Handler views remain separate. Tags
use approved pills and one add/request modal; pending requests retain their
association and display submission feedback. Settings restores its own context,
and Competition loads reject stale responses. The global context strip and
manual estimated-1RM controls are removed without rewriting historical metadata.

Federation reads scan the existing hash-only master table and omit absent
optional fields that violate the result schema when emitted as null. Personal
library reads explicitly use `format=library`. No federation records were changed.

Block labels resolve active metadata, preserve custom names and use historical
labels for archived generic blocks. Cached reports refresh presentation fields
while preserving generated content and keys. The actual analytics reports
sidecar executes this code; the gateway candidate was not deployed.

Workspace typecheck/build passed. Focused checks passed: five Federation, two
Block-index, eight Template-integrity and fourteen ProgramStore transition tests,
including an empty next Block preserving external Sessions. Mocked browser checks
cover tag input/pending feedback, context restoration, role confirmation and
320/375-pixel Settings layout; they are distinct from live checks below.

## Deployed acceptance

- Frontend `b9d2ac18…`, generation 14; Federation `97de3419…`, generation 12;
  analytics reports `2f9ea229…`, deployment generation 22: Ready.
- Normal Authentik sessions verify Settings at 320/375 pixels, visible mobile
  navigation, separate Profile settings, no global strip, and Competition rendering
  with 196 returned records in the isolated account.
- An existing multi-role Person selected Coach, continued to its roster and opened
  Settings without Athlete grant controls. Memberships were unchanged.
- An isolated tag request returned pending feedback and was removed afterward
  through the normal API. No operator approval was fabricated.
- Master Federation reads return 23 canonical records on fresh MISS and ordinary
  HIT after narrow cache invalidation. The live profile form displays 23 options.
  A second normal Coach fixture has zero personal-library entries and its editable
  Profile also displays all 23 master options; memberships/library were unchanged.
- Routed `/api/analytics/blocks` returns 200 with six entries. The running reports
  `blockAnalytics.js` hash matches reviewed output:
  `fff02acb50ba2e58f684a32c2a367cc7c4e47b546fece75c4e8eb4da4d0dbf44`.

The final one-line frontend library-query correction was deployed before its
final artifact gate and subsequently accepted. Federation and analytics reports
rollouts followed their gates. Gateway `b688…`, analytics FNS `17a58…`, IF API and
the native worker remain unchanged.

## Limits

Operator browser data and video playback were not exercised. Storage integrity
is independently recorded in [recovery evidence](production-visibility-recovery.json).
Full 500 MiB upload acceptance still awaits the Cloudflare upgrade; genuine operator tag
approval and full Discord consent remain the previously recorded external limits.
