# Full Implementation Plan

## 0. Global rule: separate stateful analytics from selected-window summaries

In `tools/health/analytics.py`, update `weekly_analysis()` to build these datasets once:

```python
all_sessions_to_ref = [
    s for s in sessions
    if (d := _parse_date(s.get("date", ""))) is not None
    and d <= ref
]

completed_history_to_ref = [
    s for s in all_sessions_to_ref
    if s.get("completed") or s.get("status") in ("logged", "completed")
]

completed_in_window = [
    s for s in completed_history_to_ref
    if cutoff <= _parse_date(s.get("date", "")) <= end
]
```

Use `completed_history_to_ref` for stateful metrics:

- `fatigue_index`
- `compute_acwr`
- `compute_banister_ffm`
- `_build_peaking_timeline`
- `compute_monotony_strain`
- `compute_decoupling`
- `compute_readiness_score`
- `generate_alerts`

Use `completed_in_window` for selected-window summaries:

- `exercise_stats`
- `sessions_analyzed`
- per-lift failed-set count
- `compute_inol`
- `compute_ri_distribution`
- `compute_specificity_ratio`
- selected-window fatigue dimensions table if desired

Update labels/prose to make the distinction explicit:

- Fatigue = current state as of selected end date
- INOL = selected-window INOL
- RI distribution = selected-window RI distribution
- Specificity = selected-window specificity against timeline target
- ACWR = workload ratio as of selected end date

---

## 1. Fix `fatigue_index()` week indexing

### Problem

`fatigue_index()` mixes zero-based week keys and one-based program week keys.

### Change

Inside `fatigue_index()`, replace this:

```python
w_idx = (d - start_day).days // 7
weeks_dict.setdefault(w_idx, []).append(s)
```

with:

```python
wk = _session_week_num(s, program_start)
if wk is not None:
    weeks_dict.setdefault(wk, []).append(s)
```

Replace this:

```python
start_wk = max(0, (start - start_day).days // 7)
end_wk = max(0, (end - start_day).days // 7)
```

with:

```python
start_wk = _calendar_week_num(start, start_day)
end_wk = _calendar_week_num(end, start_day)
```

Ensure `weekly_dims`, `weeks_dict`, `deload_weeks`, and `window_fis` all use the same one-based week numbering.

---

## 2. Fix `fatigue_index()` date-window handling

### Problem

`fatigue_index(..., days=14)` can still use only one week because `weeks` defaults to `1`.

### Change

Replace:

```python
if window_start:
    start = _parse_date(window_start)
    if start is None:
        start = end - timedelta(days=days)
else:
    start = end - timedelta(days=weeks*7)
```

with:

```python
if window_start:
    start = _parse_date(window_start)
    if start is None:
        start = end - timedelta(days=days)
else:
    start = end - timedelta(days=days)
```

At call sites that intentionally want the selected analysis window, pass:

```python
days=weeks * 7
```

---

## 3. Refactor `weekly_analysis()` metric inputs

### In `weekly_analysis()`, use full completed history for fatigue

Change fatigue call to use `completed_history_to_ref`:

```python
fatigue = fatigue_index(
    completed_history_to_ref,
    days=weeks * 7,
    glossary=glossary,
    current_maxes=current_maxes_raw,
    program_start=program_start,
    ref_date=ref,
    window_start=window_start,
    window_end=window_end,
    weeks=weeks,
    target_rpe_midpoint=target_rpe_mid,
)
```

### Use full completed history for ACWR

Change both ACWR calls to use `completed_history_to_ref`:

```python
acwr_result = compute_acwr(
    completed_history_to_ref,
    glossary,
    program_start,
    current_maxes_raw,
    phases=phases,
    current_week=current_week,
    ref_date=end,
)
```

Avoid duplicate ACWR computation inside `fatigue_dimensions`.

### Use full completed history for Banister, monotony, decoupling, taper

```python
banister = compute_banister_ffm(
    completed_history_to_ref,
    glossary,
    program_start,
    current_maxes_raw or {},
    ref_date=end,
)

monotony_strain = compute_monotony_strain(
    completed_history_to_ref,
    glossary,
    program_start,
    current_maxes_raw or {},
    ref_date=end,
)

decoupling = compute_decoupling(
    completed_history_to_ref,
    glossary,
    program_start,
    current_maxes_raw or {},
    ref_date=end,
)

taper_quality = compute_taper_quality(
    program,
    completed_history_to_ref,
    glossary,
    current_maxes_raw or {},
    program_start,
    ref_date=end,
)
```

### Keep these windowed

```python
inol_result = compute_inol(
    completed_in_window,
    program_start,
    current_maxes_raw,
    program.get("lift_profiles"),
    # add new params below
)

ri_result = compute_ri_distribution(completed_in_window, current_maxes_raw)

specificity_result = compute_specificity_ratio(
    completed_in_window,
    glossary,
    weeks_to_comp=specificity_weeks_to_comp,
)
```

---

## 4. Add fatigue reservoir model

Add constants:

