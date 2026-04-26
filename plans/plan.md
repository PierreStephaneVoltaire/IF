Implement a window-aware fatigue/readiness analytics overhaul for the powerlifting app.

Primary goal:
The Analysis page fatigue/readiness outputs should help decide whether to continue, pivot, deload, or monitor. The score must not only detect acute failures/spikes. It must also detect sustained high workload, repeated high-intensity exposure, monotony/strain, and phase-relative RPE stress. It must also avoid falsely inflating fatigue for low-load technique-focused phases.

Do not reference or special-case any named program. This needs to generalize across:
- high-volume strength blocks
- low-volume high-intensity peaking blocks
- technique-focused / skill-practice blocks
- bodybuilding or hypertrophy-focused phases
- equipped / gear-specific strength phases
- mixed specificity blocks

Important windowing rule:
The selected Analysis window must control the reported data. If the user selects 1, 2, 4, 8 weeks, or Full Block, the reported fatigue score and component values must represent that selected window. It is acceptable to query earlier history only as contextual baseline data, but earlier history must not be counted as part of the reported workload, RPE, failure rate, or fatigue numerator.

In other words:
- selected-window sessions determine the reported component values
- pre-window sessions may only determine baselines, medians, context, and confidence
- expose how many historical/context weeks were used
- do not silently turn every short-window request into Full Block analysis

