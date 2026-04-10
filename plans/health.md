---

## Simplified Flow

```
User creates/saves glossary exercise
         │
         ▼
    Has fatigue_profile with source "manual"?
         │
    YES ──► Keep it. Done.
         │
    NO ──► Call AI estimation endpoint.
              │
              ▼
         AI returns { axial, neural, peripheral, systemic, reasoning }
              │
              ▼
         Save with fatigue_profile_source: "ai_estimated"
              │
              ▼
         User sees values in sliders + "AI estimated" badge.
         If they adjust a slider → source flips to "manual".
```

That's it. No defaults table. No migration map. One code path.

**For initial population:** a shell script iterates all existing glossary entries, checks if `fatigue_profile` is null, and calls the same AI endpoint for each. Run once, done.

---

## Full Consolidated IDE Agent Prompt

```text
TASK
====
Refactor the analytics engine (app/src/health/analytics.py) and update the
relevant frontend components to fix incorrect formulas and add missing metrics.
Reference the app spec in the repo README for data model and existing metric
definitions. All analytics are deterministic math — no LLM calls — except
for section 4c which adds an AI estimation endpoint for fatigue profiles on
glossary exercises. scipy is available in the Python environment.

Read the FULL prompt before starting. Changes are interdependent:
  - The fatigue model (section 4) feeds into: fatigue index (section 5),
    ACWR (section 9), readiness score (section 12).
  - The e1RM fix (section 1) feeds into: progression rate (section 2),
    meet projection (section 3), INOL (section 8), relative intensity
    (section 10).


===============================================================================
1. e1RM ESTIMATION — FIX (critical)
===============================================================================

Current behaviour is broken: Epley/Brzycki are run on ALL non-failed sets
including 10+ rep sets, which overshoots actual 1RM by 10-20%. The 90-day
max-of-all-e1RMs is too noisy.

Changes:

a) Rep cap and priority cascade. When estimating e1RM from a single set:
   - If RPE is recorded (value 6-10) AND reps <= 6: use the existing RPE
     percentage table (RTS standard). e1RM = weight / pct(reps, rpe).
   - Else if RPE is NOT recorded AND reps <= 5: use a conservative
     percentage lookup table:
       reps 1 -> 1.000
       reps 2 -> 0.955
       reps 3 -> 0.925
       reps 4 -> 0.898
       reps 5 -> 0.875
     e1RM = weight / pct(reps).
   - Else: DISCARD this set entirely. Do not estimate from it.
   Do NOT fall back to Epley or Brzycki under any circumstance.

b) Session-derived current max. When computing "current estimated 1RM" for
   a lift (squat/bench/deadlift), collect all qualifying e1RM values from
   completed sessions in the LAST 6 WEEKS (not 90 days). Take the 90th
   percentile of these values (not the max). Require at least 3 qualifying
   sets to produce an estimate; return null if fewer.

c) This corrected e1RM (call it E_now) is the input everywhere else:
   progression rate, meet projection, INOL, relative intensity.


===============================================================================
2. PROGRESSION RATE — FIX (critical)
===============================================================================

Current behaviour is broken: OLS on top_kg across all sessions including
deloads. Deloads bias slope down, OLS is fragile to outliers, and top_kg
ignores rep schemes.

Changes:

a) Deload/break detection. Before computing regression, flag weeks:
   - Compute each week's total volume load: VL = sum(weight * reps) across
     all sets in all sessions that week.
   - A week is a DELOAD if VL < 0.65 * rolling_median(VL of previous 4
     non-deload weeks). Use median not mean.
   - A week is a BREAK if it has zero sessions or zero volume load.
   - Store the is_deload flag per week — reused by compliance (section 6)
     and other metrics.

b) Effective training weeks. After removing deloads and breaks, re-index
   remaining weeks contiguously: 0, 1, 2, ...
   All slopes are expressed as "per effective training week."

c) Regress on e1RM not top_kg. For each effective week, compute best e1RM
   from that week's sessions using the capped formulas from section 1.

d) Replace OLS with Theil-Sen. Use scipy.stats.theilslopes(y, x). Return
   slope (kg per effective week). Compute R-squared from residuals:
     predicted = intercept + slope * x
     SS_res = sum((y - predicted)^2)
     SS_tot = sum((y - mean(y))^2)
     R2 = 1 - SS_res / SS_tot


===============================================================================
3. MEET PROJECTION — FIX (critical)
===============================================================================

Formula structure is correct. Inputs are wrong.

Changes:

a) Use corrected E_now (90th percentile, 6-week window) from section 1.

b) Use corrected Theil-Sen slope as delta_w from section 2.

c) Effective training weeks remaining:
     n_t_eff = weeks_to_comp - taper_weeks - planned_deload_weeks
   For planned_deload_weeks: check phase definitions for deload indicators.
   If not determinable, estimate as floor(calendar_training_weeks / 4).

d) Keep existing lambda and P lookup tables by DOTS level (these are fine).

e) Clamp output:
     C_max = max(E_now, min(raw_projection, E_now * 1.10))
   Floor = never below current max. Ceiling = max 10% gain in one prep.

f) Formula remains:
     C_max = [E_now + delta_w * lambda * (1 - lambda^n_t_eff)
              / (1 - lambda)] * P
   ...then clamped.


===============================================================================
4. FATIGUE MODEL OVERHAUL (critical — affects sections 5, 9, 12)
===============================================================================

Current model uses a single fatigue_category enum with a single scalar
multiplier. This is too coarse — a squat produces axial, neural, peripheral,
AND systemic fatigue simultaneously.

Changes:

a) Glossary data model. Add to each glossary exercise:

     fatigue_profile: {
       axial: float 0-1,       // spinal compression loading
       neural: float 0-1,      // CNS demand baseline
       peripheral: float 0-1,  // local muscle damage potential
       systemic: float 0-1     // cardiovascular / metabolic demand
     }
     fatigue_profile_source: "ai_estimated" | "manual"
     fatigue_profile_reasoning: string | null  // AI's explanation

   Keep the old fatigue_category field as a display label only. All fatigue
   MATH now uses fatigue_profile exclusively.

b) Fallback at analytics computation time. If an exercise has no
   fatigue_profile at all (legacy data), use a safe neutral default:
     { axial: 0.3, neural: 0.3, peripheral: 0.5, systemic: 0.3 }
   This is deliberately mediocre — it won't blow anything up but it will
   be visibly "off" enough that the user is motivated to get a real
   estimate. Log a warning when this fallback is used.

c) AI estimation endpoint. Add a new endpoint to the Python FastAPI service:

     POST /api/ai/estimate-fatigue-profile

   Request body:
     {
       "name": string,
       "category": string,
       "equipment": string,
       "primary_muscles": string[],
       "secondary_muscles": string[],
       "cues": string | null,
       "notes": string | null
     }

   Response body:
     {
       "axial": float,
       "neural": float,
       "peripheral": float,
       "systemic": float,
       "reasoning": string
     }

   Implementation: call an LLM (use the existing AI service infrastructure)
   with the system prompt and tool defined below. Extract the tool call
   result and return it.

   SYSTEM PROMPT FOR THE AI SERVICE:
   ---
   You are a sport science specialist for powerlifting programming. Your
   task is to estimate the fatigue profile of a strength training exercise
   across four dimensions. Each dimension is a float from 0.0 to 1.0.

   DIMENSIONS:

   1. AXIAL (spinal compression loading)
      0.0 = zero spinal load (e.g. leg extension, bicep curl)
      0.5 = moderate spinal load (e.g. barbell row, good morning)
      1.0 = maximum spinal load (e.g. heavy back squat with bar on spine)

   2. NEURAL (central nervous system demand)
      0.0 = minimal motor unit recruitment, low coordination (e.g. cable
            face pull)
      0.5 = moderate recruitment, some coordination (e.g. barbell row, RDL)
      1.0 = maximal recruitment, high coordination under heavy load (e.g.
            competition deadlift, max effort squat)

   3. PERIPHERAL (local muscle damage potential)
      0.0 = negligible muscle damage (e.g. band pull-aparts)
      0.5 = moderate eccentric/stretch component (e.g. overhead press)
      1.0 = high eccentric loading, large ROM, stretch under load (e.g.
            deep pause squat, deficit deadlift)

   4. SYSTEMIC (cardiovascular / whole-body metabolic demand)
      0.0 = negligible metabolic cost (e.g. wrist curls)
      0.3 = small muscle mass, seated/supported (e.g. tricep extension)
      0.5 = standing compound, moderate muscle mass (e.g. barbell row)
      0.8 = large muscle mass, standing, high work capacity demand (e.g.
            heavy deadlifts for reps)
      1.0 = extreme — very large loads + large ROM + many muscles

   CALIBRATION ANCHORS (use these to stay consistent):
     Competition Back Squat: { axial: 1.0,  neural: 0.9,  peripheral: 0.8,  systemic: 0.7  }
     Competition Bench Press:{ axial: 0.15, neural: 0.85, peripheral: 0.75, systemic: 0.35 }
     Competition Deadlift:   { axial: 1.0,  neural: 1.0,  peripheral: 0.9,  systemic: 0.8  }
     RDL:                    { axial: 0.8,  neural: 0.6,  peripheral: 0.85, systemic: 0.6  }
     Barbell Row:            { axial: 0.6,  neural: 0.5,  peripheral: 0.7,  systemic: 0.4  }
     Leg Press:              { axial: 0.05, neural: 0.3,  peripheral: 0.8,  systemic: 0.5  }
     Leg Extension:          { axial: 0.0,  neural: 0.1,  peripheral: 0.7,  systemic: 0.2  }
     Bicep Curl:             { axial: 0.0,  neural: 0.05, peripheral: 0.5,  systemic: 0.1  }
     Face Pull:              { axial: 0.0,  neural: 0.05, peripheral: 0.3,  systemic: 0.1  }

   RULES:
   - Round all values to nearest 0.05.
   - Use the calibration anchors as RELATIVE references. A dumbbell lunge
     should have LESS axial load than a barbell squat but MORE than a leg
     press.
   - Barbells generally produce more axial/neural load than machines/cables
     for the same movement pattern.
   - Bilateral exercises generally have higher neural/systemic than
     unilateral, but unilateral may have higher peripheral per-limb.
   - Use the "reasoning" field to explain your estimates in 1-2 sentences.
   - You MUST call the estimate_fatigue_profile tool.
   ---

   TOOL SCHEMA:
     {
       "name": "estimate_fatigue_profile",
       "description": "Estimate the four-dimensional fatigue profile for a strength training exercise",
       "parameters": {
         "type": "object",
         "properties": {
           "axial":      { "type": "number", "minimum": 0, "maximum": 1 },
           "neural":     { "type": "number", "minimum": 0, "maximum": 1 },
           "peripheral": { "type": "number", "minimum": 0, "maximum": 1 },
           "systemic":   { "type": "number", "minimum": 0, "maximum": 1 },
           "reasoning":  { "type": "string" }
         },
         "required": ["axial", "neural", "peripheral", "systemic", "reasoning"]
       }
     }

   USER MESSAGE TEMPLATE (construct from glossary fields):
     "Estimate the fatigue profile for this exercise:
      Name: {name}
      Category: {category}
      Equipment: {equipment}
      Primary muscles: {primary_muscles joined by comma}
      Secondary muscles: {secondary_muscles joined by comma}
      Coaching cues: {cues or 'none'}
      Notes: {notes or 'none'}"

d) Glossary save hook. When a glossary exercise is saved (create or update):
   - If fatigue_profile_source is "manual" -> do nothing, keep user values.
   - Else -> call POST /api/ai/estimate-fatigue-profile with the exercise
     fields. Save the returned profile with source "ai_estimated" and store
     the reasoning string.
   This means EVERY new exercise automatically gets a profile. No user
   action required.

e) Glossary UI. In the glossary editor, add:
   - Four slider inputs (0.0 to 1.0, step 0.05) for axial, neural,
     peripheral, systemic. Labels:
       "Axial (spinal loading)"
       "Neural (CNS demand)"
       "Peripheral (muscle damage)"
       "Systemic (metabolic load)"
   - A source badge: "AI estimated" or "Manual override".
   - If source is "ai_estimated", show the reasoning string as a tooltip
     or subtitle below the sliders.
   - If the user changes ANY slider value, flip source to "manual" and
     clear the reasoning.
   - A "Re-estimate" button that re-calls the AI endpoint and overwrites
     current values (sets source back to "ai_estimated").

f) Bulk estimation shell script. Create a script (e.g. scripts/backfill-fatigue-profiles.sh
   or .py) that:
   - Fetches all glossary exercises from the API.
   - For each exercise where fatigue_profile is null or fatigue_profile_source
     is not "manual":
     - Calls POST /api/ai/estimate-fatigue-profile
     - PATCHes the glossary exercise with the result
   - Logs each exercise name + result for review.
   - Includes a --dry-run flag that prints what would be estimated without
     saving.
   Run this once after deployment to backfill all existing exercises.

g) Per-set fatigue formulas. For a set with weight w, reps r, and relative
   intensity I = w / E_now_for_that_lift (from section 1):

     F_axial      = profile.axial      * w * r
     F_neural     = profile.neural     * r * phi(I)
     F_peripheral = profile.peripheral * w * r
     F_systemic   = profile.systemic   * w * r

   Neural scaling function:
     phi(I) = (max(0, I - 0.60) / 0.40) ^ 2

   This gives:
     I <= 60%  -> 0.00   (warm-ups, light work: zero neural cost)
     I = 70%   -> 0.0625
     I = 80%   -> 0.25
     I = 85%   -> 0.39
     I = 90%   -> 0.5625
     I = 95%   -> 0.766
     I = 100%  -> 1.00

   FALLBACK for I: if E_now is not available for an exercise (not a tracked
   main lift), assume I = 0.70 for the neural calculation.

h) Weekly totals per dimension. Sum per-set values:
     F_d_week = sum(F_d_set) for d in {axial, neural, peripheral, systemic}

i) The four dimensions have DIFFERENT UNITS (neural is in weighted-reps,
   others are in kg*reps). Do NOT add them directly. Normalize per-dimension
   as ratios before combining.

   Per-dimension ACWR:
     ACWR_d = F_d_week / mean(F_d over previous 4 non-deload weeks)

   Per-dimension spike:
     spike_d = clamp((F_d_week - mean(F_d prev 3 non-deload weeks))
               / mean(F_d prev 3 non-deload weeks), 0, 1)

   Composite (used in fatigue index and composite ACWR):
     Dimension weights: axial=0.30, neural=0.30, peripheral=0.25, systemic=0.15
     composite_ACWR  = 0.30*ACWR_a + 0.30*ACWR_n + 0.25*ACWR_p + 0.15*ACWR_s
     composite_spike = 0.30*spike_a + 0.30*spike_n + 0.25*spike_p + 0.15*spike_s

j) Dashboard / Analysis display. Show per-dimension weekly fatigue as a
   four-line or stacked bar chart in the analysis page. Flag:
     "Neural overload" when ACWR_neural > 1.3
     "Axial overload" when ACWR_axial > 1.3


===============================================================================
5. FATIGUE INDEX — FIX (uses output from section 4)
===============================================================================

Formula structure stays the same:
  fatigue_index = 0.40 * failed_compound_ratio
                + 0.35 * load_spike
                + 0.25 * skip_rate

But load_spike now uses the COMPOSITE SPIKE from section 4i instead of raw
volume load spike.

failed_compound_ratio and skip_rate stay as-is.

Flag thresholds stay as-is:
  failed_sets_spike:   failed_compound_ratio > 0.15
  volume_spike:        composite_spike > 0.20
  skipping_sessions:   skip_rate > 0.30
  overreaching_risk:   fatigue_index >= 0.60

Add two new flags from section 4j:
  neural_overload:     ACWR_neural > 1.3
  axial_overload:      ACWR_axial > 1.3


===============================================================================
6. COMPLIANCE — FIX (moderate)
===============================================================================

Exclude sessions that fall in detected deload weeks (from section 2a) from
both numerator and denominator. Only measure adherence to training weeks.


===============================================================================
7. RPE DRIFT — FIX (minor)
===============================================================================

Compute residual instead of raw avg_rpe:
  residual = avg_rpe - (phase.target_rpe_min + phase.target_rpe_max) / 2

Regress on residual over time. Thresholds stay the same:
  slope >= 0.1  -> "up" (flag)
  slope <= -0.1 -> "down" (adapting)
  else          -> "stable"


===============================================================================
8. INOL — NEW METRIC
===============================================================================

Per main lift (squat/bench/deadlift) per week:

  INOL_week = sum(reps / (100 * (1 - I)))

where I = weight / E_now for that lift, summed across all sets of that lift.

Guard: if I >= 1.0, cap denominator: use max(0.01, 1 - I).

Return weekly INOL per lift. Flag:
  < 2.0  : low stimulus
  2.0-4.0: productive
  > 4.0  : overreaching risk

Add to per-lift breakdown table in analysis response.


===============================================================================
9. ACWR — NEW METRIC (uses output from section 4)
===============================================================================

Composite ACWR and per-dimension ACWR are computed in section 4i. Return all
five values (composite + 4 dimensions).

Flag zones (apply to composite and each dimension individually):
  < 0.8  : "undertraining"
  0.8-1.3: "optimal"
  1.3-1.5: "caution"
  > 1.5  : "danger"

Add as new fields in analysis summary response.


===============================================================================
10. RELATIVE INTENSITY DISTRIBUTION — NEW METRIC
===============================================================================

For each working set of a main lift, compute:
  RI = weight / E_now_for_that_lift

Bucket:
  heavy:    RI > 0.85
  moderate: 0.70 <= RI <= 0.85
  light:    RI < 0.70

Return counts and percentages per bucket per lift. Add to per-lift breakdown
or new section in analysis response.


===============================================================================
11. SPECIFICITY RATIO — NEW METRIC
===============================================================================

  SR_narrow = (sets of exact SBD) / (total sets)
  SR_broad  = (sets of SBD + secondary-category exercises sharing a main lift
               glossary category) / (total sets)

Return both. Include in analysis summary.


===============================================================================
12. READINESS SCORE — NEW METRIC
===============================================================================

  R = (1 - (0.30*F_norm + 0.25*D_rpe + 0.20*S_bw + 0.15*M_rate
       + 0.10*(1 - C_pct/100))) * 100

Components:
  F_norm = fatigue_index / 100 (from section 5)
  D_rpe  = clamp((avg_rpe_last_2wk - phase_target_rpe_midpoint) / 2, 0, 1)
  S_bw   = clamp(CV(last 7 weight log entries) / 0.03, 0, 1)
  M_rate = failed_sets / total_sets over last 2 weeks
  C_pct  = compliance percentage (from section 6)

Zones: > 75 green, 50-75 yellow, < 50 red.
Add to dashboard and analysis summary.


===============================================================================
13. ATTEMPT SELECTOR — NEW METRIC (preference-based)
===============================================================================

a) Data model. Add to program meta or preferences:
     attempt_pct_opener: float (default 0.90)
     attempt_pct_second: float (default 0.955)
     attempt_pct_third:  float (default 1.00)

b) For each lift with a projected C_max:
     attempt_k = round_to_nearest_2.5(C_max * pct_k)

c) UI: settings panel with three numeric inputs. Helper text:
     Opener: "Should feel easy under worst conditions (post-cut, bad warmup)"
     Second: "A confident single, builds momentum"
     Third:  "Your projected max — go for it"

d) Only compute when upcoming competition exists in current block.
   Return as part of competition projection response.


===============================================================================
14. FORMULA INFO SECTION — NEW UI COMPONENT
===============================================================================

Add a collapsible section at bottom of analysis page: "How These Numbers
Are Calculated".

- Collapsed by default.
- One expandable panel per metric (14 panels):
    1.  Estimated 1RM
    2.  Progression Rate
    3.  Competition Projection
    4.  Attempt Selection
    5.  Fatigue Model (4 dimensions + AI estimation)
    6.  Fatigue Index
    7.  INOL
    8.  ACWR
    9.  Relative Intensity Distribution
    10. Specificity Ratio
    11. Readiness Score
    12. DOTS Score
    13. RPE Drift
    14. Compliance

- Each panel contains:
    a) One-line plain-English summary.
    b) Formula in styled block (KaTeX if available, else pre-formatted code).
    c) Threshold / flag table where applicable.
    d) "Your current values" line plugging actual computed inputs from the
       current analysis so the user can audit end-to-end.

- Panel content defined in a shared constants file (e.g.
  src/constants/formula-info.ts).
- "Your current values" comes from existing analysis API response.


===============================================================================
CONSTRAINTS
===============================================================================

- Schema additions: fatigue_profile + fatigue_profile_source +
  fatigue_profile_reasoning on glossary exercises, attempt_pct_* on program
  meta. Everything else works with existing data.
- NO hardcoded default fatigue profiles. All profiles come from either AI
  estimation or manual user input. The ONLY fallback is the safe neutral
  { 0.3, 0.3, 0.5, 0.3 } used at analytics computation time if a profile
  is completely missing (section 4b), and this should log a warning.
- The AI estimation endpoint (section 4c) is the ONLY LLM call in the
  entire system. All analytics remain deterministic.
- Use scipy.stats.theilslopes for Theil-Sen regression.
- Preserve ALL existing API response fields. Add new ones alongside.
  Do not break the frontend contract.
- Update the README analytics section to document all formula changes,
  the new fatigue model, and all new metrics.
```