```python
_FATIGUE_RESERVOIR_HALF_LIFE_DAYS = {
    "systemic": 2.0,
    "peripheral": 4.0,
    "axial": 5.0,
    "neural": 6.0,
}

_FATIGUE_RESERVOIR_BASELINE_LOOKBACK_DAYS = 56
_FATIGUE_RESERVOIR_BASELINE_GAP_DAYS = 14
```

Add helper:

```python
def _fatigue_reservoir_series(
    sessions: list[dict],
    glossary: list[dict] | None,
    program_start: str,
    current_maxes: dict,
    ref_date: date,
) -> list[dict[str, Any]]:
    daily_dims = _daily_fatigue_by_dimension(
        sessions,
        glossary,
        program_start,
        current_maxes,
    )

    if not daily_dims:
        return []

    start_day = _parse_date(program_start) or min(daily_dims.keys())
    reservoirs = {"axial": 0.0, "neural": 0.0, "peripheral": 0.0, "systemic": 0.0}
    series = []

    day = start_day
    while day <= ref_date:
        dims = daily_dims.get(day, {"axial": 0.0, "neural": 0.0, "peripheral": 0.0, "systemic": 0.0})

        row = {"date": day}
        for dim in ("axial", "neural", "peripheral", "systemic"):
            decay = math.exp(-math.log(2) / _FATIGUE_RESERVOIR_HALF_LIFE_DAYS[dim])
            reservoirs[dim] = reservoirs[dim] * decay + dims.get(dim, 0.0)
            row[dim] = reservoirs[dim]

        series.append(row)
        day += timedelta(days=1)

    return series
```

Add helper:

```python
def _reservoir_stress_for_day(
    reservoir_series: list[dict[str, Any]],
    target_day: date,
) -> dict[str, Any]:
    by_date = {row["date"]: row for row in reservoir_series}
    current = by_date.get(target_day)
    if not current:
        return {
            "dimensions": {"axial": 0.0, "neural": 0.0, "peripheral": 0.0, "systemic": 0.0},
            "weighted": 0.0,
            "max_dimension": 0.0,
            "composite": 0.0,
            "confidence": "low",
            "context_days_used": 0,
        }

    baseline_start = target_day - timedelta(days=_FATIGUE_RESERVOIR_BASELINE_LOOKBACK_DAYS)
    baseline_end = target_day - timedelta(days=_FATIGUE_RESERVOIR_BASELINE_GAP_DAYS)

    baseline_rows = [
        row for row in reservoir_series
        if baseline_start <= row["date"] <= baseline_end
    ]

    if len(baseline_rows) >= 28:
        confidence = "high"
    elif len(baseline_rows) >= 14:
        confidence = "medium"
    else:
        confidence = "low"

    stresses = {}
    for dim in ("axial", "neural", "peripheral", "systemic"):
        vals = [row.get(dim, 0.0) for row in baseline_rows if row.get(dim, 0.0) > 0]
        if vals:
            baseline = median(vals)
            ratio = current.get(dim, 0.0) / baseline if baseline > 0 else 0.0
            stresses[dim] = _clamp((ratio - 1.0) / 0.75, 0.0, 1.0)
        else:
            stresses[dim] = 0.0

    weighted = sum(stresses[dim] * _DIMENSION_WEIGHTS[dim] for dim in _DIMENSION_WEIGHTS)
    max_dimension = max(stresses.values()) if stresses else 0.0

    composite = 0.60 * max_dimension + 0.40 * weighted

    return {
        "dimensions": {dim: round(stresses[dim], 3) for dim in stresses},
        "weighted": round(weighted, 3),
        "max_dimension": round(max_dimension, 3),
        "composite": round(composite, 3),
        "confidence": confidence,
        "context_days_used": len(baseline_rows),
    }
```

---

## 5. Replace `chronic_load_stress` with reservoir stress in `fatigue_index()`

Inside `fatigue_index()`, compute reservoir series once before weekly loop:

```python
reservoir_series = _fatigue_reservoir_series(
    history_sessions,
    glossary,
    program_start,
    current_maxes or {},
    end,
)
```

Inside each evaluated week:

```python
wk_end_date = start_day + timedelta(days=(wk - 1) * 7 + 6)
wk_end_date = min(wk_end_date, end)

reservoir = _reservoir_stress_for_day(reservoir_series, wk_end_date)
reservoir_stress = reservoir["composite"]
```

Replace current chronic stress block with:

```python
chronic_load_stress = reservoir_stress
```

Add component details:

```python
"reservoir_stress": round(reservoir_stress, 3),
"reservoir_dimension_stress": reservoir["dimensions"],
"reservoir_max_dimension_stress": reservoir["max_dimension"],
"reservoir_weighted_stress": reservoir["weighted"],
```

Update final formula from:

```python
fi_w = (
    0.12 * failure_stress +
    0.12 * acute_spike_stress +
    0.18 * rpe_stress +
    0.28 * chronic_load_stress +
    0.12 * overload_streak +
    0.10 * intensity_density_stress +
    0.08 * monotony_stress
)
```