Files likely involved:
- `tools/health/analytics.py`
- `backend/src/routes/analytics.ts` if response shape needs transport updates
- `packages/types/index.ts`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/components/analysis/WeeklyData.tsx`
- `frontend/src/constants/formulaDescriptions.ts`
- `README.md`
- `AboutPage.tsx` if formulas are documented there
- relevant tests or add tests if none exist

## 1. Refactor Fatigue Index into weekly component series

Replace the current fatigue formula:

$FI = 0.40 \times failed\_compound\_ratio + 0.35 \times composite\_spike + 0.25 \times rpe\_stress$

with a weekly score:

$FI_w =
0.12 \times failure\_stress_w
+ 0.12 \times acute\_spike\_stress_w
+ 0.18 \times rpe\_stress_w
+ 0.28 \times chronic\_load\_stress_w
+ 0.12 \times overload\_streak_w
+ 0.10 \times intensity\_density\_stress_w
+ 0.08 \times monotony\_stress_w$

Clamp final weekly score to $[0, 1]$.

Reason:
The old formula only detected failures, recent spikes, and high average RPE. It missed stable-but-hard workload, repeated high-intensity exposure, and accumulating fatigue across multiple hard weeks.

## 2. Compute selected-window Fatigue Index from weekly FI values

For each selected Analysis window:
1. Build weekly fatigue components only for weeks overlapping the selected window.
2. Compute $FI_w$ for each week.
3. Return the primary displayed `fatigue_index` as a recency-weighted mean of weekly FI values inside the selected window.

Use:

$weight_w = exp(-ln(2) \times age\_weeks / half\_life)$

where:

$half\_life = clamp(window\_week\_count / 2, 1, 4)$

Then:

$FI_{window} = weighted\_mean(FI_w)$

Also return:
- `latest_week_fi`
- `window_peak_fi`
- `window_mean_fi`
- `fatigue_window_weeks`
- `fatigue_context_weeks_used`
- `fatigue_context_confidence`: `low`, `medium`, or `high`

For a 1-week selector, this should effectively equal the latest/only week in the selected window.

## 3. Component definitions

### 3.1 `failure_stress`

Keep raw `failed_compound_ratio`, but do not use it directly as the formula input.

Use:

$failure\_stress = clamp(failed\_compound\_ratio / 0.15, 0, 1)$

Reason:
The old formula underweighted failures. If $15\%$ failed compound sets is already considered a major flag, then it should normalize near $1.0$, not contribute only a few percentage points.

### 3.2 `acute_spike_stress`

Keep the existing `composite_spike` concept, but normalize it before weighting:

$acute\_spike\_stress = clamp((composite\_spike - 0.05) / 0.35, 0, 1)$

Reason:
Small fluctuations should not matter much. Meaningful spikes should affect the score. But spikes must not be the only way fatigue rises.

### 3.3 `rpe_stress`

Replace average-RPE-only stress with session-level, phase-relative RPE stress.

For each session in the selected week:

If phase target exists:

$rpe\_excess_i = clamp((session\_rpe_i - phase\_target\_midpoint_i) / 2, 0, 1)$

If no phase target exists:

$rpe\_excess_i = clamp((session\_rpe_i - 7.0) / 3.0, 0, 1)$

Then:

$rpe\_base = sqrt(mean(rpe\_excess_i^2))$

$high\_rpe\_frequency = sessions\_with\_rpe\_9plus / sessions\_with\_rpe$

$rpe\_stress = clamp(0.70 \times rpe\_base + 0.30 \times high\_rpe\_frequency, 0, 1)$

Reason:
Plain average RPE hides isolated brutal sessions and ignores programmed phase intent. RMS should make hard sessions matter more than a simple mean.

### 3.4 `chronic_load_stress`

Use the existing four-dimensional fatigue loads:
- axial
- neural
- peripheral
- systemic

For each week and each dimension:

$load\_ratio_d = current\_weekly\_load_d / baseline\_weekly\_load_d$

$dimension\_stress_d = clamp((load\_ratio_d - 1.00) / 0.75, 0, 1)$

Then:

$chronic\_load\_stress =
0.30 \times axial\_stress
+ 0.30 \times neural\_stress
+ 0.25 \times peripheral\_stress
+ 0.15 \times systemic\_stress$

Baseline rules:
- Prefer median of 6-8 non-deload weeks before the evaluated week.
- If fewer than 6 prior non-deload weeks exist, use 3-5 prior non-deload weeks and set confidence to `medium`.
- If fewer than 3 prior non-deload weeks exist, try athlete historical non-deload median before the selected window.
- If still unavailable, do not invent a high chronic stress number. Set unavailable dimensions neutral/omitted and lower `fatigue_context_confidence`.
- Do not use future weeks to calculate baseline for an earlier week.
- Do not use weeks inside the selected reporting window as their own baseline unless no other option exists, and if that fallback is used, mark confidence `low`.

Reason:
Sustained high workload must remain visible even when week-to-week spike disappears.

### 3.5 `overload_streak`

For each week, determine whether that week is an overload week.

A week is an overload week if any of the following are true:
- `chronic_load_stress >= 0.35`
- composite ACWR, if available, is `>= 1.15`
- any main lift adjusted INOL exceeds that lift's high threshold
- `intensity_density_stress >= 0.50`
- weekly strain exceeds rolling 4-week median strain by at least `25%`

Then:

$overload\_streak = clamp(consecutive\_overload\_weeks\_ending\_this\_week / 4, 0, 1)$

The streak calculation may look before the selected window to know whether the streak was already underway, but the reported value should be attached to selected-window weeks only.

Reason:
Three consecutive hard weeks should produce a different signal than one isolated hard week, even if the current week is not a spike.

### 3.6 `intensity_density_stress`

Add a component for high-intensity exposure independent of total volume.

For sets with usable relative intensity:

$heavy\_set\_ratio = sets\_with\_RI\_gte\_0.85 / eligible\_sets$

$very\_heavy\_set\_ratio = sets\_with\_RI\_gte\_0.90 / eligible\_sets$

Then:

$intensity\_density\_stress =
clamp(0.60 \times heavy\_set\_ratio / 0.35 + 0.40 \times very\_heavy\_set\_ratio / 0.15, 0, 1)$

Eligible sets should include canonical SBD and close variations where current max or accessory e1RM can determine RI.

Reason:
Low-volume peaking or high-specificity intensity phases may not have huge volume, but repeated heavy exposures still create meaningful neural/specific fatigue.

### 3.7 `monotony_stress`

Use existing Foster monotony/strain where available:

$monotony\_stress =
max(
clamp((monotony - 1.5) / 1.0, 0, 1),
clamp((strain / rolling\_4wk\_median\_strain - 1.0) / 0.5, 0, 1)
)$

If strain baseline is missing, use monotony only and mark confidence appropriately.

Reason:
Repeated similar loading can be fatiguing even when ACWR is stable and there is no obvious spike.

## 4. Response shape / backward compatibility

Keep existing fields so the frontend does not break:
- `fatigue_index`
- `failed_compound_ratio`
- `composite_spike`
- `rpe_stress`

Add expanded fields:

`fatigue_components`:
- `failed_compound_ratio`
- `failure_stress`
- `composite_spike`
- `acute_spike_stress`
- `rpe_stress`
- `chronic_load_stress`
- `overload_streak`
- `intensity_density_stress`
- `monotony_stress`
- `latest_week_fi`
- `window_mean_fi`
- `window_peak_fi`
- `fatigue_window_weeks`
- `fatigue_context_weeks_used`
- `fatigue_context_confidence`

For old UI component names, map:
- displayed `failed_compound_ratio` can still show raw failed ratio
- displayed `composite_spike` can still show raw spike
- displayed `rpe_stress` should show the new RPE stress

But the Fatigue Signal breakdown should preferably display the new components.

## 5. Thresholds

Update fatigue thresholds:

- Low: $FI < 0.25$
- Moderate: $0.25 \le FI < 0.45$
- High: $0.45 \le FI < 0.65$
- Very High: $FI \ge 0.65$

Existing high/overreaching flags should update accordingly:
- `fatigue_high` if $FI \ge 0.45$
- `overreaching_risk` if $FI \ge 0.65$

Add flags:
- `sustained_overload` if `overload_streak >= 0.75`
- `high_chronic_load` if `chronic_load_stress >= 0.65`
- `high_intensity_density` if `intensity_density_stress >= 0.65`
- `high_monotony_strain` if `monotony_stress >= 0.65`
- preserve existing failed/spike/RPE flags where still relevant

## 6. Readiness score missing-data fix

Current readiness fallbacks penalize missing data with synthetic values like `0.5`. Replace that with available-component reweighting.

Current formula concept remains:

$R = (1 - penalty) \times 100$

But compute:

$penalty = sum(w_i \times x_i) / sum(w_i)$ only over available components.

Components:
- fatigue: weight `0.30`
- RPE drift: weight `0.25`
- subjective wellness: weight `0.20`
- performance trend: weight `0.15`
- bodyweight deviation: weight `0.10`

If a component is unavailable, omit it and renormalize.

Add:
- `readiness_confidence = available_weight / total_weight`
- optionally expose which readiness components were missing

Reason:
Missing wellness or bodyweight logs should reduce confidence, not automatically reduce readiness.

## 7. Volume landmarks MRV fix

Current MRV depends on `next_week_fi > 0.60` or one negative e1RM delta. Update MRV to use repeated evidence.

For each set bin, require at least 3 observations when possible.

MRV should be the lowest bin where any of these hold:
- median next-week FI is at least `0.55`
- probability of negative next-week e1RM change is at least `0.60`
- median next-week readiness is below `60`

Use the new fatigue index.

Reason:
One noisy bad week should not define MRV, and old FI underdetected sustained overload.

## 8. Normalize Banister load before fixed TSB labels

Current Banister uses raw dimensional load even though dimensional loads are kg-powered and athlete-scale-dependent. Add normalized load index.

Use:

$load\_index_t =
100 \times (
0.30 \times F_{axial,t} / baseline_{axial}
+ 0.30 \times F_{neural,t} / baseline_{neural}
+ 0.25 \times F_{peripheral,t} / baseline_{peripheral}
+ 0.15 \times F_{systemic,t} / baseline_{systemic}
)$

Then compute CTL/ATL/TSB from `load_index_t`.

Keep thresholds only if the scale is now indexed. If insufficient baseline exists, return lower confidence or avoid strong labels.

Reason:
Fixed TSB labels like `-30` only make sense if the load scale is normalized.

## 9. Improve intensity fallback for non-SBD/accessories

Currently non-SBD exercises fall back to `I = 0.70` for neural scaling. Replace fallback order:

1. canonical SBD current max
2. manual max if available
3. conservative backend current max
4. best recent RPE-table estimate
5. capped Epley fallback for analytics only
6. glossary accessory e1RM estimate
7. category default intensity

Suggested category defaults:
- main SBD variation: `0.75`
- close variation: `0.70`
- machine compound: `0.65`
- isolation: `0.55`

For analytics-only Epley fallback:

$e1RM = kg \times (1 + reps / 30)$

Use a conservative cap where possible, such as not exceeding a plausible ratio to a recent top single.

Reason:
The app already stores accessory e1RM estimates. A flat `0.70` makes all accessory neural stress too similar and can distort bodybuilding/hypertrophy and accessory-heavy phases.

## 10. Frontend updates

Update Fatigue Signal card to display:
- primary `fatigue_index` percentage
- label from new thresholds
- component breakdown:
  - failure stress
  - acute spike stress
  - RPE stress
  - chronic load stress
  - overload streak
  - intensity density
  - monotony/strain
- context confidence
- latest week FI and window peak FI if available

Make clear in UI copy:
- selected window controls the reported score
- historical context may be used only for baseline normalization

Do not imply that the 1-week selector is secretly full-block analysis.

## 11. Documentation updates

Update these in the same PR:
- `README.md`
- `frontend/src/constants/formulaDescriptions.ts`
- `AboutPage.tsx` if it includes formula descriptions

Replace old fatigue formula documentation with the new weekly/windowed formula.

Include notes:
- skip rate remains excluded from fatigue
- missing wellness/bodyweight reduces readiness confidence, not readiness score directly
- short windows may use prior history for baseline context only
- the fatigue index is a training-strain/fatigue-risk estimate, not a medical recovery diagnosis

## 12. Tests / validation scenarios

Add or update tests for these cases:

1. Stable high workload:
   - no failures
   - no new spike after week 1
   - moderate-high workload sustained for several weeks
   - expected: fatigue should not collapse near zero; chronic load and overload streak should contribute

2. Technique-focused block:
   - low RI
   - low RPE
   - high specificity but low load
   - expected: fatigue remains low unless monotony/RPE/failures say otherwise

3. High-intensity low-volume peaking:
   - low total volume
   - many sets at RI `>= 0.85` or `>= 0.90`
   - expected: intensity density and neural load contribute even when volume is low

4. Hypertrophy/bodybuilding-style phase:
   - high peripheral/systemic volume
   - lower RI
   - few or no SBD failures
   - expected: chronic peripheral/systemic load contributes; neural stress may remain modest

5. Missing wellness/bodyweight:
   - expected: readiness confidence drops, but readiness is not automatically penalized by fake `0.5` components

6. Windowing:
   - last 1 week score changes when only that week changes
   - last 2/4/8 week scores use only selected-window weeks for reported loads/components
   - pre-window data can change baseline/context confidence but must not be counted as selected-window workload
   - Full Block still works but should not be required for accurate short-window analysis

7. Backward compatibility:
   - existing frontend does not crash if it reads old fields
   - new fields are present when available