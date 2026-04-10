# Plan 1: e1RM Fix + Deload Detection + Progression Rate (Sections 1, 2)

## Context
The e1RM estimation is broken: Epley/Brzycki run on ALL sets including 10+ rep sets, overshooting actual 1RM by 10-20%. The 90-day max-of-all-e1RMs is too noisy. Progression rate uses OLS on raw top_kg including deloads, biasing slope down. This plan fixes both foundation pieces that everything else depends on.

## Files to Modify
- `app/src/health/analytics.py` (only file this session touches)

## Step 1: Add Conservative Rep Percentage Table

After the existing `_RPE_TABLE_PRIMARY` constant (~line 101), add:

```python
# Conservative percentage table for estimating e1RM when no RPE is recorded
# Only valid for reps 1-5. Derived from RTS-standard conversions.
_CONSERVATIVE_REP_PCT: dict[int, float] = {
    1: 1.000,
    2: 0.955,
    3: 0.925,
    4: 0.898,
    5: 0.875,
}
```

## Step 2: Fix `estimate_1rm()` (line ~247)

Update the standalone function to:
- If RPE is provided (6-10) AND reps <= 6: use RPE table lookup (existing logic)
- Else if RPE is NOT provided AND reps <= 5: use `_CONSERVATIVE_REP_PCT[reps]`
- Else: return None for all estimates (discard the set)
- **Remove Epley and Brzycki entirely.** Do NOT fall back to them under any circumstance.
- Keep `input_weight_kg` in return dict. Return `None` for epley/brzycki keys (or remove them).

New return shape:
```python
{
    "e1rm": float | None,       # The single best estimate
    "method": str | None,       # "rpe_table" | "conservative" | None
    "input_weight_kg": float,
}
```

Keep backward compat by still returning `epley` and `brzycki` keys but set them to `None`.

## Step 3: Fix `_estimate_maxes_from_sessions()` (line ~622)

Current behavior: 90-day lookback, no rep cap, max of all e1RMs.

New behavior:
- **Lookback: 42 days** (6 weeks) instead of 90
- **Rep cap**: RPE sets capped at reps <= 6, non-RPE sets capped at reps <= 5
- **Discard** sets that don't meet the cap — do not estimate from them
- **Collect all qualifying e1RM values** per lift into a list (not just max)
- **Take 90th percentile** of these values (not the max)
- **Require at least 3 qualifying sets** per lift; return None for that lift if fewer

Implementation:
1. Change `lookback_days=90` to `lookback_days=42`
2. Change `best_estimates: dict[str, float]` to `all_estimates: dict[str, list[float]]`
3. In the inner loop where e1RM is computed for each qualifying set:
   - If `rpe` is available and `6 <= int(rpe) <= 10` and `reps <= 6`: RPE lookup
   - Else if no rpe and `reps <= 5`: `_CONSERVATIVE_REP_PCT[reps]`
   - Else: `continue` (skip this set)
4. After the loop, for each lift with >= 3 values in `all_estimates[lift]`:
   - Sort the list
   - Take 90th percentile: `sorted_vals[int(len(sorted_vals) * 0.9)]`
5. If fewer than 2 lifts have estimates, return `INSUFFICIENT_DATA`

## Step 4: Add `_compute_weekly_volume_load()` helper

New private function (~line 200, in helpers section):

```python
def _compute_weekly_volume_load(
    sessions: list[dict],
    program_start: str,
) -> dict[float, float]:
    """Map week_index -> total volume load (sum of sets*reps*kg for all exercises)."""
```

Logic: bucket all exercises in completed sessions by week index, sum `sets * reps * kg`.

## Step 5: Add `_detect_deloads()` helper

New private function:

```python
def _detect_deloads(
    sessions: list[dict],
    program_start: str,
    threshold: float = 0.65,
    rolling_window: int = 4,
) -> list[dict]:
    """Return [{week_index, is_deload, is_break, effective_index}] for each week."""
```

Logic:
1. Call `_compute_weekly_volume_load()` to get weekly totals
2. Iterate weeks in order, maintaining a list of previous non-deload VLs
3. A week is a **deload** if `VL < threshold * rolling_median(previous 4 non-deload weeks)`
4. A week is a **break** if zero sessions or zero volume load
5. Re-index remaining weeks contiguously as effective training weeks

## Step 6: Add `_effective_training_data()` helper

```python
def _effective_training_data(
    sessions: list[dict],
    program_start: str,
) -> tuple[list[dict], dict[int, int]]:
    """Return filtered sessions + mapping of original week_index -> effective week index."""
```

Uses `_detect_deloads()` to remove deload/break sessions and return effective week mapping.

## Step 7: Replace `progression_rate()` (line ~302)

Current: OLS on `(week_index, top_kg)`.

New behavior:
1. Use `_effective_training_data()` to exclude deloads/breaks
2. For each effective training week, compute **best e1RM** using the capped formulas from Step 3 (per-session, take the best qualifying e1RM per week)
3. Regress on `(effective_week_index, e1rm)` using `scipy.stats.theilslopes`
4. Compute R-squared from residuals manually (Theil-Sen doesn't return R²)

Requires `scipy` — check if already in `requirements.txt`. If not, add it.

Return shape (preserve existing keys, add new ones):
```python
{
    "slope_kg_per_week": float,   # Theil-Sen slope (was OLS)
    "r2": float,                  # Computed from residuals
    "points": list,               # Now (effective_week, e1rm) pairs
    "method": "theilsen",         # NEW
    "deload_weeks_excluded": int, # NEW: count of excluded weeks
}
```

## Step 8: Add deload info to `weekly_analysis()` return

In the `weekly_analysis()` function, call `_detect_deloads()` once and add to return dict:

```python
"deload_info": {
    "deload_weeks": [...],       # week indices flagged as deloads
    "break_weeks": [...],        # week indices flagged as breaks
    "effective_training_weeks": 8,
}
```

## Step 9: Remove dead `FATIGUE_MULTIPLIERS` constant

The constant at line ~105 is never used anywhere in the codebase. Remove it.

## Verification
- Ensure `pip install scipy` works (or verify it's already a dependency)
- Run the app: `cd app && python -m uvicorn src.main:app --host 0.0.0.0 --port 8000`
- Hit `GET /v1/health/analysis/weekly?weeks=4` and verify:
  - `current_maxes` values are more conservative than before (90th pctl < max)
  - `deload_info` key is present with correct week classifications
  - Per-lift `progression_rate_kg_per_week` uses Theil-Sen slope
  - All existing response keys still present and correctly shaped