to:

```python
fi_w = (
    0.10 * failure_stress +
    0.12 * acute_spike_stress +
    0.15 * rpe_stress +
    0.34 * chronic_load_stress +
    0.10 * overload_streak +
    0.10 * intensity_density_stress +
    0.09 * monotony_stress
)
```

Keep output key `chronic_load_stress` for compatibility, but make it reservoir-based.

Add new output keys:

```python
"fatigue_model": "reservoir_v2",
"current_state_fi": round(latest_wk_fi, 3),
"window_mean_fi": round(window_mean, 3),
"window_peak_fi": round(window_peak, 3),
```

Set top-level score to current state, not weighted window average:

```python
score = round(latest_wk_fi, 3)
```

Also include selected-window weighted value separately:

```python
"window_weighted_fi": round(final_fi, 3)
```

---

## 6. Adjust fatigue flags

Update flags:

```python
if components["failed_compound_ratio"] > 0.15:
    flags.append("failed_sets_spike")

if components["composite_spike"] > 0.20:
    flags.append("volume_spike")

if components["rpe_stress"] > 0.50:
    flags.append("high_rpe_stress")

if components["overload_streak"] >= 0.75:
    flags.append("sustained_overload")

if components["chronic_load_stress"] >= 0.65:
    flags.append("high_chronic_load")

if components.get("reservoir_max_dimension_stress", 0) >= 0.75:
    flags.append("localized_fatigue_high")

if components["intensity_density_stress"] >= 0.65:
    flags.append("high_intensity_density")

if components["monotony_stress"] >= 0.65:
    flags.append("high_monotony_strain")
```

---

## 7. Fix `_resolve_intensity()` accessory e1RM lookup

Replace:

```python
e1rm = g.get("e1rm")
```

with:

```python
raw_e1rm = g.get("e1rm_estimate", g.get("e1rm"))

if isinstance(raw_e1rm, dict):
    e1rm = (
        raw_e1rm.get("kg")
        or raw_e1rm.get("e1rm_kg")
        or raw_e1rm.get("estimate_kg")
    )
else:
    e1rm = raw_e1rm
```

Also preserve category lookup.

---

## 8. Improve accessory intensity fallback

In `_resolve_intensity()`, after explicit e1RM and RPE paths, keep Epley fallback but bound by category:

```python
if weight > 0 and reps > 0:
    est = weight * (1 + reps / 30.0)
    epley_i = min(1.0, weight / est)

    if cat in ("squat", "bench", "deadlift", "main", "competition"):
        return _clamp(epley_i, 0.60, 0.95)
    if "variation" in cat:
        return _clamp(epley_i, 0.55, 0.90)
    if "machine" in cat or "compound" in cat:
        return _clamp(epley_i, 0.50, 0.85)
    return _clamp(epley_i, 0.45, 0.80)
```

---

## 9. Add optional RPE multiplier to per-set fatigue

Modify `_per_set_fatigue()` signature:

```python
def _per_set_fatigue(weight: float, reps: int, profile: dict, I: float, rpe: float | None = None) -> dict:
```

Add:

```python
rpe_multiplier = 1.0
if rpe is not None and rpe > 0:
    rpe_multiplier += 0.20 * _clamp((rpe - 7.0) / 3.0, 0.0, 1.0)
```

Apply mostly to peripheral/systemic/neural:

```python
return {
    "axial": profile["axial"] * (weight ** _FATIGUE_AXIAL_EXPONENT) * reps,
    "neural": profile["neural"] * reps * _neural_scaling(I) * math.sqrt(max(weight, 0.0) / _FATIGUE_NEURAL_LOAD_SCALE) * rpe_multiplier,
    "peripheral": profile["peripheral"] * (weight ** _FATIGUE_PERIPHERAL_EXPONENT) * reps * rpe_multiplier,
    "systemic": profile["systemic"] * weight * reps * (1 + _FATIGUE_SYSTEMIC_BETA * I) * rpe_multiplier,
}
```

Update all call sites:

```python
rpe = ex.get("rpe")
if rpe is None:
    rpe = s.get("session_rpe")
sf = _per_set_fatigue(kg, reps, profile, I, _num(rpe) if rpe is not None else None)
```

---

## 10. Fix monotony / strain explosion

Add constants:

```python
_MONOTONY_RELATIVE_SD_FLOOR = 0.10
_MONOTONY_ABSOLUTE_SD_FLOOR = 1.0
_MONOTONY_DISPLAY_CAP = 7.0
```

In `compute_monotony_strain()`, replace:

```python
monotony = mean_load / (sd_load + _MONOTONY_EPSILON) if loads else 0.0
strain = weekly_load * monotony
```

with:

```python
nonzero_days = sum(1 for value in loads if value > 0)
denom = max(
    sd_load,
    mean_load * _MONOTONY_RELATIVE_SD_FLOOR,
    _MONOTONY_ABSOLUTE_SD_FLOOR,
)

monotony_raw = mean_load / denom if mean_load > 0 else 0.0
monotony = min(monotony_raw, _MONOTONY_DISPLAY_CAP)
strain = weekly_load * monotony
```

