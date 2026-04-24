
# PHASE 2 — UI CHANGES


## Plan 17 — Plain-English Alerts Layer

**Goal:** Above the raw metrics on the Analysis page, render a small ordered list of coaching-language alerts generated deterministically from the analytics response. No AI. Nerd view still available via formula accordion.

**Files:**
- `frontend/src/components/analysis/AlertsStrip.tsx` (new)
- `frontend/src/pages/AnalysisPage.tsx` (mount at top)
- `tools/health/analytics.py` (extend with `generate_alerts` that emits structured alerts)

**Alert structure:**
```ts
interface AnalyticsAlert {
  severity: 'info' | 'caution' | 'warning'
  source: 'acwr' | 'fatigue' | 'readiness' | 'projection' | 'specificity' | 'banister' | 'decoupling' | 'monotony'
  message: string          // plain-English coaching line
  raw_detail: string       // short technical line for expand-on-click
}
```

**Deterministic mapping table (extend with every formula plan):**

| Condition | Severity | Message |
|---|---|---|
| `fatigue_index >= 0.60` and trending up | warning | "Fatigue is elevated. Consider a lighter session or deload this week." |
| `acwr_composite > 1.50` and phase intent ≠ overreach | warning | "Training load jumped sharply. Monitor recovery closely." |
| `acwr_composite > 1.50` during planned overreach | info | "Load spike is consistent with your planned overreach." |
| `decoupling_fatigue_dominant` for 3+ weeks | warning | "Strength is flat but fatigue is climbing. Accumulated stress is outpacing adaptation." |
| `tsb_today < -30` | warning | "You are in deep overload. Performance should rebound after a deload." |
| `tsb_today` in [+5, +15] and `weeks_to_comp <= 2` | info | "You're in the peaking window for your upcoming meet." |
| `specificity_below_expected` | caution | "More competition-lift practice recommended given how close your meet is." |
| `high_monotony` | caution | "Your daily training load is very uniform. Consider more contrast between hard and easy days." |
| `projected_total >= qualifying_total` (Plan 25) | info | "You're projected to exceed the qualifying total for this meet." |
| `projected_total < qualifying_total` with < 6 weeks out | caution | "Your projected total is below the meet's qualifying standard." |
| `readiness < 50` for 2+ weeks | warning | "Readiness has been low consistently. Check sleep and stress." |

Each alert is clickable → expands to show the raw metric value and links to the formula accordion entry.

---

## Plan 18 — Peaking Readiness Timeline Visualization

**Goal:** Single chart that shows TSB trajectory from Plan 8, projected meet date, expected peak window, and current position. Answers "Am I on track?" visually.

**Depends on:** Plans 8, 11, 14

**Files:**
- `frontend/src/components/analysis/PeakingTimeline.tsx` (new)
- `frontend/src/pages/AnalysisPage.tsx` (mount above Projections)

**Visual elements (single unified chart):**
- X-axis: date, from program start through comp date + 2 weeks
- Y-axis (left): TSB value
- Y-axis (right): Specificity ratio (Plan 14)
- Line: historical TSB (solid)
- Line: projected TSB if athlete follows planned sessions (dashed, simulated forward via Banister with `load_t` from `planned_exercises` dimensional sum)
- Shaded band: expected specificity range by weeks-to-comp
- Scatter: actual weekly SR
- Vertical marker: comp date
- Vertical band: peaking window (TSB +5 to +15 target, shaded green)
- Current-day marker: circle

**Status pill above chart:**
- Green: "On track — peak window lands within ±3 days of comp"
- Yellow: "Peak misaligned — currently projected to peak X days early/late"
- Red: "Significant deviation — adjust deload timing"

Computed by finding the date where projected TSB first enters [+5, +15] and comparing to comp_date.

---

# PHASE 3 — NEW FEATURES

## Plan 20 — Competition Prep Block Comparison

**Goal:** Flagship feature. Side-by-side visualization of two (or more) historical comp prep blocks aligned on phase intent, not calendar.

**Files:**
- `frontend/src/pages/BlockComparisonPage.tsx` (new route)
- `backend/src/routes/analytics.ts` (new endpoint `GET /api/analytics/block-comparison?blocks=blockA,blockB`)
- `tools/health/block_comparison.py` (new module)
- Menu entry and route wiring
- README new section "Block comparison"
- About page new subsection

**Block definition:** A "block" is a contiguous slice of a program between `program_start` and the meet date (or the current date if the block is in progress). One program can contain multiple blocks if it spans multiple competitions.

**Alignment:**
- Map each block into canonical phases via `Phase.intent` tokens: `hypertrophy`, `strength`, `peaking`, `deload`, `taper`.
- Normalize each phase to the same relative duration so visual comparison is meaningful.

