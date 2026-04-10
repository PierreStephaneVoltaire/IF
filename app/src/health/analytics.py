"""Deterministic training analytics algorithms.

Pure functions — no DynamoDB access, no LLM calls.
All math is stdlib only (math, statistics). JSON-serializable return values.

Canonical DOTS coefficients ported from:
  utils/powerlifting-app/frontend/src/utils/dots.ts
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any, Literal, Optional

from scipy.stats import theilslopes


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# DOTS polynomial coefficients (male / female)
# Source: utils/powerlifting-app/frontend/src/utils/dots.ts
DOTS_COEFFICIENTS: dict[str, dict[str, float]] = {
    "male": {
        "a": -307.75076,
        "b": 24.0900756,
        "c": -0.1918759221,
        "d": 0.0007391293,
        "e": -0.000001093,
    },
    "female": {
        "a": -57.96288,
        "b": 13.6175032,
        "c": -0.1126655495,
        "d": 0.0005158568,
        "e": -0.0000010706,
    },
}

# RPE-based %1RM lookup table (Reactive Training Systems standard)
# Keys: (reps, rpe) -> estimated percent of 1RM
_RPE_1RM_TABLE: dict[tuple[int, int], float] = {
    # RPE 10
    (1, 10): 1.000, (2, 10): 0.960, (3, 10): 0.930, (4, 10): 0.900,
    (5, 10): 0.880, (6, 10): 0.860, (7, 10): 0.840, (8, 10): 0.820,
    (9, 10): 0.800, (10, 10): 0.780,
    # RPE 9.5
    (1, 9): 1.000, (2, 9): 0.950, (3, 9): 0.915, (4, 9): 0.885,
    (5, 9): 0.860, (6, 9): 0.840, (7, 9): 0.820, (8, 9): 0.800,
    (9, 9): 0.780, (10, 9): 0.760,
    # RPE 9
    (1, 9): 1.000, (2, 9): 0.940, (3, 9): 0.900, (4, 9): 0.870,
    (5, 9): 0.845, (6, 9): 0.825, (7, 9): 0.805, (8, 9): 0.785,
    (9, 9): 0.765, (10, 9): 0.745,
    # RPE 8.5
    (1, 8): 1.000, (2, 8): 0.930, (3, 8): 0.885, (4, 8): 0.855,
    (5, 8): 0.830, (6, 8): 0.810, (7, 8): 0.790, (8, 8): 0.770,
    (9, 8): 0.750, (10, 8): 0.730,
    # RPE 8
    (1, 8): 1.000, (2, 8): 0.920, (3, 8): 0.875, (4, 8): 0.845,
    (5, 8): 0.815, (6, 8): 0.795, (7, 8): 0.775, (8, 8): 0.755,
    (9, 8): 0.735, (10, 8): 0.715,
    # RPE 7.5
    (1, 7): 1.000, (2, 7): 0.910, (3, 7): 0.860, (4, 7): 0.830,
    (5, 7): 0.805, (6, 7): 0.785, (7, 7): 0.765, (8, 7): 0.745,
    (9, 7): 0.725, (10, 7): 0.705,
    # RPE 7
    (1, 7): 1.000, (2, 7): 0.900, (3, 7): 0.850, (4, 7): 0.820,
    (5, 7): 0.795, (6, 7): 0.775, (7, 7): 0.755, (8, 7): 0.735,
    (9, 7): 0.715, (10, 7): 0.695,
    # RPE 6.5
    (1, 6): 1.000, (2, 6): 0.890, (3, 6): 0.840, (4, 6): 0.810,
    (5, 6): 0.785, (6, 6): 0.765, (7, 6): 0.745, (8, 6): 0.725,
    (9, 6): 0.705, (10, 6): 0.685,
    # RPE 6
    (1, 6): 1.000, (2, 6): 0.880, (3, 6): 0.830, (4, 6): 0.800,
    (5, 6): 0.775, (6, 6): 0.755, (7, 6): 0.735, (8, 6): 0.715,
    (9, 6): 0.695, (10, 6): 0.675,
}

# Primary RPE table — use integer RPE values (rounded down from half-steps)
_RPE_TABLE_PRIMARY: dict[tuple[int, int], float] = {
    (r, 10): v for (r, rpe), v in _RPE_1RM_TABLE.items() if rpe == 10
}
_RPE_TABLE_PRIMARY.update({
    (1, 10): 1.000, (2, 10): 0.960, (3, 10): 0.930, (4, 10): 0.900,
    (5, 10): 0.880, (6, 10): 0.860, (7, 10): 0.840, (8, 10): 0.820,
    (9, 10): 0.800, (10, 10): 0.780,
    (1, 9): 1.000, (2, 9): 0.940, (3, 9): 0.900, (4, 9): 0.870,
    (5, 9): 0.845, (6, 9): 0.825, (7, 9): 0.805, (8, 9): 0.785,
    (9, 9): 0.765, (10, 9): 0.745,
    (1, 8): 1.000, (2, 8): 0.920, (3, 8): 0.875, (4, 8): 0.845,
    (5, 8): 0.815, (6, 8): 0.795, (7, 8): 0.775, (8, 8): 0.755,
    (9, 8): 0.735, (10, 8): 0.715,
    (1, 7): 1.000, (2, 7): 0.900, (3, 7): 0.850, (4, 7): 0.820,
    (5, 7): 0.795, (6, 7): 0.775, (7, 7): 0.755, (8, 7): 0.735,
    (9, 7): 0.715, (10, 7): 0.695,
    (1, 6): 1.000, (2, 6): 0.880, (3, 6): 0.830, (4, 6): 0.800,
    (5, 6): 0.775, (6, 6): 0.755, (7, 6): 0.735, (8, 6): 0.715,
    (9, 6): 0.695, (10, 6): 0.675,
})

INSUFFICIENT_DATA = {"status": "insufficient_data"}

# Conservative percentage table for estimating e1RM when no RPE is recorded.
# Only valid for reps 1-5. Derived from RTS-standard conversions.
_CONSERVATIVE_REP_PCT: dict[int, float] = {
    1: 1.000,
    2: 0.955,
    3: 0.925,
    4: 0.898,
    5: 0.875,
}


def _num(v: Any) -> float:
    """Convert a value that may be Decimal, str, int, or float to float."""
    if v is None:
        return 0.0
    if isinstance(v, (float, int)):
        return float(v)
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Ordinary least squares. Returns (slope, intercept, r_squared).

    Returns (0.0, 0.0, 0.0) if fewer than 2 data points.
    """
    n = len(xs)
    if n < 2:
        return 0.0, 0.0, 0.0

    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))

    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0, 0.0, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    mean_y = sum_y / n
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 0.0

    return slope, intercept, r_squared