Add fields:

```python
"monotony_raw": round(float(monotony_raw), 3),
"nonzero_training_days": nonzero_days,
```

Only flag high monotony when enough data exists:

```python
if row["nonzero_training_days"] >= 3 and row["monotony"] > 2.0:
    flags.append("high_monotony")
```

For strain spike, use strain index:

```python
prev_strains = [...]
prev_median = median(prev_strains)
strain_index = row["strain"] / prev_median if prev_median > 0 else None
row["strain_index"] = round(strain_index, 3) if strain_index is not None else None

if strain_index is not None and strain_index > 1.5:
    flags.append("strain_spike")
```

---

## 11. Normalize Banister load through shared helpers

Add helper:

```python
def _banister_dimension_baselines(
    sessions: list[dict],
    glossary: list[dict] | None,
    program_start: str,
    current_maxes: dict,
) -> dict[str, float]:
    weekly_dims = _weekly_fatigue_by_dimension(sessions, glossary, program_start, current_maxes)
    deload_info = _detect_deloads(sessions, program_start)
    deload_weeks = {d["week_num"] for d in deload_info if d["is_deload"] or d["is_break"]}

    valid_weeks = [w for w in weekly_dims if w not in deload_weeks]
    baselines = {"axial": 1.0, "neural": 1.0, "peripheral": 1.0, "systemic": 1.0}

    if len(valid_weeks) >= 3:
        for dim in baselines:
            vals = sorted(weekly_dims[w].get(dim, 0.0) for w in valid_weeks if weekly_dims[w].get(dim, 0.0) > 0)
            if vals:
                baselines[dim] = max(median(vals) / 7.0, 1.0)

    return baselines
```

Add helper:

```python
def _normalized_banister_load(dims: dict[str, float], baselines: dict[str, float]) -> float:
    return 100.0 * (
        0.30 * dims.get("axial", 0.0) / max(baselines.get("axial", 1.0), 1.0)
        + 0.30 * dims.get("neural", 0.0) / max(baselines.get("neural", 1.0), 1.0)
        + 0.25 * dims.get("peripheral", 0.0) / max(baselines.get("peripheral", 1.0), 1.0)
        + 0.15 * dims.get("systemic", 0.0) / max(baselines.get("systemic", 1.0), 1.0)
    )
```

In `compute_banister_ffm()`, replace inline baseline and `norm_load` logic with those helpers.

Return baselines:

```python
"load_baselines": {dim: round(value, 3) for dim, value in baselines.items()},
"model": "normalized_dimension_banister_v2",
```

---

## 12. Fix peaking timeline future TSB unit mismatch

In `_build_peaking_timeline()`, replace:

```python
load = _composite_load_from_dimensions(dims)
```

with:

```python
baselines = banister.get("load_baselines") if isinstance(banister, dict) else None
if not baselines:
    baselines = _banister_dimension_baselines(sessions, glossary, program_start, current_maxes)

load = _normalized_banister_load(dims, baselines)
```

This ensures future projected TSB uses the same load units as historical CTL/ATL.

---

## 13. Add closest peak fallback to peaking timeline

After building projected series, keep the first date inside peaking window:

```python
peak_date = None
peak_delta_days = None
for point in series:
    tsb = point.get("projected_tsb")
    if tsb is None:
        continue
    if 5 <= tsb <= 15:
        peak_date = _parse_date(point["date"])
        if peak_date is not None:
            peak_delta_days = (comp_date - peak_date).days
        break
```

Then add closest fallback:

```python
projected_points = [
    point for point in series
    if point.get("projected_tsb") is not None
]

closest_point = None
if projected_points:
    closest_point = min(
        projected_points,
        key=lambda point: abs(float(point["projected_tsb"]) - 10.0),
    )

closest_peak_date = _parse_date(closest_point["date"]) if closest_point else None
closest_projected_tsb = float(closest_point["projected_tsb"]) if closest_point else None
```

Return:

```python
"peak_date": peak_date.isoformat() if peak_date else None,
"peak_delta_days": peak_delta_days,
"peak_type": "inside_window" if peak_date else "not_reached",
"closest_peak_date": closest_peak_date.isoformat() if closest_peak_date else None,
"closest_projected_tsb": round(closest_projected_tsb, 3) if closest_projected_tsb is not None else None,
```

UI should display `closest_peak_date` if `peak_date` is `None`, with label:

```text
Closest projected peak, not true peaking-window entry
```

---

## 14. Improve planned load resolution

Update `_planned_exercise_weight()` to support load type.