**Metrics computed per block (all from existing data):**
- Duration in weeks
- Starting e1RM per lift (average of first 2 weeks)
- Ending e1RM per lift (competition result if finalized; otherwise projected)
- Total gain kg / total gain % per lift and overall
- Average weekly sets per lift
- Average weekly volume (kg) per lift
- Peak Fatigue Index and peak ACWR
- Taper duration
- Taper Response (Plan 10's TQS equivalent if available)
- Average compliance
- Opener / 2nd / 3rd make rates per lift (when meet results available)
- Average intensity distribution (heavy / moderate / light percentages)
- Final specificity ratio
- Average INOL per lift
- PRR per lift (from Plan 11)

**Per-exercise drill-down:**
- Match exercises across blocks by glossary `id` (canonical name), not label.
- For each matched exercise: weekly volume chart overlay, weekly top e1RM overlay, total sets delta, total volume delta.

**Pattern detection (deterministic, not AI):**
- For each metric with a meaningful delta between blocks, generate a line of prose:
  - e.g. "Block B ran 30% more squat volume and gained 4 kg more on squat."
  - "Block A ran a 2-week taper and realized 96% of projection. Block B ran a 3-week taper and realized 103%."
- Top-N differences surfaced.

**Optional LLM summary at end** — reuse `program_evaluation_ai` with a new prompt variant that accepts two block summaries instead of one program. Small scope extension, not a new AI entry point.

---

## Plan 22 — Weight Class Feasibility Analyzer

**Goal:** Given current bodyweight, target weight class, and weeks to meet, compute feasibility and project DOTS outcomes at each nearby class.

**Files:**
- `frontend/src/pages/WeightClassAnalyzerPage.tsx` (new)
- `tools/health/weight_class.py` (new)
- Menu entry
- README new section
- About page new subsection

**Inputs:** current BW, federation (for class cutoffs), comp date, projected total (from existing projection).

**Output per candidate class (current class and ±1):**
- Required weekly cut rate: $(\text{current\_bw} - \text{class\_cap}) / \text{weeks\_to\_meet}$
- Feasibility label:

| Weekly cut | Label |
|---|---|
| < 0.5% | Easy |
| 0.5–0.8% | Manageable |
| 0.8–1.2% | Aggressive — expect performance cost |
| > 1.2% | Not recommended |

- Projected total at that class (with a 0.5% performance penalty per 1% BW lost)
- Projected DOTS at that class using the standard DOTS formula
- "Recommended" badge on the class with highest projected DOTS

---


**Goal:** Interactive tool where the user adjusts program parameters and sees projection update in real time.

**Files:**
- `frontend/src/pages/WhatIfSimulatorPage.tsx` (new)
- `tools/health/projection_simulator.py` (new; wraps existing projection math)
- Menu entry
- README new section
- About page new subsection

**Adjustable sliders:**
- Weeks to competition (4 – 24)
- Weekly volume per lift (sets/week)
- Weekly frequency per lift (1 – 5)
- Planned deload count (0 – 3)
- Taper duration in weeks (1 – 4)
- Starting e1RM per lift (pre-populated, editable)

**Output:** projected competition maxes + DOTS score + delta vs current plan, recomputed on every slider change. Chart overlays "current plan" vs "what-if" trajectories.

No new math — composes existing projection, Banister, and landmark functions.

---

## Plan 24 — Deload Recommendation Engine

**Goal:** Synthesize all fatigue-related signals into a single recommendation with a reason and a prescription.

**Depends on:** Plans 5, 7, 8, 9, 10

**Files:**
- `tools/health/deload_engine.py` (new)
- `backend/src/routes/analytics.ts` (add `deload_recommendation` to weekly response)
- `frontend/src/components/analysis/DeloadRecommendationCard.tsx` (new)
- Surfaced via Plan 17 alerts strip
- README new section
- About page new subsection

**Trigger rule** — recommend a deload when at least two of the following are true:

1. Fatigue Index ≥ 0.60 for 2+ consecutive weeks
2. Strength-Fatigue Decoupling negative for 3+ consecutive weeks (Plan 10)
3. EWMA-ACWR composite > 1.40 for 2+ consecutive weeks (Plan 5)
4. TSB < −30 (Plan 8)
5. Monotony > 2.0 for 2+ consecutive weeks (Plan 9)

**Prescription type** based on which dimension dominates:

- Axial-driven (axial ACWR highest) → "Reduce squat and deadlift volume by 50% for one week; keep bench normal."
- Neural-driven (neural ACWR highest) → "Drop top-set intensity to ≤ 80% for one week; keep volume moderate."
- Systemic-driven (systemic ACWR highest or TSB deeply negative) → "Reduce overall tonnage by 40–50% for one week."
- Peripheral-driven → "Reduce total reps by 30–40%; maintain intensity, shorten sets."

**Response shape:**
```ts
deload_recommendation: {
  triggered: boolean,
  severity: 'suggest' | 'recommend' | 'urgent',
  reasons: string[],      // which triggers fired
  prescription: {
    type: 'axial' | 'neural' | 'systemic' | 'peripheral',
    detail: string
  } | null
}
```

---


**Goal:** Reference database of federation rules that integrates into projection, attempt selection, and meet day planning.

**Files:**
- `backend/src/data/federations.json` (new static reference data)
- `packages/types/index.ts` (new `FederationRules` type)
- `backend/src/routes/federations.ts` (new)
- Integration points: Plan 11 (projection adjusts for press-command bench), Plan 16 (attempt increments), Plan 21 (meet day), Plan 22 (class cutoffs)
- Frontend: surface rule summaries on competition detail page
- README new section
- About page new subsection

**Schema per federation:**
```ts
interface FederationRules {
  code: string                 // 'IPF' | 'USAPL' | 'USPA' | 'WRPF' | ...
  display_name: string
  equipment_allowed: ('raw' | 'sleeved' | 'wrapped' | 'single_ply' | 'multi_ply')[]
  bench_press_command: boolean
  monolift_allowed: boolean
  weigh_in_window_hours: 2 | 24
  drug_tested: boolean
  min_attempt_increment_kg: number          // 2.5 for most, 0.5 for record attempts
  min_second_attempt_increment_kg: number   // 2.5 typically
  min_third_attempt_increment_kg: number    // 2.5 typically, 0.5 for records
  weight_classes: {
    male: { code: string; cap_kg: number }[]
    female: { code: string; cap_kg: number }[]
  }
  qualifying_totals?: {                     // per meet/event/class
    event: 'nationals' | 'worlds' | 'regionals'
    class_code: string
    sex: 'male' | 'female'
    total_kg: number
  }[]
}
```

**Integration in projection (Plan 11):** if federation requires bench press command and athlete has not logged paused bench (Plan 19 `paused = true`), apply a −2% to −4% realization factor on projected bench.

**Integration in attempt selection (Plan 16 / 12):** enforce `min_attempt_increment_kg` when rounding attempts.

---

## Plan 26 — Smart Template Comparison

**Goal:** When an athlete evaluates a template, compare the template's prescribed volumes, frequencies, and intensity distribution against the athlete's personal volume landmarks (Plan 13) and historically productive patterns.

**Depends on:** Plan 13

**Files:**
- `tools/health/template_compare.py` (new; separate from existing `template_evaluate_ai.py`)
- `backend/src/routes/templates.ts` (add deterministic comparison endpoint alongside the existing AI evaluation)
- `frontend/src/pages/TemplateDetailPage.tsx` (add "Fit to your history" card)
- README update of Template section
- About page

**Comparison dimensions:**

| Dimension | Template value | Athlete reference | Verdict |
|---|---|---|---|
| Squat weekly sets | from template | athlete MAV / MRV (Plan 13) | green / yellow / red |
| Bench weekly sets | from template | athlete MAV / MRV | |
| Deadlift weekly sets | from template | athlete MAV / MRV | |
| Squat frequency | from template | athlete productive frequency | |
| Bench frequency | from template | athlete productive frequency | |
| Deadlift frequency | from template | athlete productive frequency | |
| Intensity distribution | from template | athlete productive distribution | |
| Final-block SR | from template | Plan 14 expected-by-weeks-out | |

Each row emits a verdict and a suggestion line. No AI — pure deterministic comparison.

"Athlete productive frequency" = the frequency that correlated with highest progression rate in historical blocks (from Plan 20's per-lift analysis).

---


# Suggested Implementation Order

If you want a sensible sequence given dependencies:

1. Plan 15 (prose cleanup) — do this first so there's a clean baseline
2. Plans 1, 2, 3, 4, 5 — formula fixes (independent, any order)
3. Plan 6 → Plan 7 (wellness then readiness)
4. Plan 8 → Plan 9 → Plan 10 (peaking science layer)
6. Plan 11 → Plan 12 (projection calibration + attempt probability)
7. Plans 13, 14 (landmarks and specificity periodization)
8. Plans 16, 17, 18 (UI upgrades)
9. Plan 25 (federation rules — unblocks 21, 22, 27)
10. Plans 20, 21, 22, 23, 24, 26, 27 — feature buildout in any order

Each plan is scoped to be implementable in a single Claude Code plan-mode session.