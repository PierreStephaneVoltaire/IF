# Plan 4: Fix Meet Projection, Fatigue Index, Compliance, RPE Drift (Sections 3, 5, 6, 7)

## Context
Plans 1 and 2 fixed the foundation (e1RM, deload detection, progression rate, fatigue dimensions). This plan applies those corrections to the dependent metrics: meet projection now uses corrected e1RM + Theil-Sen, fatigue index uses composite spike instead of raw volume, compliance excludes deloads, and RPE drift computes residual vs target.

## Files to Modify
- `app/src/health/analytics.py` — all 4 fixes
- `utils/powerlifting-app/frontend/src/pages/AnalysisPage.tsx` — minor label update for fatigue spike

## Step 1: Fix Meet Projection (Section 3)

**File:** `app/src/health/analytics.py` — `meet_projection()` function (~line 674)

### 1a. Use corrected inputs (automatic)
The function already calls `_estimate_maxes_from_sessions()` and `progression_rate()`. Since Plan 1 fixed those functions (90th pctl, 6-week window, Theil-Sen), the inputs are automatically corrected. No changes needed for this part.

### 1b. Add ceiling clamp
After computing the projection for each lift, add:
```python
# Ceiling: never project more than 10% above current max
projected = max(current_kg, min(raw_projection, current_kg * 1.10))
```

Currently the code only floors at current: `comp_max = max(comp_max, current_kg)`. Add the ceiling too.

### 1c. Estimate planned deload weeks
Add logic to estimate `planned_deload_weeks`:
```python
# Count deload weeks in the remaining training period
deload_info = _detect_deloads(sessions, program_start)
remaining_weeks = [w for w in deload_info if w['week_index'] >= current_week and w['week_index'] <= comp_week]
planned_deload_weeks = sum(1 for w in remaining_weeks if w['is_deload'])
# Fallback: if not determinable, estimate as floor(calendar_weeks / 4)
if planned_deload_weeks == 0 and calendar_training_weeks > 4:
    planned_deload_weeks = calendar_training_weeks // 4
```

Update effective training weeks calculation:
```python
n_t_eff = weeks_to_comp - taper_weeks - planned_deload_weeks
```

### 1d. Add clamped indicator to return
Add `"ceiling_clamped": bool` per lift so frontend can show when the clamp was applied.

## Step 2: Fix Fatigue Index (Section 5)

**File:** `app/src/health/analytics.py` — `fatigue_index()` function (~line 477)

### 2a. Replace load spike with composite spike
Current: Component 2 is raw volume load spike:
```python
# OLD: (this_week_volume - avg_prev_3_weeks_volume) / avg_prev_3_weeks_volume
```

New: Use composite spike from Plan 2's `_compute_dimensional_spike()`.

The function needs access to glossary data to compute dimensional fatigue. Update signature:
```python
def fatigue_index(sessions, days=14, glossary=None, current_maxes=None):
```

Then replace Component 2:
```python
# Compute weekly fatigue dimensions
weekly_fatigue = _weekly_fatigue_by_dimension(recent_sessions, glossary, program_start, current_maxes or {})
deload_info = _detect_deloads(recent_sessions, program_start)
deload_weeks = [w['week_index'] for w in deload_info if w['is_deload']]
spike_result = _compute_dimensional_spike(weekly_fatigue, deload_weeks)
composite_spike = spike_result['composite']
```

### 2b. Add new flags
Add to the flags list:
```python
if spike_result['dimensions']['neural'] > 0.20:
    flags.append("neural_overload")
if spike_result['dimensions']['axial'] > 0.20:
    flags.append("axial_overload")
```

Wait — the spec says flag when ACWR_neural > 1.3 and ACWR_axial > 1.3. Let me re-read:
> "neural_overload when ACWR_neural > 1.3"
> "axial_overload when ACWR_axial > 1.3"

So these flags use ACWR, not spike. We need to also compute ACWR for these flags. Use `_compute_dimensional_acwr()` from Plan 2:
```python
acwr_result = _compute_dimensional_acwr(weekly_fatigue, deload_weeks)
if acwr_result['dimensions']['neural'] > 1.3:
    flags.append("neural_overload")
if acwr_result['dimensions']['axial'] > 1.3:
    flags.append("axial_overload")
```

### 2c. Update fatigue_components in return dict
Change key name from `"fatigue_load_spike"` to `"composite_spike"`.

## Step 3: Fix Compliance (Section 6)

**File:** `app/src/health/analytics.py` — `session_compliance()` function (~line 574)

### 3a. Exclude deload and break weeks
After computing the current week and session window, call `_detect_deloads()`:
```python
deload_info = _detect_deloads(sessions_in_window, program_start)
deload_weeks = set(w['week_index'] for w in deload_info if w['is_deload'])
break_weeks = set(w['week_index'] for w in deload_info if w['is_break'])
excluded = deload_weeks | break_weeks
```

Filter sessions:
```python
planned = [s for s in sessions_in_window
           if _week_index(s, program_start) not in excluded]
completed = [s for s in planned if s.get('status') in ('logged', 'completed')]
```

### 3b. Add excluded weeks info to return
```python
return {
    "phase": phase_name,
    "planned": len(planned),
    "completed": len(completed),
    "pct": (len(completed) / len(planned) * 100) if planned else 0,
    "excluded_weeks": {
        "deload": sorted(deload_weeks),
        "break": sorted(break_weeks),
    }
}
```

## Step 4: Fix RPE Drift (Section 7)

**File:** `app/src/health/analytics.py` — `rpe_drift()` function (~line 395)

### 4a. Add phases parameter
Update signature:
```python
def rpe_drift(sessions, exercise_name, program_start="", window_weeks=4, phases=None):
```

### 4b. Compute residual instead of raw RPE
After collecting (week_index, avg_rpe) points, if `phases` is provided:
1. For each data point, determine which phase the week falls in
2. Get `target_rpe_midpoint = (phase.target_rpe_min + phase.target_rpe_max) / 2`
3. Compute residual: `residual = avg_rpe - target_rpe_midpoint`
4. Run OLS regression on `(effective_week_index, residual)` instead of `(week_index, avg_rpe)`

If no phases or no target RPE in the phase: fall back to existing raw RPE regression (backward compat).

### 4c. Update call in weekly_analysis()
Pass `phases` to the rpe_drift call:
```python
drift = rpe_drift(filtered_sessions, ex_name, program_start, phases=phases)
```

The `phases` data is available in `weekly_analysis()` from `program.get("phases", [])`.

## Step 5: Update Frontend Label

**File:** `utils/powerlifting-app/frontend/src/pages/AnalysisPage.tsx`

In the fatigue card, change the label from "Load spike" to "Fatigue spike" since the component key changed from `fatigue_load_spike` to `composite_spike`.

Find where `fatigue_components.fatigue_load_spike` is rendered and update:
```typescript
// OLD: fatigue_components.fatigue_load_spike
// NEW: fatigue_components.composite_spike
```

Update the display label accordingly.

## Verification
- Run the app
- Hit `GET /v1/health/analysis/weekly?weeks=4` and verify:
  - Projections have `ceiling_clamped` field
  - Fatigue components use `composite_spike` key
  - Compliance has `excluded_weeks` key
  - RPE drift computes residual when phase targets exist
  - All existing keys still present
- `npm run build` in frontend