```python
def _planned_exercise_weight(ex: dict, current_maxes: dict[str, Any]) -> float | None:
    load_type = (
        ex.get("load_type")
        or ex.get("loadSource")
        or ex.get("load_source")
        or ""
    )
    load_type = str(load_type).lower().strip()

    kg = _num(ex.get("kg"))
    if kg > 0 and load_type in ("", "absolute", "kg"):
        return round(float(kg), 3)

    canonical = _canonical_lift_from_name(ex.get("name", ""))
    current_max = _num(current_maxes.get(canonical)) if canonical else 0.0

    pct = ex.get("percent") or ex.get("percentage") or ex.get("pct")
    if pct is not None and current_max > 0:
        pct_num = _num(pct)
        if pct_num > 1.5:
            pct_num = pct_num / 100.0
        if 0 < pct_num <= 1.2:
            return round(current_max * pct_num, 3)

    rpe_target = ex.get("rpe_target") or ex.get("rpe")
    if rpe_target is not None and current_max > 0:
        try:
            reps = int(_num(ex.get("reps", 0)))
            rpe_int = int(_num(rpe_target))
        except (TypeError, ValueError):
            return None

        if 1 <= reps <= 6 and 6 <= rpe_int <= 10:
            pct_from_table = _RPE_TABLE_PRIMARY.get((reps, rpe_int))
            if pct_from_table is not None:
                return round(current_max * pct_from_table, 3)

    if load_type == "unspecified":
        return None

    return None
```

Update `_future_planned_daily_fatigue()` to count unresolved sets:

```python
unresolved_sets = 0
...
if sets <= 0 or reps <= 0:
    continue

weight = _planned_exercise_weight(ex, current_maxes)
if weight is None or weight <= 0:
    unresolved_sets += sets
    continue
```

Return both daily fatigue and unresolved count:

```python
return daily, unresolved_sets
```

Update caller:

```python
future_daily_fatigue, future_unresolved_sets = _future_planned_daily_fatigue(...)
```

Return in peaking timeline:

```python
"future_unresolved_sets": future_unresolved_sets,
```

---

## 15. Make INOL phase-aware and trend-aware

Change signature:

```python
def compute_inol(
    sessions: list[dict],
    program_start: str = "",
    current_maxes: dict | None = None,
    lift_profiles: list[dict] | None = None,
    phases: list[dict] | None = None,
    selected_weeks: int = 1,
    all_history_sessions: list[dict] | None = None,
    ref_date: date | None = None,
) -> dict:
```

Call from `weekly_analysis()`:

```python
inol_result = compute_inol(
    completed_in_window,
    program_start,
    current_maxes_raw,
    program.get("lift_profiles"),
    phases=phases,
    selected_weeks=weeks,
    all_history_sessions=completed_history_to_ref,
    ref_date=end,
)
```

### Add phase multiplier helper

```python
def _phase_inol_multiplier(phase: dict | None, effective_week: int | None = None) -> float:
    if not phase:
        return 1.0

    text = f"{phase.get('name', '')} {phase.get('intent', '')}".lower()

    if "deload" in text:
        return 0.45
    if "taper" in text or "peak" in text:
        return 0.65
    if "overreach" in text or _num(phase.get("target_rpe_max")) >= 9:
        return 1.25
    if "hypertrophy" in text or "volume" in text or "accumulation" in text:
        return 1.10
    if "strength" in text:
        return 1.00
    if effective_week is not None and effective_week <= 2:
        return 0.70

    return 1.0
```

### Add uncertainty multiplier helper

```python
def _inol_uncertainty_multiplier(selected_weeks: int) -> tuple[float, float]:
    if selected_weeks <= 1:
        return 0.75, 1.25
    if selected_weeks <= 2:
        return 0.85, 1.15
    return 1.0, 1.0
```

### Apply phase-adjusted thresholds

For each lift/week:

```python
current_phase = _find_current_phase(phases or [], wk)
effective_week = effective_map.get(wk)
phase_mult = _phase_inol_multiplier(current_phase, effective_week)

base_low = thresholds[lift]["low"]
base_high = thresholds[lift]["high"]

low_uncertainty, high_uncertainty = _inol_uncertainty_multiplier(selected_weeks)

adjusted_low = base_low * phase_mult
adjusted_high = base_high * phase_mult

display_low = adjusted_low * low_uncertainty
display_high = adjusted_high * high_uncertainty
```

Return:

```python
"phase_adjusted_thresholds": {
    lift: {
        "low": round(adjusted_low, 2),
        "high": round(adjusted_high, 2),
        "display_low": round(display_low, 2),
        "display_high": round(display_high, 2),
        "phase_multiplier": round(phase_mult, 2),
    }
}
```

### Ramp-up grace

Do not flag low INOL when:

```python
effective_week is not None and effective_week <= 2
```

unless phase text contains `overreach`, `peak`, or target RPE max is at least `9`.

### Add trend pressure

Using `all_history_sessions`, compute per-lift weekly volume and average RI.

Add helper:

```python
def _lift_weekly_volume_ri(
    sessions: list[dict],
    program_start: str,
    current_maxes: dict,
) -> dict[str, dict[int, dict[str, float]]]:
```

For each lift/week, calculate:

```python
volume = sum(sets * reps * kg)
ri_weighted_sum += (kg / max_val) * sets
ri_sets += sets
avg_ri = ri_weighted_sum / ri_sets
```

Then for latest selected week per lift:

```python
prev_weeks = previous 4 weeks with data
volume_ratio = current_volume / median(prev_volumes)
ri_ratio = current_ri / median(prev_ris)

trend_pressure = (
    0.60 * _clamp((volume_ratio - 1.0) / 0.50, 0.0, 1.0)
    + 0.40 * _clamp((ri_ratio - 1.0) / 0.15, 0.0, 1.0)
)
```

Return:

```python
"trend_pressure": {
    lift: {
        "value": round(trend_pressure, 3),
        "volume_ratio": round(volume_ratio, 3),
        "ri_ratio": round(ri_ratio, 3),
    }
}
```

Flagging rules:

```python
if avg > display_high and trend_pressure > 0.35:
    flags.append(f"overreaching_risk_{lift}")
elif avg > display_high:
    flags.append(f"high_inol_monitor_{lift}")

if avg < display_low and not ramp_up_grace:
    flags.append(f"low_stimulus_{lift}")
```

---

## 16. Split readiness into training/external/overall

In `compute_readiness_score()`, keep existing components but calculate:

```python
training_components = []
if f_norm is not None:
    training_components.append((0.45, f_norm))
if d_rpe is not None:
    training_components.append((0.30, d_rpe))
if p_trend is not None:
    training_components.append((0.25, p_trend))

external_components = []
if w_subj is not None:
    external_components.append((0.60, w_subj))
if s_bw is not None:
    external_components.append((0.40, s_bw))
```

Helper:

```python
def _score_from_penalties(components: list[tuple[float, float]]) -> tuple[float, float]:
    available = sum(w for w, _ in components)
    if available <= 0:
        return 50.0, 0.0
    penalty = sum(w * x for w, x in components) / available
    return round(_clamp((1 - penalty) * 100, 0, 100), 1), round(available, 2)
```

Compute:

```python
training_score, training_conf = _score_from_penalties(training_components)
external_score, external_conf = _score_from_penalties(external_components)

if training_conf > 0 and external_conf > 0:
    overall = round(0.70 * training_score + 0.30 * external_score, 1)
elif training_conf > 0:
    overall = training_score
elif external_conf > 0:
    overall = external_score
else:
    overall = 50.0
```

Return:

```python
{
    "score": overall,
    "training_score": training_score,
    "external_score": external_score,
    "zone": zone,
    "components": {...},
    "readiness_confidence": ...,
    "training_readiness_confidence": training_conf,
    "external_readiness_confidence": external_conf,
}
```

Update UI to display:

- Overall Readiness
- Training Readiness
- External Readiness

---

## 17. Fix DOTS bodyweight/sex backend mismatch

In `weekly_analysis()`, replace:

```python
bodyweight = _num(meta.get("bodyweight_kg", 0))
sex = meta.get("sex", "").lower()
```

with:

```python
bodyweight = _num(
    meta.get(
        "current_body_weight_kg",
        meta.get("bodyweight_kg", meta.get("body_weight_kg", 0)),
    )
)

sex = str(
    meta.get("sex")
    or program.get("settings", {}).get("sex")
    or ""
).lower()
```

If sex is not available, return reason:

```python
"estimated_dots_reason": "Missing sex or bodyweight"
```

---

## 18. Improve specificity target competition selection

Add helper:

```python
def _select_specificity_target_competition(program: dict, ref_date: date) -> dict[str, Any] | None:
    competitions = [
        c for c in program.get("competitions", [])
        if c.get("status") in ("confirmed", "optional")
        and (d := _parse_date(c.get("date", ""))) is not None
        and d > ref_date
    ]

    if not competitions:
        meta_date = program.get("meta", {}).get("comp_date")
        if meta_date and (d := _parse_date(meta_date)) and d > ref_date:
            return {
                "name": program.get("meta", {}).get("program_name") or "Upcoming Meet",
                "date": meta_date,
                "selection_reason": "meta_comp_date",
            }
        return None

    goal_dates = set()
    for goal in program.get("goals", []) or []:
        if str(goal.get("priority", "")).lower() != "primary":
            continue
        for key in ("target_competition_dates",):
            for value in goal.get(key, []) or []:
                goal_dates.add(str(value))
        if goal.get("target_competition_date"):
            goal_dates.add(str(goal.get("target_competition_date")))

    for comp in sorted(competitions, key=lambda c: c.get("date", "")):
        if comp.get("date") in goal_dates:
            return {**comp, "selection_reason": "primary_goal"}

    for comp in sorted(competitions, key=lambda c: c.get("date", "")):
        notes = str(comp.get("notes", "")).lower()
        if "qualifier" in notes or "primary" in notes:
            return {**comp, "selection_reason": "competition_notes"}

    nearest = sorted(competitions, key=lambda c: c.get("date", ""))[0]
    return {**nearest, "selection_reason": "nearest_confirmed"}
```

In `weekly_analysis()`:

```python
specificity_target = _select_specificity_target_competition(program, ref)
specificity_comp_date = specificity_target.get("date") if specificity_target else None
```

Return:

