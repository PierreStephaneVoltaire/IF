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
from typing import Any, Literal, Optional


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


# ---------------------------------------------------------------------------
# Public algorithms
# ---------------------------------------------------------------------------

def estimate_1rm(weight_kg: float, reps: int, rpe: Optional[int] = None) -> dict:
    """Estimate 1RM via Epley, Brzycki, and (optionally) RPE table.

    Args:
        weight_kg: Load lifted.
        reps: Repetitions performed.
        rpe: Optional RPE (6-10). Enables RPE-based estimation.

    Returns:
        {"epley": float, "brzycki": float, "rpe_based": float | None}
    """
    epley = _num(weight_kg) * (1 + reps / 30) if reps > 0 else _num(weight_kg)
    brzycki = _num(weight_kg) * 36 / (37 - reps) if reps < 37 else _num(weight_kg)

    rpe_based = None
    if rpe is not None and 1 <= reps <= 10 and 6 <= rpe <= 10:
        rpe_rounded = int(rpe)
        pct = _RPE_TABLE_PRIMARY.get((reps, rpe_rounded))
        if pct is not None:
            rpe_based = round(_num(weight_kg) / pct, 1)

    return {
        "epley": round(epley, 1),
        "brzycki": round(brzycki, 1),
        "rpe_based": rpe_based,
        "input_weight_kg": round(_num(weight_kg), 1),
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
    """Weekly rate of change (kg/week) for a lift via OLS on top sets.

    Args:
        sessions: List of session dicts.
        exercise_name: Name of the exercise (case-insensitive).
        program_start: ISO date string for the program start.

    Returns:
        {"slope_kg_per_week": float, "r2": float, "points": [(week, kg), ...]}
        or INSUFFICIENT_DATA.
    """
    if not program_start:
        program_start = _infer_program_start(sessions)

    points = _exercise_top_sets(sessions, exercise_name, program_start)
    if len(points) < 2:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 2 completed sessions with {exercise_name} data"}

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    slope, intercept, r2 = _ols(xs, ys)

    return {
        "slope_kg_per_week": round(slope, 2),
        "r2": round(r2, 3),
        "points": [(round(w, 1), round(k, 1)) for w, k in points],
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
    """Composite fatigue score from recent training signals.

    Components (weighted):
      - avg_rpe (weight 0.4): mean session RPE, normalized to 0-1 (10 = max fatigue)
      - volume_delta (weight 0.35): week-over-week volume change, capped
      - bodyweight_delta (weight 0.25): bodyweight drop (stress indicator), capped

    Returns:
        {"score": float (0-1), "components": {...}, "flags": [...]}
        or INSUFFICIENT_DATA.
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

    # Component 1: average RPE
    rpes = []
    for s in recent:
        rpe_raw = s.get("session_rpe")
        if rpe_raw is not None:
            try:
                rpes.append(_num(rpe_raw))
            except (ValueError, TypeError):
                pass
    avg_rpe = sum(rpes) / len(rpes) if rpes else 7.0
    rpe_norm = _clamp((avg_rpe - 5) / 5, 0, 1)  # 5 RPE = 0, 10 RPE = 1

    # Component 2: volume delta (this week vs last week)
    this_week_start = ref - timedelta(days=7)
    last_week_start = ref - timedelta(days=14)
    vol_this = 0.0
    vol_last = 0.0
    for s in recent:
        d = _parse_date(s.get("date", ""))
        if d is None:
            continue
        for ex in s.get("exercises", []):
            kg = ex.get("kg")
            try:
                kg_f = _num(kg) if kg is not None else 0
            except (ValueError, TypeError):
                kg_f = 0
            sets = _num(ex.get("sets", 0))
            reps = _num(ex.get("reps", 0))
            v = sets * reps * kg_f
            if d >= this_week_start:
                vol_this += v
            elif d >= last_week_start:
                vol_last += v

    if vol_last > 0:
        vol_change = (vol_this - vol_last) / vol_last
    else:
        vol_change = 0.0
    # Volume spike is a fatigue risk; negative = deload (less fatigue)
    vol_norm = _clamp(vol_change, -1, 1) * 0.5 + 0.5  # map -1..1 to 0..1

    # Component 3: bodyweight delta (weight loss = potential stress)
    bws = []
    for s in recent:
        bw = _num(s.get("body_weight_kg"))
        if bw is not None:
            try:
                bws.append((s.get("date", ""), _num(s.get("body_weight_kg"))))
            except (ValueError, TypeError):
                pass

    bw_delta_norm = 0.3  # neutral default
    if len(bws) >= 2:
        bws.sort(key=lambda x: x[0])
        bw_change = bws[-1][1] - bws[0][1]
        # More than 1kg drop in 2 weeks is notable stress
        bw_delta_norm = _clamp(-bw_change / 2.0, 0, 1)

    score = round(rpe_norm * 0.4 + vol_norm * 0.35 + bw_delta_norm * 0.25, 3)

    flags = []
    if rpe_norm >= 0.7:
        flags.append("high_rpe")
    if vol_change > 0.15:
        flags.append("volume_spike")
    if bw_delta_norm >= 0.5:
        flags.append("weight_loss")
    if score >= 0.7:
        flags.append("overreaching_risk")

    return {
        "score": score,
        "components": {
            "avg_rpe": round(avg_rpe, 1),
            "rpe_normalized": round(rpe_norm, 3),
            "volume_change_pct": round(vol_change * 100, 1),
            "volume_normalized": round(vol_norm, 3),
            "bodyweight_delta_norm": round(bw_delta_norm, 3),
        },
        "flags": flags,
    }


def periodization_compliance(program: dict, weeks: int = 4) -> dict:
    """Compare actual volume/intensity against phase targets.

    Looks at the current phase's target RPE ranges and volume prescriptions
    vs what was actually logged.

    Returns:
        {"phase": str, "planned_intensity": float, "actual_intensity": float,
         "planned_volume_sessions": int, "actual_volume_sessions": int,
         "compliance_pct": float}
        or INSUFFICIENT_DATA.
    """
    phases = program.get("phases", [])
    sessions = program.get("sessions", [])
    meta = program.get("meta", {})

    if not phases or not sessions:
        return {**INSUFFICIENT_DATA, "reason": "No phases or sessions in program"}

    current_week = _calculate_current_week(meta.get("program_start", ""))
    current_phase = _find_current_phase(phases, current_week)
    if not current_phase:
        # Fall back to last phase
        current_phase = phases[-1]

    phase_name = current_phase.get("name", "Unknown")

    # Determine phase window
    phase_start_week = current_phase.get("start_week", 1)
    phase_end_week = current_phase.get("end_week", current_week)
    # Look at the last `weeks` weeks within the phase
    lookback_start = max(phase_start_week, current_week - weeks + 1)

    # Filter sessions to the lookback window
    program_start = meta.get("program_start", "")
    phase_sessions = []
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _week_index(s, program_start) if program_start else None
        if wk is None:
            continue
        week_num = int(wk) + 1
        if lookback_start <= week_num <= min(phase_end_week, current_week):
            phase_sessions.append(s)

    if not phase_sessions:
        return {**INSUFFICIENT_DATA, "reason": f"No completed sessions in weeks {lookback_start}-{current_week}"}

    # Planned intensity: use phase target_rpe if available
    planned_intensity = current_phase.get("target_rpe", 8.0)
    try:
        planned_intensity = _num(planned_intensity)
    except (ValueError, TypeError):
        planned_intensity = 8.0

    # Actual intensity: mean session RPE
    actual_rpes = []
    for s in phase_sessions:
        rpe_raw = s.get("session_rpe")
        if rpe_raw is not None:
            try:
                actual_rpes.append(_num(rpe_raw))
            except (ValueError, TypeError):
                pass
    actual_intensity = sum(actual_rpes) / len(actual_rpes) if actual_rpes else 0

    # Volume: count sessions completed vs planned
    # Planned sessions per week from phase
    planned_sessions_per_week = current_phase.get("days_per_week", 4)
    try:
        planned_sessions_per_week = int(planned_sessions_per_week)
    except (ValueError, TypeError):
        planned_sessions_per_week = 4
    weeks_in_window = current_week - lookback_start + 1
    planned_volume_sessions = planned_sessions_per_week * weeks_in_window
    actual_volume_sessions = len(phase_sessions)

    if planned_volume_sessions > 0:
        compliance_pct = round((actual_volume_sessions / planned_volume_sessions) * 100, 1)
    else:
        compliance_pct = 100.0

    # Intensity compliance (how close actual RPE is to target, ±1 RPE tolerance)
    intensity_deviation = abs(actual_intensity - planned_intensity)
    intensity_compliance = max(0, 1.0 - intensity_deviation / 2.0)  # 0 deviation = 100%, 2+ = 0%
    overall_compliance = round(compliance_pct * 0.5 + intensity_compliance * 100 * 0.5, 1)

    return {
        "phase": phase_name,
        "weeks_analyzed": weeks_in_window,
        "planned_intensity": round(planned_intensity, 1),
        "actual_intensity": round(actual_intensity, 1),
        "planned_volume_sessions": planned_volume_sessions,
        "actual_volume_sessions": actual_volume_sessions,
        "compliance_pct": overall_compliance,
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


def _estimate_maxes_from_sessions(sessions: list[dict]) -> dict:
    """Estimate current maxes from the heaviest singles/doubles in recent sessions."""
    top: dict[str, float] = {}
    for s in sessions:
        for ex in s.get("exercises", []):
            name = ex.get("name", "").lower()
            kg = ex.get("kg")
            if kg is None:
                continue
            try:
                kg_f = _num(kg)
            except (ValueError, TypeError):
                continue
            for canonical in ("squat", "bench press", "bench", "deadlift"):
                if canonical in name or name in canonical:
                    key = "bench" if canonical == "bench press" else canonical
                    if key not in top or kg_f > top[key]:
                        top[key] = kg_f
    # Only return if we found at least 2 of the 3 lifts
    if len(top) >= 2:
        return top
    return {}


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

    # Get current maxes — fall back to most recent competition results
    maxes = program.get("current_maxes", {})
    method = "current_maxes"
    if not maxes:
        maxes = _estimate_maxes_from_comps(program.get("competitions", []))
        method = "comp_results"
    if not maxes:
        maxes = _estimate_maxes_from_sessions(sessions)
        method = "session_estimated"

    if not maxes:
        return {**INSUFFICIENT_DATA, "reason": "No current maxes recorded and no competition results or session data to estimate from"}

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
        slope = prog.get("slope_kg_per_week", 0)
        r2 = prog.get("r2", 0)

        # Project forward (cap at 12 weeks of progression to avoid over-extrapolation)
        effective_weeks = min(weeks_to_comp, 12)
        projected = current_kg + slope * effective_weeks
        # Don't project below current
        projected = max(projected, current_kg)

        lifts[lift_name] = {
            "current": round(current_kg, 1),
            "projected": round(projected, 1),
            "slope_kg_per_week": slope,
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
) -> dict:
    """Full weekly analysis aggregation — the single entry point for tools and API.

    Pulls the last `weeks` weeks of sessions and runs all applicable algorithms.

    Returns structured JSON matching the spec:
        {"week": int, "block": str, "lifts": {...}, "fatigue_index": float,
         "compliance": float, "flags": [...], "projection": {...}}
    """
    meta = program.get("meta", {})
    phases = program.get("phases", [])
    program_start = meta.get("program_start", "")

    current_week = _calculate_current_week(program_start)
    current_phase = _find_current_phase(phases, current_week)
    phase_name = current_phase.get("name", "Unknown") if current_phase else "Unknown"

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

    # Identify main lifts
    main_lifts = ["squat", "bench press", "bench", "deadlift", "deadlift (conventional)",
                   "deadlift (sumo)"]
    # Normalize: use whatever names appear in the data
    exercise_names = set()
    for s in recent_sessions:
        for ex in s.get("exercises", []):
            name = ex.get("name", "").lower().strip()
            if name:
                exercise_names.add(name)

    # Determine which main lifts actually have data
    tracked_lifts = []
    lift_alias_map = {}
    for canonical in ["squat", "bench press", "bench", "deadlift"]:
        for ex_name in exercise_names:
            if canonical in ex_name or ex_name in canonical:
                lift_alias_map[canonical] = ex_name
                if canonical not in tracked_lifts:
                    tracked_lifts.append(canonical)
                break

    # If no alias found, just use the exercise names directly
    if not tracked_lifts:
        tracked_lifts = sorted(exercise_names)

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
        elif prog.get("status") == "insufficient_data":
            lift_data["progression_rate_kg_per_week"] = None

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

        lifts_report[ex_name] = lift_data

    # Fatigue index
    fatigue = fatigue_index(sessions, days=weeks * 7)
    fatigue_score = fatigue.get("score", 0) if "score" in fatigue else None
    if fatigue.get("flags"):
        all_flags.extend(fatigue["flags"])

    # Periodization compliance
    compliance_result = periodization_compliance(program, weeks=min(weeks, 4))
    compliance_pct = compliance_result.get("compliance_pct", 0) if "compliance_pct" in compliance_result else None

    # Meet projection (if comp date exists)
    projection = None
    projection_reason = None
    if meta.get("comp_date"):
        proj = meet_projection(program, sessions)
        if "total" in proj:
            projection = {
                "total": proj["total"],
                "confidence": proj["confidence"],
                "weeks_to_comp": proj.get("weeks_to_comp"),
                "method": proj.get("method"),
            }
        else:
            projection_reason = proj.get("reason", "Insufficient data for projection")

    return {
        "week": current_week,
        "block": phase_name,
        "lifts": lifts_report,
        "fatigue_index": fatigue_score,
        "compliance": compliance_pct,
        "flags": all_flags,
        "projection": projection,
        "projection_reason": projection_reason,
        "sessions_analyzed": len(recent_sessions),
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