def _pearson(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation coefficient. Returns 0.0 if insufficient data."""
    n = len(xs)
    if n < 3:
        return 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))

    if den_x < 1e-12 or den_y < 1e-12:
        return 0.0
    return num / (den_x * den_y)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _week_index(session: dict, program_start: str) -> Optional[float]:
    """Return week index (0-based float) for a session relative to program start."""
    d = _parse_date(session.get("date", ""))
    start = _parse_date(program_start)
    if d is None or start is None:
        return None
    days = (d - start).days
    return days / 7.0


def _exercise_top_sets(sessions: list[dict], exercise_name: str, program_start: str):
    """Extract (week_index, top_kg) pairs for a specific exercise across sessions.

    Only includes completed sessions where the exercise exists and has a numeric kg.
    """
    points = []
    name_lower = exercise_name.lower()
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _week_index(s, program_start)
        if wk is None:
            continue
        for ex in s.get("exercises", []):
            if ex.get("name", "").lower() != name_lower:
                continue
            kg = ex.get("kg")
            if kg is None:
                continue
            try:
                kg_f = _num(kg)
            except (ValueError, TypeError):
                continue
            if kg_f > 0:
                points.append((wk, kg_f))
    return points


def _get_exercise_sessions(sessions: list[dict], exercise_name: str) -> list[dict]:
    """Filter sessions that contain the named exercise and are completed."""
    name_lower = exercise_name.lower()
    out = []
    for s in sessions:
        if not s.get("completed"):
            continue
        for ex in s.get("exercises", []):
            if ex.get("name", "").lower() == name_lower:
                out.append(s)
                break
    return out


def _compute_weekly_volume_load(
    sessions: list[dict],
    program_start: str,
) -> dict[float, float]:
    """Map week_index -> total volume load (sum of sets*reps*kg for all exercises)."""
    weekly: dict[float, float] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _week_index(s, program_start)
        if wk is None:
            continue
        week_load = 0.0
        for ex in s.get("exercises", []):
            kg = _num(ex.get("kg", 0))
            sets = _num(ex.get("sets", 0))
            reps = _num(ex.get("reps", 0))
            week_load += sets * reps * kg
        weekly[wk] = weekly.get(wk, 0.0) + week_load
    return weekly


def _detect_deloads(
    sessions: list[dict],
    program_start: str,
    threshold: float = 0.65,
    rolling_window: int = 4,
) -> list[dict]:
    """Detect deload and break weeks from session volume patterns.

    Returns list of {week_index, is_deload, is_break, effective_index} for each week.
    A week is a deload if VL < threshold * rolling_median(previous 4 non-deload weeks).
    A week is a break if zero sessions or zero volume load.
    Remaining weeks are re-indexed contiguously as effective training weeks.
    """
    if not program_start:
        program_start = _infer_program_start(sessions)

    weekly_vl = _compute_weekly_volume_load(sessions, program_start)

    # Count sessions per week
    sessions_per_week: dict[float, int] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _week_index(s, program_start)
        if wk is not None:
            sessions_per_week[wk] = sessions_per_week.get(wk, 0) + 1

    # Also track weeks with sessions that may not be completed (for break detection)
    for s in sessions:
        wk = _week_index(s, program_start)
        if wk is not None:
            sessions_per_week[wk] = sessions_per_week.get(wk, 0) + 1

    if not weekly_vl:
        return []

    sorted_weeks = sorted(weekly_vl.keys())
    results = []
    prev_non_deload_vls: list[float] = []

    for wk in sorted_weeks:
        vl = weekly_vl.get(wk, 0.0)
        session_count = sessions_per_week.get(wk, 0)

        is_break = session_count == 0 or vl == 0.0

        is_deload = False
        if not is_break and len(prev_non_deload_vls) >= 1:
            # Use rolling median of up to `rolling_window` previous non-deload weeks
            window = prev_non_deload_vls[-rolling_window:]
            med = median(window)
            if med > 0 and vl < threshold * med:
                is_deload = True

        results.append({
            "week_index": wk,
            "is_deload": is_deload,
            "is_break": is_break,
            "volume_load": vl,
            "effective_index": -1,  # filled below
        })

        if not is_deload and not is_break:
            prev_non_deload_vls.append(vl)

    # Re-index effective training weeks contiguously
    eff_idx = 0
    for r in results:
        if not r["is_deload"] and not r["is_break"]:
            r["effective_index"] = eff_idx
            eff_idx += 1

    return results


def _effective_training_data(
    sessions: list[dict],
    program_start: str,
) -> tuple[list[dict], dict[float, int]]:
    """Return (filtered sessions, mapping of original week_index -> effective week index).

    Removes sessions in deload/break weeks and returns effective week mapping.
    """
    deload_info = _detect_deloads(sessions, program_start)
    excluded_weeks = set()
    effective_map: dict[float, int] = {}
    for d in deload_info:
        if d["is_deload"] or d["is_break"]:
            excluded_weeks.add(d["week_index"])
        else:
            effective_map[d["week_index"]] = d["effective_index"]

    filtered = [
        s for s in sessions
        if _week_index(s, program_start) not in excluded_weeks
    ]
    return filtered, effective_map


# ---------------------------------------------------------------------------
# Public algorithms
# ---------------------------------------------------------------------------

def estimate_1rm(weight_kg: float, reps: int, rpe: Optional[int] = None) -> dict:
    """Estimate 1RM via RPE table or conservative rep percentage.

    Priority cascade (no Epley/Brzycki fallback):
      1. RPE recorded (6-10) AND reps <= 6 → RPE table lookup
      2. No RPE AND reps <= 5 → conservative percentage table
      3. Otherwise → discard (return None)

    Args:
        weight_kg: Load lifted.
        reps: Repetitions performed.
        rpe: Optional RPE (6-10).

    Returns:
        {"e1rm": float | None, "method": str | None, "input_weight_kg": float,
         "epley": None, "brzycki": None, "rpe_based": float | None}
    """
    w = _num(weight_kg)
    e1rm = None
    method = None
    rpe_based = None

    if rpe is not None and 1 <= reps <= 6 and 6 <= int(rpe) <= 10:
        pct = _RPE_TABLE_PRIMARY.get((reps, int(rpe)))
        if pct is not None:
            e1rm = round(w / pct, 1)
            rpe_based = e1rm
            method = "rpe_table"
    elif rpe is None and 1 <= reps <= 5:
        pct = _CONSERVATIVE_REP_PCT.get(reps)
        if pct is not None:
            e1rm = round(w / pct, 1)
            method = "conservative"

    return {
        "e1rm": e1rm,
        "method": method,
        "input_weight_kg": round(w, 1),
        "epley": None,
        "brzycki": None,
        "rpe_based": rpe_based,
    }


def calculate_dots(total_kg: float, bodyweight_kg: float, sex: str) -> float:
    """Calculate DOTS score from total and bodyweight.

    Args:
        total_kg: Combined squat + bench + deadlift total.
        bodyweight_kg: Lifter bodyweight.
        sex: "male" or "female".

    Returns:
        DOTS score rounded to 2 decimal places.
    """
    sex_key = sex.lower()
    if sex_key not in DOTS_COEFFICIENTS:
        raise ValueError(f"Invalid sex: {sex!r}. Expected 'male' or 'female'.")

    c = DOTS_COEFFICIENTS[sex_key]
    bw = _num(bodyweight_kg)
    total = _num(total_kg)
    denom = c["a"] + c["b"]*bw + c["c"]*bw**2 + c["d"]*bw**3 + c["e"]*bw**4

    if abs(denom) < 1e-12:
        return 0.0

    return round((500 / denom) * total, 2)


def progression_rate(sessions: list[dict], exercise_name: str, program_start: str = "") -> dict:
    """Weekly rate of change (kg/week) for a lift via Theil-Sen regression on e1RM.

    Excludes deload/break weeks. Regresses on e1RM estimates per effective
    training week instead of raw top-set kg.

    Args:
        sessions: List of session dicts.
        exercise_name: Name of the exercise (case-insensitive).
        program_start: ISO date string for the program start.

    Returns:
        {"slope_kg_per_week": float, "r2": float, "points": [(week, e1rm), ...],
         "method": "theilsen", "deload_weeks_excluded": int}
        or INSUFFICIENT_DATA.
    """
    if not program_start:
        program_start = _infer_program_start(sessions)

    name_lower = exercise_name.lower()

    # Get deload info for this exercise's sessions
    ex_sessions = _get_exercise_sessions(sessions, exercise_name)
    deload_info = _detect_deloads(ex_sessions, program_start)
    excluded_weeks = set(
        d["week_index"] for d in deload_info if d["is_deload"] or d["is_break"]
    )
    deload_count = len(excluded_weeks)

    # Collect best e1RM per effective training week
    week_e1rm: dict[int, list[float]] = {}
    effective_map = {d["week_index"]: d["effective_index"] for d in deload_info
                     if d["effective_index"] >= 0}

    for s in ex_sessions:
        wk = _week_index(s, program_start)
        if wk is None or wk in excluded_weeks:
            continue
        eff_idx = effective_map.get(wk)
        if eff_idx is None:
            continue

        session_rpe = s.get("session_rpe")
        best_e1rm_week = None

        for ex in s.get("exercises", []):
            if ex.get("name", "").lower() != name_lower:
                continue
            if ex.get("failed", False):
                continue
            kg = _num(ex.get("kg", 0))
            reps = int(_num(ex.get("reps", 0)))
            if kg <= 0 or reps <= 0:
                continue

            e1rm = None
            rpe = session_rpe if session_rpe is not None else None
            if rpe is not None and 1 <= reps <= 6 and 6 <= int(rpe) <= 10:
                pct = _RPE_TABLE_PRIMARY.get((reps, int(rpe)))
                if pct is not None:
                    e1rm = kg / pct
            elif rpe is None and 1 <= reps <= 5:
                pct = _CONSERVATIVE_REP_PCT.get(reps)
                if pct is not None:
                    e1rm = kg / pct

            if e1rm is not None:
                if best_e1rm_week is None or e1rm > best_e1rm_week:
                    best_e1rm_week = e1rm

        if best_e1rm_week is not None:
            week_e1rm.setdefault(eff_idx, []).append(best_e1rm_week)

    if not week_e1rm:
        return {**INSUFFICIENT_DATA, "reason": f"No qualifying e1RM estimates for {exercise_name}"}

    # Take median e1RM per effective week (most robust central tendency)
    xs = sorted(week_e1rm.keys())
    ys = [median(week_e1rm[w]) for w in xs]

    if len(xs) < 2:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 2 effective training weeks with {exercise_name} data"}

    # Theil-Sen regression
    result = theilslopes(ys, xs)
    slope = result[0]
    intercept = result[1]

    # Compute R² from residuals
    predicted = [intercept + slope * x for x in xs]
    mean_y = sum(ys) / len(ys)
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, predicted))
    r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 0.0

    points = [(round(float(x), 1), round(y, 1)) for x, y in zip(xs, ys)]

    return {
        "slope_kg_per_week": round(slope, 2),
        "r2": round(r_squared, 3),
        "points": points,
        "method": "theilsen",
        "deload_weeks_excluded": deload_count,
    }


def volume_intensity_correlation(
    sessions: list[dict],
    exercise_name: str,
    program_start: str = "",
) -> dict:
    """Pearson correlation between weekly volume and intensity for a lift.

    Volume = sets * reps * kg summed per week.
    Intensity = average top-set kg per week.

    Returns:
        {"pearson_r": float, "volume_series": [...], "intensity_series": [...]}
        or INSUFFICIENT_DATA.
    """
    if not program_start:
        program_start = _infer_program_start(sessions)

    name_lower = exercise_name.lower()

    # Bucket by week
    weekly_volume: dict[int, float] = {}
    weekly_intensity: dict[int, float] = {}
    weekly_count: dict[int, int] = {}

    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _week_index(s, program_start)
        if wk is None:
            continue
        week_num = int(wk) + 1  # 1-indexed week number

        for ex in s.get("exercises", []):
            if ex.get("name", "").lower() != name_lower:
                continue
            kg = ex.get("kg")
            try:
                kg_f = _num(kg) if kg is not None else 0
            except (ValueError, TypeError):
                kg_f = 0
            sets = _num(ex.get("sets", 0))
            reps = _num(ex.get("reps", 0))

            weekly_volume[week_num] = weekly_volume.get(week_num, 0) + sets * reps * kg_f
            weekly_intensity[week_num] = weekly_intensity.get(week_num, 0) + kg_f
            weekly_count[week_num] = weekly_count.get(week_num, 0) + 1

    weeks = sorted(weekly_volume.keys())
    if len(weeks) < 3:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 3 weeks of {exercise_name} data"}

    vol_series = [weekly_volume[w] for w in weeks]
    int_series = [weekly_intensity[w] / weekly_count[w] for w in weeks]

    r = _pearson(vol_series, int_series)

    return {
        "pearson_r": round(r, 3),
        "volume_series": [(w, round(v, 0)) for w, v in zip(weeks, vol_series)],
        "intensity_series": [(w, round(i, 1)) for w, i in zip(weeks, int_series)],
    }


def rpe_drift(
    sessions: list[dict],
    exercise_name: str,
    program_start: str = "",
    window_weeks: int = 4,
) -> dict:
    """Detect RPE drift — whether RPE is trending up at the same loads (fatigue signal).

    OLS on (week_index, avg_rpe_per_session) for the exercise over the last N weeks.

    Returns:
        {"slope": float, "drift_direction": "up"|"down"|"stable", "flag": str|null}
        or INSUFFICIENT_DATA.
    """
    if not program_start:
        program_start = _infer_program_start(sessions)

    ex_sessions = _get_exercise_sessions(sessions, exercise_name)
    if len(ex_sessions) < 3:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 3 completed sessions with {exercise_name}"}

    # Filter to window
    if program_start:
        start_date = _parse_date(program_start)
        window_start = start_date + timedelta(weeks=max(0, (len(sessions) // 3) - window_weeks))
    else:
        window_start = None

    points = []
    for s in ex_sessions:
        if window_start:
            d = _parse_date(s.get("date", ""))
            if d and d < window_start:
                continue
        wk = _week_index(s, program_start)
        if wk is None:
            continue
        rpe = None
        rpe_val = s.get("session_rpe")
        if rpe_val is not None:
            rpe = _num(rpe_val)
        else:
            # Fall back to exercise-level RPE
            name_lower = exercise_name.lower()
            for ex in s.get("exercises", []):
                if ex.get("name", "").lower() == name_lower:
                    rpe_raw = ex.get("rpe")
                    rpe = _num(rpe_raw) if rpe_raw is not None else None
                    break
        if rpe is None:
            continue
        try:
            rpe_f = _num(rpe)
        except (ValueError, TypeError):
            continue
        points.append((wk, rpe_f))

    if len(points) < 3:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 3 RPE data points for {exercise_name}"}

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    slope, _, r2 = _ols(xs, ys)

    if slope >= 0.1:
        direction = "up"
        flag = "fatigue"
    elif slope <= -0.1:
        direction = "down"
        flag = "adaptation"
    else:
        direction = "stable"
        flag = None

    return {
        "slope": round(slope, 3),
        "drift_direction": direction,
        "flag": flag,
        "r2": round(r2, 3),
    }


def fatigue_index(sessions: list[dict], days: int = 14) -> dict:
    """Composite fatigue score from observable training data.

    No RPE required. Derived from:
      - failed compound sets ratio (40%)
      - fatigue load spike (35%)
      - session skip rate (25%)
    """
    ref = date.today()
    cutoff = ref - timedelta(days=days)
    recent = []
    for s in sessions:
        d = _parse_date(s.get("date", ""))
        if d and d >= cutoff:
            recent.append(s)

    if len(recent) < 2:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 2 sessions in the last {days} days"}

    # Component 1: failed compound sets ratio (40%)
    total_compound_sets = 0
    failed_compound_sets = 0
    for s in recent:
        for ex in s.get("exercises", []):
            name_lower = ex.get("name", "").lower()
            is_compound = any(kw in name_lower for kw in
                ["squat", "deadlift", "bench", "press", "row", "rdl", "pullup", "chinup"])
            if not is_compound:
                continue
            sets = _num(ex.get("sets", 0))
            total_compound_sets += sets
            if ex.get("failed", False):
                failed_compound_sets += sets

    failed_ratio = _clamp(failed_compound_sets / total_compound_sets, 0, 1) if total_compound_sets > 0 else 0

    # Component 2: fatigue load spike (35%)
    this_week_start = ref - timedelta(days=7)
    this_week_load = 0.0
    prev_weeks_load = []
    for week_offset in range(1, 4):
        wk_start = ref - timedelta(days=7 * (week_offset + 1))
        wk_end = ref - timedelta(days=7 * week_offset)
        wk_load = 0.0
        for s in sessions:
            d = _parse_date(s.get("date", ""))
            if d and wk_start <= d < wk_end:
                for ex in s.get("exercises", []):
                    kg = _num(ex.get("kg", 0))
                    sets = _num(ex.get("sets", 0))
                    reps = _num(ex.get("reps", 0))
                    wk_load += sets * reps * kg
        if wk_load > 0:
            prev_weeks_load.append(wk_load)

    for s in sessions:
        d = _parse_date(s.get("date", ""))
        if d and d >= this_week_start:
            for ex in s.get("exercises", []):
                kg = _num(ex.get("kg", 0))
                sets = _num(ex.get("sets", 0))
                reps = _num(ex.get("reps", 0))
                this_week_load += sets * reps * kg

    avg_prev = sum(prev_weeks_load) / len(prev_weeks_load) if prev_weeks_load else 0
    load_spike = _clamp((this_week_load - avg_prev) / avg_prev, 0, 1) if avg_prev > 0 else 0

    # Component 3: skip rate (25%)
    planned_in_window = [s for s in sessions if _parse_date(s.get("date", ""))
                         and cutoff <= _parse_date(s.get("date", "")) <= ref
                         and s.get("status") in ("planned", "logged", "completed", "skipped")]
    skipped = sum(1 for s in planned_in_window if s.get("status") == "skipped")
    skip_rate = _clamp(skipped / len(planned_in_window), 0, 1) if planned_in_window else 0

    score = round(0.40 * failed_ratio + 0.35 * load_spike + 0.25 * skip_rate, 3)

    flags = []
    if failed_ratio > 0.15:
        flags.append("failed_sets_spike")
    if load_spike > 0.20:
        flags.append("volume_spike")
    if skip_rate > 0.30:
        flags.append("skipping_sessions")
    if score >= 0.6:
        flags.append("overreaching_risk")

    return {
        "score": score,
        "components": {
            "failed_compound_ratio": round(failed_ratio, 3),
            "fatigue_load_spike": round(load_spike, 3),
            "skip_rate": round(skip_rate, 3),
        },
        "flags": flags,
    }


def session_compliance(program: dict, weeks: int = 4) -> dict:
    """Planned vs completed session compliance."""
    sessions = program.get("sessions", [])
    meta = program.get("meta", {})
    program_start = meta.get("program_start", "")
    current_week = _calculate_current_week(program_start)
    cutoff_week = max(1, current_week - weeks + 1)

    planned = [s for s in sessions
               if s.get("status") in ("planned", "logged", "completed", "skipped")
               and cutoff_week <= int(s.get("week_number", 0)) <= current_week]
    completed = [s for s in planned if s.get("status") in ("logged", "completed")]

    planned_count = len(planned)
    completed_count = len(completed)
    compliance_pct = round((completed_count / planned_count) * 100, 1) if planned_count > 0 else 0

    phases = program.get("phases", [])
    current_phase = _find_current_phase(phases, current_week)
    phase_name = current_phase.get("name", "Unknown") if current_phase else "Unknown"

    return {
        "phase": phase_name,
        "planned_sessions": planned_count,
        "completed_sessions": completed_count,
        "compliance_pct": compliance_pct,
    }


def _estimate_maxes_from_comps(competitions: list[dict]) -> dict:
    """Extract best lifts from the most recent completed competition."""
    best: dict[str, float] = {}
    for c in sorted(competitions, key=lambda c: c.get("date", ""), reverse=True):
        results = c.get("results", {})
        if not results:
            continue
        for lift_key, result_key in [("squat", "squat_kg"), ("bench", "bench_kg"), ("deadlift", "deadlift_kg")]:
            val = results.get(result_key)
            if val is not None:
                try:
                    best[lift_key] = _num(val)
                except (ValueError, TypeError):
                    pass
        if best:
            return best
    return {}


def _estimate_maxes_from_sessions(sessions: list[dict], lookback_days: int = 42) -> dict:
    """Estimate current maxes from qualifying sets in the last N days.

    Uses RPE table (reps<=6) or conservative table (reps<=5).
    Takes 90th percentile of qualifying e1RM estimates (not the max).
    Requires at least 3 qualifying sets per lift.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    all_estimates: dict[str, list[float]] = {"squat": [], "bench": [], "deadlift": []}

    for s in sessions:
        d = _parse_date(s.get("date", ""))
        if d is None or d < cutoff:
            continue
        status = s.get("status", "")
        if status in ("planned", "skipped"):
            continue

        session_rpe = s.get("session_rpe")
        for ex in s.get("exercises", []):
            if ex.get("failed", False):
                continue
            name = ex.get("name", "").lower().strip()
            kg = _num(ex.get("kg", 0))
            reps = int(_num(ex.get("reps", 0)))
            if kg <= 0 or reps <= 0:
                continue

            canonical = None
            if name == "squat":
                canonical = "squat"
            elif name in ("bench press", "bench"):
                canonical = "bench"
            elif name == "deadlift":
                canonical = "deadlift"
            if canonical is None:
                continue

            e1rm = None
            rpe = session_rpe if session_rpe is not None else None
            if rpe is not None and 1 <= reps <= 6 and 6 <= int(rpe) <= 10:
                pct = _RPE_TABLE_PRIMARY.get((reps, int(rpe)))
                if pct is not None:
                    e1rm = kg / pct
            elif rpe is None and 1 <= reps <= 5:
                pct = _CONSERVATIVE_REP_PCT.get(reps)
                if pct is not None:
                    e1rm = kg / pct

            if e1rm is not None:
                all_estimates[canonical].append(round(e1rm, 1))

    # Take 90th percentile per lift, require at least 3 qualifying sets
    result: dict[str, float] = {}
    for lift, vals in all_estimates.items():
        if len(vals) >= 3:
            sorted_vals = sorted(vals)
            idx = min(int(len(sorted_vals) * 0.9), len(sorted_vals) - 1)
            result[lift] = sorted_vals[idx]

    return result if len(result) >= 2 else {}


def meet_projection(
    program: dict,
    sessions: list[dict],
    comp_date: Optional[str] = None,
) -> dict:
    """Project competition total from current 1RM estimates and progression trends.

    Falls back to most recent competition results if current_maxes is empty.

    Returns:
        {"squat": float, "bench": float, "deadlift": float, "total": float,
         "confidence": float, "method": str}
        or INSUFFICIENT_DATA.
    """
    meta = program.get("meta", {})
    if comp_date is None:
        comp_date = meta.get("comp_date", "")
    if not comp_date:
        return {**INSUFFICIENT_DATA, "reason": "No competition date set"}

    comp = _parse_date(comp_date)
    if comp is None:
        return {**INSUFFICIENT_DATA, "reason": f"Invalid competition date: {comp_date}"}

    ref = date.today()
    if comp <= ref:
        return {**INSUFFICIENT_DATA, "reason": "Competition date is in the past"}

    weeks_to_comp = (comp - ref).days / 7.0
    program_start = meta.get("program_start", "")
    if not program_start:
        program_start = _infer_program_start(sessions)

    # Get maxes from session estimates
    maxes = _estimate_maxes_from_sessions(sessions)
    method = "session_estimated"

    if not maxes:
        return {**INSUFFICIENT_DATA, "reason": "No session data to estimate maxes from"}

    # Diminishing returns projection parameters — λ based on DOTS level
    # <300 beginner (0.96), 300-400 intermediate (0.90), >=400 advanced (0.85)
    bodyweight = _num(meta.get("current_body_weight_kg", meta.get("bodyweight_kg", 0)))
    sex = meta.get("sex", "male").lower()
    total_now = sum(_num(maxes.get(k, 0)) for k in ("squat", "bench", "deadlift"))
    dots_now = calculate_dots(total_now, bodyweight, sex) if bodyweight > 0 and total_now > 0 else 0
    if dots_now >= 400:
        lam = 0.85
    elif dots_now < 300:
        lam = 0.96
    else:
        lam = 0.90

    # Peaking factor: beginners barely peak, advanced lifters with practiced tapers peak harder
    if dots_now >= 400:
        peak_factor = 1.05
    elif dots_now < 300:
        peak_factor = 1.01
    else:
        peak_factor = 1.03

    # Taper weeks: scale with time remaining (per message.txt guidelines)
    if weeks_to_comp >= 12:
        weeks_taper = 3
    elif weeks_to_comp >= 8:
        weeks_taper = 2
    else:
        weeks_taper = 1
    n_t = max(0, weeks_to_comp - weeks_taper)

    lifts = {}
    for lift_name in ("squat", "bench", "deadlift"):
        current = maxes.get(lift_name)
        if current is None:
            continue
        try:
            current_kg = _num(current)
        except (ValueError, TypeError):
            continue

        # Get progression rate
        prog = progression_rate(sessions, lift_name, program_start)
        delta_w = prog.get("slope_kg_per_week", 0)
        r2 = prog.get("r2", 0)

        # Diminishing returns: gain = delta_w * lambda * (1 - lambda^n_t) / (1 - lambda)
        if n_t > 0 and delta_w > 0:
            projected_gain = delta_w * lam * (1 - lam ** n_t) / (1 - lam)
        else:
            projected_gain = 0

        projected_e1rm = current_kg + projected_gain
        comp_max = projected_e1rm * peak_factor
        comp_max = max(comp_max, current_kg)  # never project below current

        lifts[lift_name] = {
            "current": round(current_kg, 1),
            "projected": round(comp_max, 1),
            "slope_kg_per_week": delta_w,
            "confidence": round(_clamp(r2, 0, 1), 2),
        }

    if not lifts:
        return {**INSUFFICIENT_DATA, "reason": "No lift maxes found (squat, bench, deadlift)"}

    total = sum(v["projected"] for v in lifts.values())
    avg_confidence = sum(v["confidence"] for v in lifts.values()) / len(lifts)

    return {
        "squat": lifts.get("squat", {}).get("projected"),
        "bench": lifts.get("bench", {}).get("projected"),
        "deadlift": lifts.get("deadlift", {}).get("projected"),
        "total": round(total, 1),
        "confidence": round(avg_confidence, 2),
        "weeks_to_comp": round(weeks_to_comp, 1),
        "method": method,
        "lifts": lifts,
    }


def weekly_analysis(
    program: dict,
    sessions: list[dict],
    ref_date: Optional[str] = None,
    weeks: int = 1,
    block: Optional[str] = None,
) -> dict:
    """Full weekly analysis aggregation — the single entry point for tools and API.

    Pulls the last `weeks` weeks of sessions and runs all applicable algorithms.

    Returns structured JSON:
        {"week": int, "block": str, "lifts": {...}, "fatigue_index": float,
         "compliance": {...}, "current_maxes": {...}, "estimated_dots": float|null,
         "projection": {...}, "projection_reason": str|null, "flags": [...],
         "sessions_analyzed": int}
    """
    meta = program.get("meta", {})
    phases = program.get("phases", [])
    program_start = meta.get("program_start", "")

    current_week = _calculate_current_week(program_start)
    current_phase = _find_current_phase(phases, current_week)
    phase_name = current_phase.get("name", "Unknown") if current_phase else "Unknown"

    # Filter sessions by block if specified
    if block:
        sessions = [s for s in sessions if s.get("block", "current") == block]

    # Filter sessions to the analysis window
    ref = _parse_date(ref_date) if ref_date else date.today()
    cutoff = ref - timedelta(weeks=weeks)
    recent_sessions = []
    for s in sessions:
        d = _parse_date(s.get("date", ""))
        if d and d >= cutoff:
            recent_sessions.append(s)

    # Sort by date descending
    recent_sessions.sort(key=lambda s: s.get("date", ""), reverse=True)

    # Per-exercise stats from filtered sessions
    exercise_stats: dict[str, dict[str, Any]] = {}
    for s in recent_sessions:
        for ex in s.get("exercises", []):
            name = ex.get("name", "").strip()
            if not name:
                continue
            kg = _num(ex.get("kg", 0))
            sets = _num(ex.get("sets", 0))
            reps = _num(ex.get("reps", 0))
            vol = sets * reps * kg

            if name not in exercise_stats:
                exercise_stats[name] = {"total_sets": 0, "total_volume": 0.0, "max_kg": 0.0}
            exercise_stats[name]["total_sets"] += int(sets)
            exercise_stats[name]["total_volume"] += vol
            if kg > exercise_stats[name]["max_kg"]:
                exercise_stats[name]["max_kg"] = kg

    for v in exercise_stats.values():
        v["total_volume"] = round(v["total_volume"], 1)
        v["max_kg"] = round(v["max_kg"], 1)

    # Identify main lifts — exact match only (no substring matching)
    exercise_names = set()
    for s in recent_sessions:
        for ex in s.get("exercises", []):
            name = ex.get("name", "").lower().strip()
            if name:
                exercise_names.add(name)

    # Only match the exact big-three lift names
    tracked_lifts = []
    lift_alias_map = {}
    for canonical, output_key in [("squat", "squat"), ("bench press", "bench"), ("deadlift", "deadlift"), ("bench", "bench")]:
        if canonical in exercise_names and output_key not in lift_alias_map:
            lift_alias_map[output_key] = canonical
            if output_key not in tracked_lifts:
                tracked_lifts.append(output_key)

    # Per-lift analysis
    lifts_report = {}
    all_flags = []

    for lift_key in tracked_lifts:
        ex_name = lift_alias_map.get(lift_key, lift_key)
        lift_data: dict[str, Any] = {}

        # Progression
        prog = progression_rate(sessions, ex_name, program_start)
        if "slope_kg_per_week" in prog:
            lift_data["progression_rate_kg_per_week"] = prog["slope_kg_per_week"]
            lift_data["r2"] = prog.get("r2", 0)
        elif prog.get("status") == "insufficient_data":
            lift_data["progression_rate_kg_per_week"] = None
            lift_data["r2"] = None

        # Volume and intensity (compare last week to week before)
        vol_corr = volume_intensity_correlation(sessions, ex_name, program_start)
        if "volume_series" in vol_corr and len(vol_corr["volume_series"]) >= 2:
            vols = [v[1] for v in vol_corr["volume_series"]]
            recent_vol = vols[-1]
            prev_vol = vols[-2] if len(vols) >= 2 else recent_vol
            vol_change = ((recent_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0
            lift_data["volume_change_pct"] = round(vol_change, 1)

            intens = [i[1] for i in vol_corr["intensity_series"]]
            recent_int = intens[-1]
            prev_int = intens[-2] if len(intens) >= 2 else recent_int
            int_change = ((recent_int - prev_int) / prev_int * 100) if prev_int > 0 else 0
            lift_data["intensity_change_pct"] = round(int_change, 1)

        # RPE drift
        drift = rpe_drift(sessions, ex_name, program_start)
        if "drift_direction" in drift:
            lift_data["rpe_trend"] = drift["drift_direction"]
            if drift.get("flag"):
                flag_name = f"{ex_name}_rpe_{drift['flag']}"
                all_flags.append(flag_name)
        else:
            lift_data["rpe_trend"] = "unknown"

        # Failed sets count
        failed_sets = 0
        for s in recent_sessions:
            for ex in s.get("exercises", []):
                ex_lower = ex.get("name", "").lower().strip()
                if ex_lower == ex_name and ex.get("failed", False):
                    failed_sets += _num(ex.get("sets", 0))
        lift_data["failed_sets"] = int(failed_sets)

        lifts_report[ex_name] = lift_data

    # Fatigue index
    fatigue = fatigue_index(sessions, days=weeks * 7)
    fatigue_score = fatigue.get("score", 0) if "score" in fatigue else None
    fatigue_components = fatigue.get("components", {}) if "components" in fatigue else {}
    if fatigue.get("flags"):
        all_flags.extend(fatigue["flags"])

    # Session compliance
    compliance_result = session_compliance(program, weeks=min(weeks, 4))
    compliance_obj = {
        "phase": compliance_result.get("phase", "Unknown"),
        "planned": compliance_result.get("planned_sessions", 0),
        "completed": compliance_result.get("completed_sessions", 0),
        "pct": compliance_result.get("compliance_pct", 0),
    }

    # Deload detection (used by multiple downstream metrics)
    deload_info_raw = _detect_deloads(sessions, program_start)
    deload_info = {
        "deload_weeks": [d["week_index"] for d in deload_info_raw if d["is_deload"]],
        "break_weeks": [d["week_index"] for d in deload_info_raw if d["is_break"]],
        "effective_training_weeks": sum(1 for d in deload_info_raw if d["effective_index"] >= 0),
    }

    # Current maxes: always estimate from session data
    current_maxes_raw = _estimate_maxes_from_sessions(sessions)
    maxes_method = "session_estimated" if current_maxes_raw else "none"

    current_maxes_out = {}
    if current_maxes_raw:
        for lift_key in ("squat", "bench", "deadlift"):
            val = current_maxes_raw.get(lift_key)
            if val is not None:
                try:
                    current_maxes_out[lift_key] = round(_num(val), 1)
                except (ValueError, TypeError):
                    pass
    current_maxes_out["method"] = maxes_method

    # Estimated DOTS
    estimated_dots = None
    bodyweight = _num(meta.get("bodyweight_kg", 0))
    sex = meta.get("sex", "").lower()
    if bodyweight > 0 and sex in ("male", "female") and len(current_maxes_out) >= 3:
        total_kg = sum(
            current_maxes_out.get(lift, 0)
            for lift in ("squat", "bench", "deadlift")
        )
        if total_kg > 0:
            estimated_dots = calculate_dots(total_kg, bodyweight, sex)

    # Meet projection — find upcoming competitions
    projections: list[dict[str, Any]] = []
    projection_reason = None
    competitions = program.get("competitions", [])
    today = date.today()

    # Find all upcoming confirmed/optional competitions
    upcoming: list[dict] = []
    for c in sorted(competitions, key=lambda x: x.get("date", "")):
        if c.get("status") in ("confirmed", "optional"):
            d = _parse_date(c.get("date", ""))
            if d and d > today:
                upcoming.append(c)

    # Pick which comps to project: next + final (if different)
    to_project: list[dict] = []
    if len(upcoming) >= 2:
        to_project = [upcoming[0], upcoming[-1]]
    elif len(upcoming) == 1:
        to_project = [upcoming[0]]

    for comp in to_project:
        proj = meet_projection(program, sessions, comp_date=comp["date"])
        if "total" in proj:
            projections.append({
                "total": proj["total"],
                "confidence": proj["confidence"],
                "weeks_to_comp": proj.get("weeks_to_comp"),
                "method": proj.get("method"),
                "comp_name": comp.get("name"),
            })

    # Fallback to legacy meta.comp_date if no upcoming competitions
    if not projections and not to_project and meta.get("comp_date"):
        proj = meet_projection(program, sessions, comp_date=meta["comp_date"])
        if "total" in proj:
            projections.append({
                "total": proj["total"],
                "confidence": proj["confidence"],
                "weeks_to_comp": proj.get("weeks_to_comp"),
                "method": proj.get("method"),
                "comp_name": None,
            })
        else:
            projection_reason = proj.get("reason", "Insufficient data for projection")

    return {
        "week": current_week,
        "block": phase_name,
        "lifts": lifts_report,
        "fatigue_index": fatigue_score,
        "fatigue_components": fatigue_components,
        "compliance": compliance_obj,
        "current_maxes": current_maxes_out,
        "estimated_dots": estimated_dots,
        "projections": projections,
        "projection_reason": projection_reason,
        "flags": all_flags,
        "sessions_analyzed": len(recent_sessions),
        "exercise_stats": exercise_stats,
        "deload_info": deload_info,
    }


# ---------------------------------------------------------------------------
# Renderer helpers (re-exported for reuse, avoid circular imports)
# ---------------------------------------------------------------------------

def _calculate_current_week(program_start: str) -> int:
    if not program_start:
        return 1
    try:
        start = datetime.strptime(program_start, "%Y-%m-%d").date()
        today = date.today()
        days_since = (today - start).days
        return max(1, (days_since // 7) + 1)
    except ValueError:
        return 1


def _find_current_phase(phases: list[dict], current_week: int) -> Optional[dict]:
    for phase in phases:
        start = phase.get("start_week", 0)
        end = phase.get("end_week", 0)
        if start <= current_week <= end:
            return phase
    return None


def _infer_program_start(sessions: list[dict]) -> str:
    """Infer program start from the earliest session date."""
    dates = []
    for s in sessions:
        d = _parse_date(s.get("date", ""))
        if d:
            dates.append(d)
    if dates:
        return min(dates).isoformat()
    return ""