```python
"specificity_target_competition": specificity_target,
```

---

## 19. Update `formulaDescriptions.ts`

Update these entries:

### `fatigue_index`

Change summary to:

```typescript
summary: 'Current fatigue state from failures, acute spikes, RPE, intensity density, monotony, and decaying fatigue reservoirs. Recent work matters more, and localized dimension overload is not diluted away by quiet lifts.'
```

Change formula to:

```typescript
formula: `R_d,t = R_d,t-1 * exp(-ln(2) / half_life_d) + Load_d,t
S_d,t = clamp((R_d,t / baseline_d - 1.0) / 0.75, 0, 1)
ReservoirStress = 0.60 * max(S_d) + 0.40 * weighted_mean(S_d)

FI = 0.10*fail + 0.12*spike + 0.15*rpe + 0.34*reservoir
   + 0.10*streak + 0.10*density + 0.09*monotony`
```

Add variables:

```typescript
{ name: 'R_d,t', description: 'Decaying fatigue reservoir for each fatigue dimension' },
{ name: 'half_life_d', description: 'Dimension-specific fatigue half-life in days' },
{ name: 'ReservoirStress', description: 'Max-sensitive chronic fatigue pressure' },
```

### `inol`

Update summary:

```typescript
summary: 'Selected-window stimulus-adjusted INOL with phase-adjusted target ranges, ramp-up grace, uncertainty bands, and volume/intensity trend pressure.'
```

Add to formula:

```typescript
TargetRange_l,w = BaseRange_l * PhaseMultiplier_w
DisplayRange = TargetRange widened for small selected windows
TrendPressure = 0.60*volume_spike + 0.40*RI_spike
```

### `readiness_score`

Update formula:

```typescript
formula: `TrainingReadiness = 100 * (1 - weighted_penalty(fatigue, rpe_drift, performance_trend))
ExternalReadiness = 100 * (1 - weighted_penalty(wellness, bodyweight))
OverallReadiness = 0.70*TrainingReadiness + 0.30*ExternalReadiness`
```

### `monotony_strain`

Update formula:

```typescript
formula: `Monotony = mean(daily_load) / max(SD(daily_load), 0.10*mean(daily_load), load_floor)
Monotony_display = min(Monotony, 7.0)
Strain = weekly_load * Monotony_display
StrainIndex = Strain / rolling_4wk_median(Strain)`
```

### `banister_ffm`

Add note:

```typescript
summary: 'Daily normalized dimension load drives CTL, ATL, and TSB. Future peaking projections use the same normalized load units as historical data.'
```

### `specificity_ratio`

Add note:

```typescript
summary: 'Measures direct and broad powerlifting specificity against the selected target competition timeline, preferring primary-goal meets over nearest meets.'
```

---

## 20. Update README and About page formula docs

Update the same formulas in:

- `README.md`
- `frontend/src/constants/formulaDescriptions.ts`
- `frontend/src/pages/AboutPage.tsx`

Required documentation changes:

1. Fatigue Signal is now a current state using decaying reservoirs.
2. Selected week filter affects window summaries, not fatigue state history.
3. ACWR/Banister/Readiness use full history up to selected end date.
4. INOL is selected-window and phase-adjusted.
5. Monotony uses denominator floor and display cap.
6. Banister projected TSB uses normalized future load.
7. Specificity target competition selection prefers primary goals.
8. Readiness is split into training/external/overall.

---

## 21. Update AI program evaluation prompt

In `tools/health/program_evaluation_ai.py`, add near the top of the prompt:

```text
PRIMARY TASK CLARIFICATION:
This is a PROGRAM ANALYSIS, not a general lifestyle audit. Training structure,
load progression, specificity, fatigue response, lift trends, and competition
alignment are the primary subjects.

Diet, sleep, bodyweight, supplements, and life stress are EXTERNAL CONTEXT.
Use them only to explain uncertainty or confounding. Do not let them dominate
the evaluation unless the training data is otherwise internally coherent and
the external factor is clearly severe enough to explain the issue.
```

Replace current recovery language:

```text
Poor or declining sleep is a confounder for every other metric. Flag it
as a root cause before blaming programming.
```

with:

```text
Sleep/recovery context may explain why training outputs look worse than expected,
but keep it in External Factors / Confounders. Do not make sleep or calories the
main conclusion unless multiple training metrics are normal while
performance/readiness is still deteriorating.
```

Add:

```text
small_changes should primarily be training/program adjustments. Lifestyle
changes belong in external_factors unless they are the only clearly supported
intervention.
```

---

## 22. Update program evaluation output schema

Add field:

```json
"external_factors": [
  {
    "factor": "string",
    "impact": "low | moderate | high",
    "reason": "string",
    "separate_from_program": true
  }
]
```

Update parser/types/frontend card to render `external_factors` separately from:

- `what_is_working`
- `what_is_not_working`
- `small_changes`

---

## 23. Add tests

Add deterministic unit tests for `tools/health/analytics.py`.

### Fatigue week indexing

Test:

