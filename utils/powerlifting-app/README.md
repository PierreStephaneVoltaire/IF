# Powerlifting App

Implementation-accurate documentation for `utils/powerlifting-app/`.

This README is intentionally code-exact. It describes what the powerlifting
portal does today, including current limitations, caching behavior, and a few
places where older UI prose no longer matches the implementation.

If you want the current truth, treat these files as the real sources of truth:

- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/components/analysis/WeeklyData.tsx`
- `frontend/src/components/analysis/AiAnalysis.tsx`
- `frontend/src/constants/formulaDescriptions.ts`
- `backend/src/routes/analytics.ts`
- `tools/health/analytics.py`
- `tools/health/*_ai.py`
- `packages/types/index.ts`

## What This App Is

The powerlifting app is a single-athlete training portal that combines:

- deterministic analytics for progress, workload, fatigue, readiness, scoring,
  and competition projection
- narrow AI tools for fatigue-profile estimation, lift-profile cleanup and
  stimulus estimation, accessory ROI analysis, program evaluation, template
  evaluation, and spreadsheet import
- DynamoDB-backed storage for the full training record
- optional S3-backed video attachments

The frontend is React 19 + Vite + TypeScript + Mantine. The backend is
Express/TypeScript. Most serious analytics and AI work does not happen inside
the Node backend itself. The backend is primarily a thin transport layer that
calls IF health tools through the IF agent API.

High-level request flow:

```text
React page
  -> Express route
    -> invokeToolDirect(...)
      -> IF API /v1/chat/completions with X-Direct-Tool-Invoke: true
        -> tools/health/tool.py
          -> deterministic analytics module or AI module
            -> JSON back to frontend
```

For the Analysis page specifically there are three separate computation paths:

1. Backend deterministic analysis via `weekly_analysis`
2. Frontend-local derivations from program data, glossary data, and weight log
3. Separate AI reports for correlation analysis and full-block program evaluation

## Storage And Data Model

### Core storage model

The app stores its main state in DynamoDB table `if-health`. Important records:

- `program#current`
  Active-program pointer. Resolves to the latest concrete program version.
- `program#vNNN`
  Full program snapshot. New versions are written instead of updating in place.
- `weight_log#vNNN`
  Bodyweight history for the same program version.
- `max_history#vNNN`
  Historical max entries.
- `glossary#v1`
  Canonical exercise glossary plus fatigue metadata and accessory e1RM metadata.
- Template and import records
  Stored through the health tool layer and exposed in the portal through the
  template and import pages.

Storage conventions:

- Dates are `YYYY-MM-DD`
- Timestamps are ISO8601
- Weights are stored in kilograms
- Frontend unit switching is display-only

### Program meta

`Program.meta` captures:

- Identity and versioning:
  `program_name`, `version_label`, `updated_at`, `archived`, `archived_at`
- Timeline:
  `program_start`, `comp_date`, `weight_class_confirm_by`
- Federation / class context:
  `federation`, `practicing_for`, `weight_class_kg`
- Bodyweight context:
  `current_body_weight_kg`, `current_body_weight_lb`
- Targets:
  `target_squat_kg`, `target_bench_kg`, `target_dl_kg`, `target_total_kg`
- Attempt defaults:
  `attempt_pct.opener`, `attempt_pct.second`, `attempt_pct.third`
- Anthropometrics:
  `height_cm`, `arm_wingspan_cm`, `leg_length_cm`
- Manual and lift-specific max helpers:
  `manual_maxes`, `lift_attempt_settings`
- Program history/context:
  `training_notes[]`, `change_log[]`, `last_comp`
- Template lineage:
  `template_lineage.applied_template_sk`, `applied_at`, `week_start_day`,
  `start_date`

Important nuance:

- The typed schema does not currently declare `meta.sex`.
- Backend projection and backend `estimated_dots` still look for `meta.sex`.
- Frontend DOTS and IPF GL calculations instead use `settingsStore.sex`.

### Phases

`Phase` captures:

- `name`
- `intent`
- `start_week`
- `end_week`
- `target_rpe_min`
- `target_rpe_max`
- `days_per_week`
- `notes`
- `block`

Phases matter to:

- RPE drift
- readiness score
- AI program evaluation
- template evaluation

### Sessions and exercises

`Session` captures:

- Date placement:
  `date`, `day`, `week`, `week_number`
- Phase resolution:
  `phase`
- Block grouping:
  `block`
- Status:
  `status`, `completed`
- Planned work:
  `planned_exercises[]`
- Logged work:
  `exercises[]`
- Subjective/context fields:
  `session_notes`, `session_rpe`, `body_weight_kg`, `pain_log`
- Media:
  `videos[]`

`Exercise` captures:

- `name`
- `sets`
- `reps`
- `kg`
- `notes`
- `failed`
- `failed_sets[]`
- `load_source`
- `rpe_target`

These are the raw inputs to almost everything:

- e1RM estimation
- progression rate
- volume and intensity trends
- fatigue index
- fatigue-dimension workload
- INOL
- ACWR
- readiness
- specificity
- correlation AI

### Competitions

`Competition` captures:

- `name`, `date`, `federation`, `location`
- `hotel_required`
- `status`
- `weight_class_kg`
- `body_weight_kg`
- `targets`
- `results`
- `notes`
- `decision_date`
- `between_comp_plan`
- `comp_day_protocol`

Competition data drives:

- current max fallback from actual meet results
- weeks-to-comp context
- meet projection selection
- attempt selection
- DOTS/IPF GL interpretations
- AI program evaluation competition-alignment output

### Diet notes

`DietNote` captures averaged recovery/nutrition context, not meal-by-meal logging:

- `date`
- `notes`
- `avg_daily_calories`
- `avg_protein_g`
- `avg_carb_g`
- `avg_fat_g`
- `avg_sleep_hours`
- `water_intake`
- `water_unit`
- `consistent`

These are currently used mostly in frontend trend cards and AI interpretation,
not the hard deterministic training formulas.

### Supplements and supplement phases

Supplement data is stored:

- `supplements[]` with `name`, `dose`
- `supplement_phases[]` with phase notes, item list, peak-week protocol, block,
  start/end week

Important implementation note:

- Older app prose says supplements are not fed into AI yet.
- Current `program_evaluation_ai.py` does include a supplement summary in the
  prompt payload.
- The prompt still instructs the model to treat supplements cautiously and only
  mention them if materially relevant.

### Lift profiles

`LiftProfile` is one of the most important custom-data structures in the app.

Per lift (`squat`, `bench`, `deadlift`) it stores:

- `style_notes`
- `sticking_points`
- `primary_muscle`
- `volume_tolerance`
- `stimulus_coefficient`
- `stimulus_coefficient_reasoning`
- `stimulus_coefficient_confidence`
- `stimulus_coefficient_updated_at`

These profiles are used in two different ways:

1. As direct deterministic inputs through `stimulus_coefficient`, which modifies
   INOL
2. As soft AI context for lift-profile review, lift-profile rewrite, stimulus
   estimation, fatigue-profile estimation, correlation analysis, and program
   evaluation

### Weight log and max history

Additional tracked records:

- `WeightEntry`: `date`, `kg`
- `MaxEntry`: `date`, `squat_kg`, `bench_kg`, `deadlift_kg`, `total_kg`,
  `bodyweight_kg`, `context`

The Analysis page bodyweight trend uses `weight_log`. It does not derive
bodyweight trends only from `program.meta.current_body_weight_kg`.

### Glossary

`GlossaryExercise` captures:

- Identity and classification:
  `id`, `name`, `category`, `fatigue_category`, `equipment`
- Muscle mapping:
  `primary_muscles[]`, `secondary_muscles[]`
- Coaching metadata:
  `cues[]`, `notes`, `video_url`
- Fatigue metadata:
  `fatigue_profile`, `fatigue_profile_source`, `fatigue_profile_reasoning`
- Accessory e1RM metadata:
  `e1rm_estimate`
- Archive status:
  `archived`

The glossary is essential for:

- fatigue-dimension math
- specificity ratio broad counting
- muscle-group aggregation on the Analysis page
- import resolution
- AI fatigue estimation
- accessory e1RM backfill

### Templates and imports

Templates capture:

- `meta`: name, description, estimated weeks, days/week, timestamps,
  archival state, derivation lineage, AI evaluation
- `phases[]`
- `sessions[]`
- `glossary_resolution`
- `required_maxes[]`

Pending imports capture:

- file identity and classification
- AI parse result
- merge strategy and conflict resolution
- apply / reject state
- expiry / TTL

Import flows are AI-assisted and are covered later in this README.

### Local settings and external inputs

Some values are not stored inside `Program` but still change outputs:

- `settingsStore.unit`
  Display unit only
- `settingsStore.barWeightKg`
  Plate calculator and related tools
- `settingsStore.sex`
  Frontend DOTS and IPF GL calculations
- OpenPowerlifting dataset
  Used only on the Rankings page

### Intentionally missing or still-lightweight data

The current app does not do the following:

- no HRV
- no bar-velocity capture
- no vision-based technical analysis
- no per-meal diet logging
- no per-night sleep staging
- no true multi-athlete normalization

It also uses some soft context in AI without pushing that same context into the
rigid formulas. Body metrics are the best example: they are available to AI
prompts, but the deterministic fatigue math does not directly adjust for them.

## Analysis Page: Data Sources And Render Path

`frontend/src/pages/AnalysisPage.tsx` pulls data from three places:

1. `fetchWeeklyAnalysis(effectiveWeeks, 'current')`
   - route: `GET /api/analytics/analysis/weekly`
   - backend tool: `weekly_analysis`
   - primary source for fatigue, compliance, readiness, INOL, ACWR, specificity,
     projections, per-lift stats, flags, and backend current maxes
2. `fetchWeightLog(version)`
   - used for the bodyweight trend and as fallback bodyweight for local DOTS/IPF GL
3. `fetchGlossary()`
   - used for muscle-group aggregation and per-lift accessory/category grouping

AI cards are loaded separately by `AiAnalysis.tsx`:

- `GET /api/analytics/correlation?weeks=...&block=current`
- `GET /api/analytics/program-evaluation?refresh=...`

Windowing behavior:

- `1`, `2`, `4`, `8` week modes use a simple rolling date cutoff
- `Full Block` computes the number of weeks from `program.meta.program_start`
  to today and passes that week count to the backend

Important distinction:

- backend analysis uses deterministic health-tool math
- several cards on the page are frontend-derived and can disagree with backend
  values
- AI sections are cached separately and regenerated on demand

## Analysis Page: Every Section And What It Means

### 1. Estimated 1 Rep Maxes

This top card is not a pure pass-through of backend `current_maxes`.

Render priority:

1. If local `dotsTrend` rows exist, the card uses `highestMaxes`, which scans the
   locally-computed weekly Epley trend rows and takes the highest squat, bench,
   and deadlift value seen in the selected window.
2. If there is no local trend data, the card falls back to backend
   `data.current_maxes`.

Local trend rules:

- built from completed sessions only
- main-lift matching is name-based
- Epley formula is `kg * (1 + reps / 30)`
- local DOTS is then computed from local total plus latest bodyweight from
  weight log or session bodyweight

Backend `current_maxes` rules are different and more conservative; they are
documented in the formula section below.

Result: the top max card can legitimately differ from the backend maxes used by
projections and INOL.

### 2. Compliance

Source: backend `weekly_analysis -> session_compliance`

Displayed fields:

- percent complete
- completed / planned sessions
- current phase name
- average sessions per week across the selected window

Implementation notes:

- compliance uses all session rows in the window
- completed means `completed == true` or `status in ('logged', 'completed')`
- planned count does not exclude deload or break weeks

### 3. Fatigue Signal

Source: backend `fatigue_index`

Displayed:

- composite fatigue score as a percentage
- label: low / moderate / high
- component breakdown:
  `failed_compound_ratio`, `composite_spike`, `rpe_stress`

Threshold colors:

- `< 0.30` low
- `0.30 - 0.59` moderate
- `>= 0.60` high / overreaching risk

### 4. Readiness

Source: backend `compute_readiness_score`

Displayed:

- readiness score on a 0-100 scale
- normalized components:
  fatigue, RPE drift, bodyweight stability, miss rate

Threshold colors are implicit through the backend zone:

- `> 75` green
- `50 - 75` yellow
- `< 50` red

### 5. Stimulus-Adjusted INOL

Source: backend `compute_inol`

Displayed:

- average adjusted INOL per lift across the selected window
- lift-specific stimulus coefficient
- lift-level flags:
  low stimulus if `< 2.0`, overreaching if `> 4.0`

Important nuance:

- backend also returns raw, unadjusted INOL
- the UI currently surfaces only the adjusted version

### 6. ACWR

Source: backend `compute_acwr`

Displayed:

- composite ACWR
- composite zone
- per-dimension ACWR for axial, neural, peripheral, systemic

Zones:

- `< 0.80` undertraining
- `0.80 - 1.30` optimal
- `1.30 - 1.50` caution
- `> 1.50` danger

If there are fewer than 5 completed weeks, the UI shows an insufficient-data
message instead of ratios.

### 7. Relative Intensity Distribution

Source: backend `compute_ri_distribution`

Displayed:

- overall heavy / moderate / light distribution
- per-lift bucket distribution

Buckets:

- heavy: `RI > 0.85`
- moderate: `0.70 <= RI <= 0.85`
- light: `RI < 0.70`

### 8. Specificity Ratio

Source: backend `compute_specificity_ratio`

Displayed:

- narrow specificity = direct SBD sets / total sets
- broad specificity = (SBD + same-category secondary work) / total sets
- supporting counts: SBD sets and total sets

### 9. Fatigue Dimensions (Weekly)

Source: backend `_weekly_fatigue_by_dimension`

Displayed:

- weekly axial, neural, peripheral, systemic totals
- last 8 weeks only in the table/card UI

This section only exists because the health tool always loads the glossary and
passes it to `weekly_analysis`.

### 10. Projections

Source: backend `meet_projection`

Displayed:

- projected total
- confidence
- weeks to competition
- method
- first and last upcoming competitions when multiple upcoming meets exist

If no eligible competition exists, the page shows a reason string instead.

Important hidden detail:

- backend also computes `attempt_selection`
- the Analysis page currently does not render it

### 11. e1RM Progression, DOTS, and IPF GL Trend

Source: frontend-local `dotsTrend` / `ipfGlTrend`

Displayed:

- weekly local Epley-estimated squat, bench, deadlift, and total
- local DOTS trend
- local IPF GL trend
- weekly change badges

Implementation details:

- weekly bodyweight is the max session bodyweight seen in that week, or the
  latest weight-log entry if the week has none
- IPF GL mode is:
  - `classic_powerlifting` for full SBD weeks
  - `classic_bench` for bench-only weeks

This section is not sourced from backend `weekly_analysis`.

### 12. Body Weight Trend

Source: frontend-local `weightLog`

Displayed:

- latest weight
- change over the selected analysis window
- last 8 entries

It compares the latest weight to the oldest entry inside the current window,
falling back to the oldest overall entry if the window is empty.

### 13. Sleep Trend

Source: frontend-local aggregation of `diet_notes`

Displayed:

- average sleep hours
- week-over-week delta
- weekly sleep cards
- simple 7-hour threshold messaging

### 14. Nutrition Trend

Source: frontend-local aggregation of `diet_notes`

Displayed:

- average calories
- average protein
- average carbs
- average fat
- average water
- consistency percent

Aggregation rules:

- notes are bucketed into Monday-start weeks
- per-week averages are computed from whatever fields exist in that week
- deltas compare the first and last available weekly values, normalized by the
  number of points

### 15. Athlete Measurements

Source: `program.meta`

Displayed when present:

- height
- arm wingspan
- leg length

This is display-only on the Analysis page. These measurements matter more to AI
context than to rigid formulas.

### 16. Lift Style Profiles

Source: `program.lift_profiles`

Displayed:

- style/setup notes
- sticking points
- primary driver
- volume tolerance

This section is descriptive, but the same data also affects INOL and multiple AI
paths.

### 17. Competitions

Source: `program.competitions`

Displayed:

- meet name
- date
- status
- meet results if present

This table is informational. Projection logic uses competition data separately.

### 18. WeeklyData Subsections

Rendered by `frontend/src/components/analysis/WeeklyData.tsx`.

Subsections:

- Per-Lift Breakdown
  - progression rate
  - R-squared
  - volume and intensity week-over-week percent change
  - failed-set count
  - RPE trend
  - frequency and raw-set totals
  - expandable accessory list by same glossary category
- Exercise Volume
  - total sets
  - total volume
  - max weight
  - raw table or charts
- Sets by Muscle Group
  - glossary primary muscles get full set credit
  - glossary secondary muscles get 0.5 credit
- Avg Weekly by Muscle Group
  - same 1.0 / 0.5 weighting
  - average sets/week and average volume/week

### 19. AI Analysis

Rendered by `AiAnalysis.tsx`.

Subsections:

- Exercise ROI Correlation
  - requires at least 4 weeks selected
  - cached unless regenerated
- Program Evaluation
  - only shown in Full Block mode
  - frontend gate is at least 4 completed sessions
  - backend gate is stricter: at least 4 completed weeks

### 20. Formula Accordion And Flags

The accordion is a prose layer from `frontend/src/constants/formulaDescriptions.ts`.
It is useful, but it is not the final authority where code and prose differ.

The `Flags` card is a merged list from multiple backend analytics sources:

- RPE drift flags
- fatigue flags
- INOL flags

## Deterministic Formulas And Why They Are Customized

### Estimated 1RM and current max selection

Where used:

- backend current maxes
- backend meet projection
- backend INOL / ACWR / RI distribution
- frontend trend table uses a separate local Epley path

Backend session estimate:

```text
If session RPE exists and reps are 1..6 and RPE is 6..10:
  e1RM = weight / RPE_TABLE[(reps, RPE)]

Else if no RPE exists and reps are 1..5:
  e1RM = weight / CONSERVATIVE_REP_PCT[reps]
```

Selection rules:

- ignore failed sets
- use only recent session estimates within the last 42 days
- take the 90th percentile per lift
- require at least 3 qualifying estimates per lift
- require at least 2 lifts total for a session-derived current-max object
- prefer the latest completed competition results over session-derived estimates

Why this is customized:

- the main analysis intentionally avoids generic Epley/Brzycki as the primary
  truth path
- the implementation is explicitly conservative
- the percentile selection dampens one-off inflated sets
- real competition results override estimates when available

### Deload detection and effective weeks

Where used:

- progression rate
- effective training week count
- projection logic
- deload info block on the Analysis page

Rules:

```text
A week is a break if volume load == 0.

A week is a deload if:
  1. weekly volume load is below a rolling median threshold
  2. and intensity confirms it is intentionally easy
```

Exact thresholds:

- volume threshold with squat/deadlift present: `< 0.65 * median(previous rolling non-deload weeks)`
- volume threshold with no squat/deadlift present: `< 0.75 * median(...)`
- intensity confirmation:
  - all primary-lift RPEs `<= 6`, or
  - best primary-lift e1RM dropped by at least 10 percent vs the previous two
    non-deload weeks
- stagnation alone does not count as a deload

Why this is customized:

- progression math should not punish intentionally easy weeks
- the code deliberately requires both low volume and low intensity evidence
- a week is not labeled deload just because it stopped improving

### Progression rate

Where used:

- per-lift breakdown
- meet projection

Formula:

```text
For each effective training week:
  best_weekly_e1RM = max(qualifying e1RMs in that week)

slope = Theil-Sen(best_weekly_e1RM ~ effective_week_index)
R^2 = fit quality against the Theil-Sen line
```

Important details:

- cutoff is the last 90 days
- only completed/logged sessions count
- deload and break weeks are excluded
- weekly point uses the best qualifying set, not the average

Why this is customized:

- Theil-Sen is robust to noisy training logs and outliers
- "effective week" indexing prevents deliberate deloads from flattening slope

### Volume/intensity correlation

Where used:

- per-lift volume and intensity percent-change display
- accessory ROI prior for correlation AI

Formula:

```text
weekly_volume = sum(sets * reps * kg) for the exercise in that week
weekly_avg_intensity = mean(kg) for that exercise in that week
pearson_r = corr(weekly_volume, weekly_avg_intensity)
```

Requirements:

- at least 3 weeks of data

### RPE drift

Where used:

- per-lift breakdown
- readiness score
- flags

Current implementation:

```text
If phase target RPE ranges exist:
  residual = actual_session_rpe - phase_target_midpoint
  slope = Theil-Sen(residual ~ week)
Else:
  slope = Theil-Sen(actual_rpe ~ week)
```

Flags:

- slope `>= 0.1` -> fatigue
- slope `<= -0.1` -> adaptation
- otherwise stable

Why this is customized:

- it compares performance against the intended phase difficulty, not just raw RPE
- it treats rising RPE at the same planned difficulty as a fatigue signal

Important code/prose mismatch:

- older formula text says OLS
- current code uses Theil-Sen here as well

### Fatigue model and fatigue dimensions

Where used:

- fatigue dimensions table
- fatigue index spike path
- ACWR

Per-set model:

```text
I = weight / e1RM
phi(I) = 0                        if I <= 0.60
phi(I) = ((I - 0.60) / 0.40)^2   otherwise

axial      = profile.axial      * weight * reps
neural     = profile.neural     * reps * phi(I)
peripheral = profile.peripheral * weight * reps
systemic   = profile.systemic   * weight * reps
```

Implementation details:

- only squat, bench, and deadlift get direct current-max lookup for `I`
- non-SBD exercises fall back to `I = 0.70` for neural scaling
- weekly totals multiply the per-set values by `sets`
- missing glossary fatigue profiles fall back to:
  `axial=0.3, neural=0.3, peripheral=0.5, systemic=0.3`

Why this is customized:

- the app intentionally tracks four recovery dimensions instead of one tonnage
  number
- neural fatigue is intensity-sensitive and intentionally zeroed below 60 percent

### Fatigue index

Where used:

- Fatigue Signal card
- readiness score
- flags

Formula:

```text
FI = 0.40 * failed_compound_ratio
   + 0.35 * composite_spike
   + 0.25 * rpe_stress

rpe_stress = clamp((avg_session_rpe - 6.0) / 4.0, 0, 1)
```

Component details:

- `failed_compound_ratio`
  failed compound sets / total compound sets
- `composite_spike`
  preferred path: weighted dimensional spike from glossary fatigue math
  fallback path: recent tonnage spike vs recent-week average
- `rpe_stress`
  captures prolonged RPE 9-10 grinding even if failures never occur

Flags:

- `failed_sets_spike` if failed ratio > 0.15
- `volume_spike` if composite spike > 0.20
- `high_rpe_stress` if RPE stress > 0.50
- `overreaching_risk` if FI >= 0.60
- `neural_overload` and `axial_overload` if dimension ACWR > 1.3

Why this is customized:

- skip rate was intentionally removed
- code comment rationale: resting reduces fatigue, not increases it
- the model treats high-RPE grinding as fatigue even without misses
- when glossary data exists, fatigue is computed through axial/neural/peripheral/
  systemic workload rather than plain tonnage

### INOL

Where used:

- Stimulus-Adjusted INOL card
- flags

Formula:

```text
I = kg / current_max_for_lift
denom = (1 - I), except if I >= 1 then denom = max(0.01, 1 - I)

raw_set_INOL = reps / (100 * denom)
raw_weekly_INOL = sum(raw_set_INOL * sets)
adjusted_weekly_INOL = raw_weekly_INOL * stimulus_coefficient
```

Only canonical lifts count:

- squat
- bench / bench press
- deadlift

Stimulus coefficient behavior:

- default `1.0`
- read from `lift_profiles[].stimulus_coefficient`
- clamped to `[1.0, 2.0]`

Why this is customized:

- raw INOL assumes the same load/intensity stress means the same practical
  stimulus for every lifter
- the stimulus-coefficient prompt explicitly adjusts for:
  - effective ROM
  - mechanical advantage or disadvantage
  - total muscle mass under meaningful tension
  - time under tension near the weak point
  - eccentric loading
  - volume recovery tolerance
- baseline `1.0` means competition-standard stimulus

### ACWR

Where used:

- ACWR card
- fatigue-overload flagging

Formula:

```text
ACWR_dim = mean(last 1 week dim load) / mean(previous 4 weeks dim load)
Composite = 0.30*axial + 0.30*neural + 0.25*peripheral + 0.15*systemic
```

Requirements:

- at least 5 completed weeks

Zones:

- `< 0.80` undertraining
- `0.80 - 1.30` optimal
- `1.30 - 1.50` caution
- `> 1.50` danger

Why this is customized:

- workload is measured through fatigue-dimension totals, not simple tonnage
- code comment rationale: deload weeks are included for a more accurate chronic
  baseline

Important code/prose mismatch:

- older formula text says "previous 4 non-deload weeks"
- current code includes deloads in the chronic baseline

### Relative intensity distribution

Where used:

- RI Distribution card

Formula:

```text
RI = kg / current_max_for_lift

heavy    if RI > 0.85
moderate if 0.70 <= RI <= 0.85
light    if RI < 0.70
```

Counts are set-based, not exercise-entry-based.

### Specificity ratio

Where used:

- Specificity Ratio card

Formula:

```text
narrow = direct_SBD_sets / total_sets
broad  = (direct_SBD_sets + same_category_secondary_sets) / total_sets
```

Secondary category matching uses glossary categories `squat`, `bench`, and
`deadlift`.

### Readiness score

Where used:

- Readiness card

Formula:

```text
R = (1 - (
      0.30 * fatigue_norm
    + 0.25 * rpe_drift
    + 0.20 * bw_stability
    + 0.15 * miss_rate
    + 0.10 * (1 - compliance_pct / 100)
    )) * 100
```

Component construction:

- `fatigue_norm`
  fatigue index over the last 14 days
- `rpe_drift`
  `clamp((avg_rpe_last_14d - current_phase_target_midpoint) / 2, 0, 1)`
- `bw_stability`
  coefficient of variation of the last 7 session bodyweight entries,
  normalized by `0.03`
- `miss_rate`
  failed sets / total sets in the last 14 days
- `compliance_pct`
  2-week compliance

Fallbacks:

- no fatigue data -> `0.5`
- no recent RPEs -> `7.5`
- no recent bodyweight series -> `0.5`

Why this is customized:

- it is a training-readiness model tied to actual logged training behavior
- it blends stress, performance feel, bodyweight stability, misses, and
  execution consistency instead of relying on a generic subjective readiness input

### DOTS and IPF GL

Where used:

- local trend card
- rankings/tools pages

DOTS:

```text
DOTS = 500 * total / (a + b*bw + c*bw^2 + d*bw^3 + e*bw^4)
```

IPF GL:

```text
GL = result * 100 / (A - B * exp(-C * bw))
```

Important implementation nuance:

- backend `weekly_analysis.estimated_dots` looks for `meta.bodyweight_kg` and
  `meta.sex`
- frontend local trend cards use `settingsStore.sex` and weight log / session BW
- this is one reason backend `estimated_dots` can be null while local trend DOTS
  still renders

### Meet projection

Where used:

- Projections card
- backend attempt selection input

Formula skeleton:

```text
weeks_to_comp = (comp_date - today) / 7

Choose lambda and peak_factor from current DOTS:
  DOTS < 300  -> lambda=0.96, peak=1.01
  300-399.99  -> lambda=0.90, peak=1.03
  >= 400      -> lambda=0.85, peak=1.05

weeks_taper =
  3 if weeks_to_comp >= 12
  2 if weeks_to_comp >= 8
  1 otherwise

planned_deload_weeks =
  detected future deloads, else floor(weeks_to_comp / 4) if no future deloads
  are found and the meet is more than 4 weeks away

n_t = max(0, weeks_to_comp - weeks_taper - planned_deload_weeks)

projected_gain = delta_w * lambda * (1 - lambda^n_t) / (1 - lambda)
comp_max = (current_max + projected_gain) * peak_factor
```

Ceiling clamp:

```text
ceiling_pct = 10% + 1% per 2 weeks beyond 8, capped at 30%
comp_max is clamped to [current_max, current_max * (1 + ceiling_pct)]
```

Why this is customized:

- projection is time-aware and DOTS-aware
- the ceiling is intentionally tighter for near-term meets and looser for far-out
  meets
- taper and planned deloads are explicitly subtracted

Important code/prose mismatch:

- older formula text says a fixed 10 percent ceiling
- current code uses a dynamic ceiling up to 30 percent

### Attempt selection

Where used:

- computed in backend `weekly_analysis`
- currently not rendered on the Analysis page

Formula:

```text
opener = round_to_2.5(projected_comp_max * opener_pct)
second = round_to_2.5(projected_comp_max * second_pct)
third  = round_to_2.5(projected_comp_max * third_pct)
```

Default percents:

- opener `0.90`
- second `0.955`
- third `1.00`

### Compliance

Where used:

- Compliance card
- Readiness score

Formula:

```text
compliance = completed_sessions / planned_sessions * 100
```

Important implementation detail:

- all weeks in the selected compliance window are counted
- deloads and breaks are not excluded

## Where And How AI Is Used

### AI execution model

The app has multiple AI entry points, but each is narrow.

Current model/config variables:

- `ANALYSIS_MODEL`
  correlation analysis, program evaluation, template evaluation, import parsing
- `ANALYSIS_MODEL_THINKING_BUDGET`
  thinking budget for those heavier calls
- `MODEL_ROUTER_MODEL`
  lift-profile review/rewrite/estimate and fatigue-profile estimation
- `IMPORT_FAST_MODEL`
  import classification, glossary resolution, accessory e1RM backfill

### 1. Exercise fatigue-profile estimation

User-visible surfaces:

- auto-trigger when a new glossary exercise is added without a manual fatigue profile
- explicit estimate button in the glossary flows
- route: `POST /api/analytics/fatigue-profile/estimate`
- route: `POST /api/exercises/:id/estimate-fatigue`

Tool/module path:

- `fatigue_profile_estimate`
- `tools/health/fatigue_ai.py`

Prompt summary:

- estimate four 0.0-1.0 dimensions: axial, neural, peripheral, systemic
- anchor to known example lifts and accessories
- treat athlete body metrics and lift profile as soft modifiers only
- explicitly ignore diet, sleep, supplements, and programming context

Output:

- dimension values rounded to nearest `0.05`
- short reasoning string

Important implementation detail:

- the auto-add path sends a full exercise dict and is the cleaner path
- the `glossary_estimate_fatigue` path currently passes only the exercise name
  into `fatigue_ai`, which is rougher and can fall back to defaults on error

### 2. Lift-profile review, rewrite, and stimulus estimation

User-visible surfaces:

- Dashboard lift-profile guide
- dedicated `LiftProfilePage`

Routes:

- `POST /api/analytics/lift-profile/review`
- `POST /api/analytics/lift-profile/rewrite`
- `POST /api/analytics/lift-profile/estimate-stimulus`
- `POST /api/analytics/lift-profile/rewrite-and-estimate`

Tool/module path:

- `tools/health/lift_profile_ai.py`

Prompt summary:

- review whether a profile has enough biomechanical detail to estimate how much
  raw INOL understates or overstates stimulus
- score completeness as:
  - style/setup: 40 points
  - sticking point: 35 points
  - primary driver: 25 points
- ready threshold for estimation is `55`
- stimulus coefficient range is `1.0` to `2.0`
- baseline `1.0` means competition-standard stimulus
- raise coefficient for longer ROM, more tension, more muscle mass under
  tension, mechanical disadvantage, more weak-point time, and low volume tolerance
- keep closer to `1.0` for shorter ROM, strong leverage, bypassed weak points,
  and high volume tolerance

Fallback behavior:

- if AI fails or profile is too sparse, coefficient defaults to `1.0`
- confidence drops to `low`

### 3. Exercise ROI correlation analysis

User-visible surface:

- Analysis page -> `Exercise ROI Correlation`

Route:

- `GET /api/analytics/correlation?weeks=N&block=current`

Tool/module path:

- `correlation_analysis`
- `tools/health/correlation_ai.py`

Prompt summary:

- identify only anatomically plausible accessory -> SBD relationships
- do not judge the program structure itself
- treat missing weeks or low frequency as normal for powerlifting
- use lift profiles to weight relevance
- use deterministic ROI prior (`pearson_r` between weekly accessory volume and
  average intensity) only as a confidence modifier, never as permission to
  invent a relationship

Inputs:

- weekly big-lift e1RMs built locally inside the AI module using Epley
- weekly accessory volume table
- lift profiles
- athlete measurements
- bodyweight trend
- caloric context
- weeks to primary competition
- deterministic accessory ROI table

Cache behavior:

- cached by Monday-aligned window key:
  `corr_report#{window_start}_{weeks}w`
- `Regenerate` bypasses cache
- exported XLSX uses the cached report if one exists

Minimum data:

- current code requires at least 4 distinct weeks of data

### 4. Full-block program evaluation

User-visible surface:

- Analysis page -> `Program Evaluation`

Route:

- `GET /api/analytics/program-evaluation?refresh=...`

Tool/module path:

- `program_evaluation`
- `tools/health/program_evaluation_ai.py`

Prompt summary:

- the model is framed as an objective sports scientist and analyst, not a coach
- default stance should be conservative: continue or monitor unless multiple
  signals point to a real issue
- it must not redesign the program, call it random, or tell the athlete to drop
  competitions
- it must use:
  - program meta
  - phases
  - competitions
  - lift profiles
  - measurements
  - supplement summary
  - diet and bodyweight context
  - completed and planned sessions
  - deterministic weekly analysis
  - exercise ROI prior
  - formula reference text

Output:

- `stance`
- `summary`
- `what_is_working`
- `what_is_not_working`
- `competition_alignment[]`
- `small_changes[]`
- `monitoring_focus[]`
- `conclusion`

Cache behavior:

- cached on a weekly cadence under `program_eval#{window_start}`
- `Regenerate` bypasses cache

Minimum data:

- backend requires at least 4 completed weeks

Important frontend/backend mismatch:

- frontend gate only checks for at least 4 completed sessions before trying to
  show the card
- backend is stricter and may still return insufficient data

### 5. Accessory e1RM backfill

User-visible surface:

- glossary estimate e1RM flows

Route:

- `POST /api/exercises/:id/estimate-e1rm`

Tool/module path:

- `glossary_estimate_e1rm`
- `tools/health/e1rm_backfill_ai.py`

Prompt summary:

- estimate accessory training maxes as conservative ratios of primary SBD lifts
- use lift profiles and past logged instances when available
- prefer underestimation to overestimation
- confidence is intentionally only `medium` or `low`

Persisted output:

- writes `glossary[].e1rm_estimate`

### 6. Template evaluation

User-visible surface:

- Template detail -> `AI Evaluation`

Route:

- `POST /api/templates/:sk/evaluate`

Tool/module path:

- `template_evaluate`
- `tools/health/template_evaluate_ai.py`

Prompt summary:

- judge whether a template fits current athlete context and meet timeline
- produce stance, strengths, weaknesses, suggestions, projected readiness at comp
- treat RPE and percentage-based planned sessions specially

Important current rough edge:

- `core.template_evaluate()` currently passes mocked athlete context:
  - `current_maxes`
  - `dots_score = 350`
  - `weeks_to_comp = 12`
- so template evaluation is real AI output, but not yet fed by the full current
  athlete context you might expect

### 7. Spreadsheet import AI

User-visible surface:

- Import wizard

AI modules:

- `import_classify_ai.py`
  - classify file as `template`, `session_import`, or `ambiguous`
- `import_parse_ai.py`
  - parse structured phases, sessions, warnings, parse notes
- `glossary_resolve_ai.py`
  - resolve exercise names to glossary IDs or suggest new entries

Prompt summaries:

- classification looks for real dates vs relative weeks and absolute kg vs RPE/%
- parsing extracts structured training data and warnings without inventing rows
- glossary resolution handles abbreviations and nicknames, but only suggests
  new entry `name`, `category`, and `equipment`

## Other Important User-Facing Surfaces

### Dashboard

The Dashboard is the main control surface for:

- program meta edits
- weight log interaction
- lift-profile review / rewrite / stimulus estimation
- anthropometrics

### Glossary page

The Glossary page is where exercise intelligence lives:

- canonical exercise definitions
- category and muscle mapping
- fatigue profile
- fatigue-profile reasoning
- accessory e1RM estimates
- archive state

### Template library and designer

These pages manage:

- blank template creation
- block-to-template conversion
- template archive/unarchive
- application to a program
- AI evaluation

### Tools page

Deterministic utility tools include:

- DOTS calculator
- attempt selector
- unit converter
- percent table
- plate calculator
- weight tracker

### Rankings page

The Rankings page is separate from the core training analytics. It compares user
totals and DOTS to the OpenPowerlifting dataset with filterable federation,
country, region, equipment, sex, age class, year, and event type.

### Videos

Videos are stored and displayed, but no computer-vision analysis is currently
performed.

## Known Mismatches, Rough Edges, And "Read The Code" Notes

These are the main places where older prose or UI expectations diverge from the
current implementation:

1. Projection ceiling prose is stale.
   Older descriptions say projections are clamped to 10 percent above current
   max. Current code uses a time-scaled ceiling that can rise to 30 percent.

2. ACWR prose is stale.
   Older formula text says chronic load is previous 4 non-deload weeks. Current
   code includes deload weeks in the chronic baseline.

3. RPE drift prose is stale.
   Older prose says OLS. Current code uses Theil-Sen.

4. Compliance prose is partly stale.
   Current code counts all weeks in the compliance window, including deloads and
   breaks.

5. The About page understates the AI surface area.
   The current codebase has more than the originally-described three narrow AI
   tools.

6. Supplement usage prose is stale.
   Some older prose says supplements are not fed into AI prompts. Program
   evaluation currently includes supplement summary context.

7. Backend `estimated_dots` is fragile.
   It depends on `meta.bodyweight_kg` and `meta.sex`, while the current typed
   schema mainly stores `current_body_weight_kg` and frontend sex in local
   settings. Frontend local DOTS trends are often more complete than backend
   `estimated_dots`.

8. The top max card is not the same thing as backend current maxes.
   The card prefers local Epley-based trend maxima when they exist.

9. `attempt_selection` is computed but not rendered on the Analysis page.

10. Program-evaluation gating differs between frontend and backend.

11. Template evaluation is still partly scaffolded.
    The current athlete context passed into the template-evaluation model is
    mocked and minimal.

12. The glossary fatigue-estimation path is rougher than the auto-add path.
    The direct glossary estimate route currently hands less structured context
    into `fatigue_ai`.

## Bottom Line

The powerlifting app is not just a logbook. It is a layered system:

- raw training data and meet data in DynamoDB
- glossary metadata for anatomy and fatigue semantics
- deterministic analysis in `tools/health/analytics.py`
- narrow AI interpretation layers in `tools/health/*_ai.py`
- a React Analysis page that mixes backend analytics with additional local trends

The most important customizations are the ones that make the portal athlete-
specific instead of textbook-generic:

- conservative current-max estimation instead of naive Epley everywhere
- deload-aware progression math
- four-dimensional fatigue instead of one load number
- fatigue index without skip-rate inflation
- stimulus-adjusted INOL from lift profiles
- phase-aware RPE drift and readiness
- DOTS-sensitive, taper-aware meet projection

If you are changing the analytics or the AI prompts, update this README at the
same time. The portal's behavior is now too custom for a short marketing README
to stay truthful.
