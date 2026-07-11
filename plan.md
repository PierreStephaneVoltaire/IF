• I’ll treat this as a diagnosis-and-fix-plan pass: keep a visible checklist, work each symptom through live evidence and code, mark it planned, then move on. I’ll first read the required domain/ADR material and the bug-diagnosis workflow, while
parallel read-only investigations map the UI/API failures and the Fission resource layout.

• Started `/root/code_map`

• Started `/root/live_runtime`

• Started `/root/function_resources`

• Ran git status --short && git -C utils/powerlifting-app status --short
└ M bug.md
M lambda/pod_budget/resources.yaml

• Explored
└ Read SKILL.md (diagnosing-bugs skill), CONTEXT.md
List adr

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Checklist opened:

- [investigating] Session design UI crash
- [queued] Competition design 502
- [queued] Dashboard upcoming Competition Entries missing
- [queued] Fatigue state card empty
- [queued] Percentile rankings empty
- [queued] Unauthenticated profile crash
- [queued] Weekly Analysis empty / section isolation broken
- [queued] Past Block Analysis failure
- [queued] Consolidate oversized Fission functions by domain
- [deferred follow-up] Image digests, IfNotPresent, and zero minimum replicas

The separate repo already has uncommitted changes in bug.md and lambda/pod_budget/resources.yaml; this pass will treat them as operator-owned state. I’m now building a red-capable browser/API loop for the session designer before forming a cause
theory.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The live session designer itself renders cleanly in anonymous/read-only mode, so the crash is interaction-gated rather than a basic route/data-load failure. I’m narrowing the loop to authenticated-only controls without issuing writes: enable the
UI in-browser, reuse the live Operator data for reads, then open an existing Session editor and capture the exact React exception.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Session design is now [planned].

- Repro: authenticated live browser, select Week 21. It deterministically throws TypeError: item.sets.toFixed is not a function.
- Live cause: the July 4 Session has sets, reps, and kg stored as strings, while the shared PlannedExercise contract and designer calculations require numbers.
- Fix plan: normalize stored Session exercise numerics at the program_get read boundary, normalize planned-exercise write payloads before persistence, and make the designer’s volume/display math coerce invalid legacy values defensively. The
  regression loop will load Week 21, render its volume and all Session cards, and open both edit/create dialogs without a page error.

Checklist advances to Competition design 502. The live request trace already shows that the Competition page’s /api/stats/categories dependency is the failing call, not the Competition Entry list itself; I’m verifying the exact container
packaging gap now.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Competition design 502 is [planned].

- Repro: GET /api/stats/categories returns 502 in about 50 ms; the live pod_analysis traceback is ModuleNotFoundError: pandas.
- Cause: the repository’s aggregate requirements correctly include pandas, numpy, and scipy, but the deployed mutable pod_analysis image was not rebuilt from the current archive. The existing-image build shortcut allows handler/dependency changes
  to remain undeployed.

- Fix plan: make function image rebuild identity depend on the assembled archive hash, rebuild/deploy pod_analysis, and add a container smoke check that imports every aggregate handler before promotion. Verify both /api/stats/categories and the
  full Competition design page return usable data.

Next is Dashboard upcoming Competition Entries missing. There are legacy competitions embedded in the Program and canonical Competition Entries in their own store; the domain context explicitly makes the independent Competition Entry store
authoritative, so I will plan against that source rather than guess between them.

⚠ Heads up, you have less than 10% of your 5h limit left. Run /status for a breakdown.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Dashboard upcoming Competition Entries is [planned].

⚠ Heads up, you have less than 5% of your 5h limit left. Run /status for a breakdown.

• Dashboard upcoming Competition Entries is [planned].

- Repro: the Dashboard requests country=Canada&state=ON and receives zero rows; the same canonical endpoint with no filter returns four future selected Competition Entries, all stored as venue_country=CA.
- Cause: ranking-location settings are incorrectly reused to filter the Athlete’s own Competition Entries, and the stored value format also differs (Canada versus CA).
- Fix plan: load the Athlete’s complete canonical Competition Entry list on the Dashboard, then apply only lifecycle/date filtering locally. Keep ranking geography isolated to percentile requests. Verify the four current future selected Entries
  render while available, skipped, completed, and past Entries remain excluded.

I’m moving to Fatigue state card empty. This is coupled to the same stale analysis image, but I’m checking its own cache/status behavior because a successful dependency rebuild alone may leave poisoned “complete” cache rows in place.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Fatigue state card is [planned].