- program starts week 1
- sessions across weeks 1-4
- `fatigue_index()` returns context weeks matching actual prior weeks
- no zero/one-based mismatch

### Fatigue filter stability

Test:

- full block, 8-week, and 1-week filters with same `ref_date`
- current fatigue state should be identical or near-identical
- window mean/peak may differ

### Smolov Jr bench specialization

Test:

- high bench frequency/volume
- low squat/deadlift
- peripheral/neural reservoir stress remains high
- `localized_fatigue_high` appears
- fatigue is not diluted away by low axial/squat/deadlift work

### Readiness split

Test:

- high training fatigue with good wellness
- training readiness low, external readiness high
- overall between them

### INOL ramp-up

Test:

- week 1 low INOL
- no `low_stimulus_*` flag during ramp-up
- week 5 low INOL can flag

### INOL trend pressure

Test:

- same INOL but rising volume/RI
- trend pressure increases and high INOL becomes stronger warning

### Monotony explosion

Test:

- one failed set or identical small daily loads
- monotony is capped
- no billion-scale strain
- high monotony requires at least 3 nonzero training days

### Banister projection units

Test:

- historical TSB and projected TSB remain in same numeric range
- projected peak date or closest peak date is returned

### Planned load resolver

Test:

- absolute kg
- percent
- RPE target
- unspecified load
- unresolved sets counted

### Accessory e1RM lookup

Test:

- glossary has `e1rm_estimate`
- `_resolve_intensity()` uses it

### Specificity target

Test:

- multiple competitions
- later primary-goal meet selected over nearest optional meet
- fallback to nearest confirmed when no primary goal exists

---

## 24. Frontend UI updates

### Analysis page

Update labels:

```text
Fatigue Signal
```

to:

```text
Current Fatigue State
```

Show:

- current fatigue state
- selected-window mean
- selected-window peak
- reservoir dimension stress
- context days/weeks used
- confidence

### INOL card

Show:

- selected-window adjusted INOL
- raw INOL
- stimulus coefficient
- phase-adjusted target range
- uncertainty display range
- trend pressure
- ramp-up grace note when applicable

### Readiness card

Show:

- overall readiness
- training readiness
- external readiness
- confidence for each

### Monotony / strain card

Show:

- monotony capped display
- raw monotony in tooltip/details
- strain index
- nonzero training days

### Peaking timeline

If `peak_date` is `None` and `closest_peak_date` exists, show:

```text
Closest projected peak: YYYY-MM-DD
Projected TSB: X
Note: projected TSB does not enter the target peaking window.
```

### Specificity

Show selected target competition:

```text
Specificity target: [Competition Name] ([selection_reason])
```

---

## 25. Backend/types updates

Update `packages/types/index.ts` for changed analytics shape:

### Fatigue

Add optional fields:

```typescript
fatigue_model?: string
current_state_fi?: number
window_weighted_fi?: number
window_mean_fi?: number
window_peak_fi?: number
reservoir_stress?: number
reservoir_dimension_stress?: Record<string, number>
reservoir_max_dimension_stress?: number
reservoir_weighted_stress?: number
```

### INOL

Add:

```typescript
phase_adjusted_thresholds?: Record<string, {
  low: number
  high: number
  display_low: number
  display_high: number
  phase_multiplier: number
}>
trend_pressure?: Record<string, {
  value: number
  volume_ratio: number
  ri_ratio: number
}>
```

### Readiness

Add:

```typescript
training_score?: number
external_score?: number
training_readiness_confidence?: number
external_readiness_confidence?: number
```

### Peaking timeline

Add:

```typescript
peak_type?: 'inside_window' | 'not_reached'
closest_peak_date?: string | null
closest_projected_tsb?: number | null
future_unresolved_sets?: number
```

### Specificity

Add:

```typescript
specificity_target_competition?: {
  name?: string
  date: string
  selection_reason: string
}
```

### Program evaluation

Add:

```typescript
external_factors?: Array<{
  factor: string
  impact: 'low' | 'moderate' | 'high'
  reason: string
  separate_from_program: boolean
}>
```

---

## 26. Implementation order

1. Fix `fatigue_index()` week indexing.
2. Fix `fatigue_index()` date handling.
3. Refactor `weekly_analysis()` into `completed_history_to_ref` and `completed_in_window`.
4. Fix monotony cap/floor.
5. Fix accessory `e1rm_estimate` lookup.
6. Add Banister normalization helpers and fix peaking timeline units.
7. Add closest peak fallback.
8. Improve planned load resolver and unresolved set count.
9. Add fatigue reservoir helpers.
10. Replace chronic stress with reservoir stress.
11. Add INOL phase ranges, uncertainty bands, ramp-up grace, and trend pressure.
12. Split readiness.
13. Fix backend DOTS bodyweight/sex fallback.
14. Add specificity target competition resolver.
15. Update frontend UI rendering.
16. Update types.
17. Update formula docs.
18. Update README/About docs.
19. Update AI prompt and schema.
20. Add unit tests.
21. Run regression checks on existing analysis responses.