- Repro: the Dashboard’s fatigue_readiness section reports status=error with the live scipy import failure, so no fatigue_index or component payload exists to render.
- Cause: deterministic fatigue computation never starts in the stale pod_analysis image; this is not an insufficient-data result from the Athlete’s Sessions.
- Fix plan: include scipy in the rebuilt aggregate image and treat a section-level error as an explicit retryable card state. After deployment, invalidate/requeue only fatigue_readiness for the block window and verify the card receives
  fatigue_index plus components without waiting on overview/workload.

Next: Percentile rankings. I’m testing both the categories lookup and a known Athlete ranking request, then checking whether the rankings dataset has any second failure hidden behind the missing pandas import.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Percentile rankings is [planned].

- Repro: the known Athlete request to /api/stats/ranking_percentile returns 502; its handler fails at import before reading data. Categories fails at the same point.
- Cause: pandas/numpy are absent from the stale aggregate image. The required OpenPowerlifting CSV is present in S3 and the function has the configured bucket/read path, so there is no conflicting rankings data source.
- Fix plan: rebuild pod_analysis with the aggregate requirements, synchronously warm the shared dataset once per pod, and smoke-test categories plus global/national/regional percentile responses before exposing the image. Verify both Dashboard
  rankings and the dedicated Rankings page with the Athlete’s current totals.

Next: Profile page crashes when unauthenticated. I’m reproducing that in a clean browser context and tracing which authenticated identity assumption is dereferenced.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Unauthenticated profile crash is [planned].

- Repro: a clean browser at /profile renders a blank root and throws Cannot read properties of undefined (reading 'localeCompare').
- Cause: public profile handlers build correct VideoLibraryItem wrappers, then mistakenly return only each inner raw video. The anonymous page sorts them as wrappers and dereferences missing session_date / video.
- Fix plan: return the full wrappers from both current and nickname public-profile handlers, keep the frontend sorter tolerant of missing legacy dates, and add anonymous profile coverage with the live public video shape. Acceptance is a rendered
  public profile, sortable lift videos, and zero page exceptions while signed out.

Next is Weekly Analysis data and independent section loading. I’m separating the backend compute failure from the frontend orchestration failure so the plan fixes both rather than merely making the current image work.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Weekly Analysis is [planned].

- Repro: the live Weekly tab queues all five deterministic sections; each independently returns status=error for missing scipy, and the UI collapses to one “No analysis data” message.
- Causes: the stale analysis image prevents every computation, while the frontend still uses Promise.all and one merged data gate, so a transport failure or zero successful payloads hides even frontend-local sections.
- Fix plan: rebuild pod_analysis; fetch/update section state with Promise.allSettled; render overview, fatigue/readiness, peaking, workload, and alerts behind their own loading/error/retry boundary; keep frontend-derived max/weight/nutrition
  trends visible regardless of backend status. A failed section must not remove successful or local sections, and retry must target only that section.

Next: Past Block Analysis. Live logs indicate a separate routing regression from Weekly Analysis, so I’m reproducing its block endpoint rather than assuming the dependency rebuild fixes it.

────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Past Block Analysis is [planned].

- Repro: the known off-season#2 block endpoint returns 502; backend logs show Fission 404 for weekly_analysis.
- Cause: block analytics still calls the removed standalone route instead of pod_analysis with function: weekly_analysis. It also bypasses valid block cache rows and recomputes every request.
- Fix plan: use a grouped analysis invoker, restore fingerprinted block-cache read/write behavior, and verify both cached and forced-refresh paths for block_767584cb209385.

All reported functional issues now have reproduced causes and concrete fixes. I’m closing the last checklist item by aligning consolidation with the project’s existing domain-function ADRs and separating the requested resource work from the later
digest/IfNotPresent/zero-replica change.

───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Final checklist state:

- [planned] Session design crash
- [planned] Competition design 502
- [planned] Dashboard upcoming Competition Entries
- [planned] Fatigue state
- [planned] Percentile rankings
- [planned] Unauthenticated profile
- [planned] Weekly Analysis independence
- [planned] Past Block Analysis
- [planned] Domain-function consolidation and request reductions
- [deferred by request] Digest references, IfNotPresent, and MinScale=0

The consolidation target is 18 physical Function CRs while preserving operation-level HTTP/MCP schemas, so grouping does not make tool calls ambiguous. It also removes the current 3-CPU scheduling blocker and fixes the build process that deployed
pod_analysis without its dependencies.

•
