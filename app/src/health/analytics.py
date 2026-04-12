"""Deterministic training analytics algorithms.

Pure functions — no DynamoDB access, no LLM calls.
All math is stdlib only (math, statistics). JSON-serializable return values.

Canonical DOTS coefficients ported from:
  utils/powerlifting-app/frontend/src/utils/dots.ts
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any, Literal, Optional

from scipy.stats import theilslopes


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

_RPE_TABLE_PRIMARY: dict[tuple[int, int], float] = {
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
}

INSUFFICIENT_DATA = {"status": "insufficient_data"}

_DEFAULT_FATIGUE_PROFILE = {
    "axial": 0.3,
    "neural": 0.3,
    "peripheral": 0.5,
    "systemic": 0.3,
}

_CONSERVATIVE_REP_PCT: dict[int, float] = {
    1: 1.000,
    2: 0.955,
    3: 0.925,
    4: 0.898,
    5: 0.875,
}

# Primary high-fatiguing lifts for deload intensity condition check.
_PRIMARY_LIFT_NAMES: frozenset[str] = frozenset({"squat", "deadlift"})


def _num(v: Any) -> float:
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


def _count_failed_sets(ex: dict) -> int:
    failed_arr = ex.get("failed_sets")
    if failed_arr and isinstance(failed_arr, list):
        return sum(1 for f in failed_arr if f)
    if ex.get("failed", False):
        return int(_num(ex.get("sets", 0)))
    return 0


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ols(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
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


def _session_week_num(session: dict, program_start: str = "") -> Optional[int]:
    """Return the integer week number for a session.

    Uses the session's week_number field if available (preferred — always an integer).
    Falls back to computing from program_start date.
    """
    wn = session.get("week_number")
    if wn is not None:
        try:
            return int(wn)
        except (ValueError, TypeError):
            pass
    if program_start:
        d = _parse_date(session.get("date", ""))
        start = _parse_date(program_start)
        if d is not None and start is not None:
            return max(1, (d - start).days // 7 + 1)
    return None


def _week_index(session: dict, program_start: str) -> Optional[float]:
    """Float week offset — kept for legacy callers; use _session_week_num for grouping."""
    d = _parse_date(session.get("date", ""))
    start = _parse_date(program_start)
    if d is None or start is None:
        return None
    return (d - start).days / 7.0


def _get_exercise_sessions(sessions: list[dict], exercise_name: str) -> list[dict]:
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


def _compute_weekly_volume_load(sessions: list[dict], program_start: str) -> dict[int, float]:
    weekly: dict[int, float] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _session_week_num(s, program_start)
        if wk is None:
            continue
        week_load = 0.0
        for ex in s.get("exercises", []):
            week_load += _num(ex.get("sets", 0)) * _num(ex.get("reps", 0)) * _num(ex.get("kg", 0))
        weekly[wk] = weekly.get(wk, 0.0) + week_load
    return weekly


def _best_primary_e1rm_for_sessions(w_sessions: list[dict]) -> Optional[float]:
    best: Optional[float] = None
    for s in w_sessions:
        session_rpe = s.get("session_rpe")
        for ex in s.get("exercises", []):
            if ex.get("name", "").lower().strip() not in _PRIMARY_LIFT_NAMES:
                continue
            if _count_failed_sets(ex) > 0:
                continue
            kg = _num(ex.get("kg", 0))
            reps = int(_num(ex.get("reps", 0)))
            if kg <= 0 or reps <= 0:
                continue
            rpe = session_rpe
            e1rm = None
            if rpe is not None and 1 <= reps <= 6 and 6 <= int(rpe) <= 10:
                pct = _RPE_TABLE_PRIMARY.get((reps, int(rpe)))
                if pct:
                    e1rm = kg / pct
            elif rpe is None and 1 <= reps <= 5:
                pct = _CONSERVATIVE_REP_PCT.get(reps)
                if pct:
                    e1rm = kg / pct
            if e1rm is not None and (best is None or e1rm > best):
                best = e1rm
    return best


def _detect_deloads(
    sessions: list[dict],
    program_start: str,
    threshold: float = 0.65,
    threshold_no_main: float = 0.75,
    rolling_window: int = 4,
) -> list[dict]:
    """Detect deload and break weeks.

    A week is a DELOAD if:
      1. VL < threshold * median(prev rolling_window non-deload weeks)
         (threshold_no_main if no squat/deadlift present)
      2. Intensity condition (only when primary lifts present):
         - RPE path: all primary RPEs <= 6
         - e1RM path: best e1RM dropped >= 10% vs prev 2 non-deload weeks
         - Stagnation is NOT a deload
    A week is a BREAK if zero volume load.
    week_index == week_num (int) for backward compat.
    """
    if not program_start:
        program_start = _infer_program_start(sessions)

    week_sessions: dict[int, list[dict]] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _session_week_num(s, program_start)
        if wk is None:
            continue
        week_sessions.setdefault(wk, []).append(s)

    if not week_sessions:
        return []

    sorted_weeks = sorted(week_sessions.keys())
    results = []
    prev_non_deload_vls: list[float] = []
    prev_non_deload_e1rms: list[float] = []

    for wk in sorted_weeks:
        w_sessions = week_sessions[wk]

        vl = sum(
            _num(ex.get("sets", 0)) * _num(ex.get("reps", 0)) * _num(ex.get("kg", 0))
            for s in w_sessions for ex in s.get("exercises", [])
        )
        is_break = vl == 0.0

        has_main_lift = any(
            ex.get("name", "").lower().strip() in _PRIMARY_LIFT_NAMES
            for s in w_sessions for ex in s.get("exercises", [])
        )

        is_deload = False
        if not is_break and len(prev_non_deload_vls) >= 1:
            med = median(prev_non_deload_vls[-rolling_window:])
            thr = threshold if has_main_lift else threshold_no_main
            volume_condition = med > 0 and vl < thr * med

            if volume_condition:
                if not has_main_lift:
                    is_deload = True
                else:
                    primary_rpes: list[float] = []
                    for s in w_sessions:
                        if not any(
                            ex.get("name", "").lower().strip() in _PRIMARY_LIFT_NAMES
                            for ex in s.get("exercises", [])
                        ):
                            continue
                        rpe = s.get("session_rpe")
                        if rpe is not None:
                            primary_rpes.append(_num(rpe))
                        else:
                            for ex in s.get("exercises", []):
                                if ex.get("name", "").lower().strip() in _PRIMARY_LIFT_NAMES:
                                    ex_rpe = ex.get("rpe")
                                    if ex_rpe is not None:
                                        primary_rpes.append(_num(ex_rpe))

                    if primary_rpes:
                        intensity_condition = all(r <= 6 for r in primary_rpes)
                    else:
                        week_e1rm = _best_primary_e1rm_for_sessions(w_sessions)
                        if week_e1rm is not None and prev_non_deload_e1rms:
                            best_prev = max(prev_non_deload_e1rms[-2:])
                            intensity_condition = week_e1rm < best_prev * 0.90
                        else:
                            intensity_condition = False
                    is_deload = intensity_condition

        week_best_e1rm = _best_primary_e1rm_for_sessions(w_sessions)

        results.append({
            "week_num": wk,
            "week_index": wk,
            "is_deload": is_deload,
            "is_break": is_break,
            "volume_load": vl,
            "effective_index": -1,
        })

        if not is_deload and not is_break:
            prev_non_deload_vls.append(vl)
            if week_best_e1rm is not None:
                prev_non_deload_e1rms.append(week_best_e1rm)

    eff_idx = 0
    for r in results:
        if not r["is_deload"] and not r["is_break"]:
            r["effective_index"] = eff_idx
            eff_idx += 1

    return results


def _effective_training_data(
    sessions: list[dict],
    program_start: str,
) -> tuple[list[dict], dict[int, int]]:
    deload_info = _detect_deloads(sessions, program_start)
    excluded_weeks: set[int] = set()
    effective_map: dict[int, int] = {}
    for d in deload_info:
        if d["is_deload"] or d["is_break"]:
            excluded_weeks.add(d["week_num"])
        else:
            effective_map[d["week_num"]] = d["effective_index"]
    filtered = [s for s in sessions if _session_week_num(s, program_start) not in excluded_weeks]
    return filtered, effective_map


# ---------------------------------------------------------------------------
# Fatigue dimension helpers
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _get_fatigue_profile(exercise_name: str, glossary: list[dict] | None = None) -> dict:
    if glossary:
        name_lower = exercise_name.lower().strip()
        for ex in glossary:
            if ex.get("name", "").lower().strip() == name_lower:
                profile = ex.get("fatigue_profile")
                if isinstance(profile, dict) and all(k in profile for k in ("axial", "neural", "peripheral", "systemic")):
                    return profile
    logger.warning(f"No fatigue profile for {exercise_name}")
    return dict(_DEFAULT_FATIGUE_PROFILE)


def _neural_scaling(I: float) -> float:
    if I <= 0.60:
        return 0.0
    return ((I - 0.60) / 0.40) ** 2


def _per_set_fatigue(weight: float, reps: int, profile: dict, e1rm: float | None = None) -> dict:
    I = (weight / e1rm) if (e1rm and e1rm > 0) else 0.70
    return {
        "axial": profile["axial"] * weight * reps,
        "neural": profile["neural"] * reps * _neural_scaling(I),
        "peripheral": profile["peripheral"] * weight * reps,
        "systemic": profile["systemic"] * weight * reps,
    }


def _weekly_fatigue_by_dimension(
    sessions: list[dict],
    glossary: list[dict] | None,
    program_start: str,
    current_maxes: dict,
) -> dict[int, dict[str, float]]:
    """Keyed by integer week_number."""
    weekly: dict[int, dict[str, float]] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _session_week_num(s, program_start)
        if wk is None:
            continue
        week_dim = weekly.get(wk, {"axial": 0.0, "neural": 0.0, "peripheral": 0.0, "systemic": 0.0})
        for ex in s.get("exercises", []):
            name = ex.get("name", "").strip()
            kg = _num(ex.get("kg", 0))
            sets = int(_num(ex.get("sets", 0)))
            reps = int(_num(ex.get("reps", 0)))
            if kg <= 0 or sets <= 0 or reps <= 0:
                continue
            profile = _get_fatigue_profile(name, glossary)
            name_lower = name.lower()
            e1rm = None
            if name_lower == "squat":
                e1rm = current_maxes.get("squat")
            elif name_lower in ("bench press", "bench"):
                e1rm = current_maxes.get("bench")
            elif name_lower == "deadlift":
                e1rm = current_maxes.get("deadlift")
            sf = _per_set_fatigue(kg, reps, profile, e1rm)
            for dim in ("axial", "neural", "peripheral", "systemic"):
                week_dim[dim] += sf[dim] * sets
        weekly[wk] = week_dim
    return weekly


def _compute_dimensional_acwr(
    weekly_fatigue: dict[int, dict[str, float]],
    deload_weeks: list[int] | None = None,
    acute_weeks: int = 1,
    chronic_weeks: int = 4,
) -> dict:
    """Per-dimension ACWR. Deloads included for accurate chronic baseline.
    Returns insufficient_data if fewer than (acute + chronic) completed weeks exist.
    """
    sorted_weeks = sorted(weekly_fatigue.keys())
    min_weeks_needed = acute_weeks + chronic_weeks
    if len(sorted_weeks) < min_weeks_needed:
        return {
            "status": "insufficient_data",
            "reason": f"Need at least {min_weeks_needed} completed weeks for ACWR "
                      f"({acute_weeks} acute + {chronic_weeks} chronic)",
        }
    dimensions = {}
    for dim in ("axial", "neural", "peripheral", "systemic"):
        vals = [weekly_fatigue[w].get(dim, 0.0) for w in sorted_weeks]
        acute = vals[-acute_weeks:]
        chronic_window = vals[-(acute_weeks + chronic_weeks):-acute_weeks]
        if not chronic_window:
            dimensions[dim] = None
            continue
        acute_mean = sum(acute) / len(acute)
        chronic_mean = sum(chronic_window) / len(chronic_window)
        dimensions[dim] = round(acute_mean / chronic_mean, 3) if chronic_mean > 0 else None
    weights = {"axial": 0.30, "neural": 0.30, "peripheral": 0.25, "systemic": 0.15}
    valid = {k: v for k, v in dimensions.items() if v is not None}
    composite = round(sum(valid.get(k, 0) * weights[k] for k in weights if k in valid), 3) if valid else None
    return {"dimensions": dimensions, "composite": composite}


def _compute_dimensional_spike(
    weekly_fatigue: dict[int, dict[str, float]],
    deload_weeks: list[int] | None = None,
) -> dict:
    sorted_weeks = sorted(weekly_fatigue.keys())
    if len(sorted_weeks) < 2:
        return {"dimensions": {}, "composite": None}
    dimensions = {}
    for dim in ("axial", "neural", "peripheral", "systemic"):
        vals = [weekly_fatigue[w].get(dim, 0.0) for w in sorted_weeks]
        current = vals[-1]
        prev = vals[:-1][-3:]
        prev_mean = sum(prev) / len(prev) if prev else 0
        spike = _clamp((current - prev_mean) / prev_mean, 0.0, 1.0) if prev_mean > 0 else 0.0
        dimensions[dim] = round(spike, 3)
    weights = {"axial": 0.30, "neural": 0.30, "peripheral": 0.25, "systemic": 0.15}
    valid = {k: v for k, v in dimensions.items() if v is not None}
    composite = round(sum(valid.get(k, 0) * weights[k] for k in weights if k in valid), 3) if valid else None
    return {"dimensions": dimensions, "composite": composite}


# ---------------------------------------------------------------------------
# Public algorithms
# ---------------------------------------------------------------------------

def estimate_1rm(weight_kg: float, reps: int, rpe: Optional[int] = None) -> dict:
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
    return {"e1rm": e1rm, "method": method, "input_weight_kg": round(w, 1),
            "epley": None, "brzycki": None, "rpe_based": rpe_based}


def calculate_dots(total_kg: float, bodyweight_kg: float, sex: str) -> float:
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
    """Theil-Sen regression on e1RM per effective training week. Excludes deload/break weeks."""
    if not program_start:
        program_start = _infer_program_start(sessions)

    name_lower = exercise_name.lower()
    cutoff = date.today() - timedelta(days=90)

    ex_sessions = [
        s for s in _get_exercise_sessions(sessions, exercise_name)
        if (d := _parse_date(s.get("date", ""))) is not None and d >= cutoff
    ]

    deload_info = _detect_deloads(sessions, program_start)
    excluded_weeks: set[int] = {d["week_num"] for d in deload_info if d["is_deload"] or d["is_break"]}
    deload_count = len(excluded_weeks)
    effective_map: dict[int, int] = {
        d["week_num"]: d["effective_index"] for d in deload_info if d["effective_index"] >= 0
    }

    week_e1rm: dict[int, list[float]] = {}
    for s in ex_sessions:
        wk = _session_week_num(s, program_start)
        if wk is None or wk in excluded_weeks:
            continue
        eff_idx = effective_map.get(wk)
        if eff_idx is None:
            continue
        session_rpe = s.get("session_rpe")
        for ex in s.get("exercises", []):
            if ex.get("name", "").lower() != name_lower:
                continue
            if _count_failed_sets(ex) > 0:
                continue
            kg = _num(ex.get("kg", 0))
            reps = int(_num(ex.get("reps", 0)))
            if kg <= 0 or reps <= 0:
                continue
            e1rm = None
            rpe = session_rpe
            if rpe is not None and 1 <= reps <= 6 and 6 <= int(rpe) <= 10:
                pct = _RPE_TABLE_PRIMARY.get((reps, int(rpe)))
                if pct is not None:
                    e1rm = kg / pct
            elif rpe is None and 1 <= reps <= 5:
                pct = _CONSERVATIVE_REP_PCT.get(reps)
                if pct is not None:
                    e1rm = kg / pct
            if e1rm is not None:
                week_e1rm.setdefault(eff_idx, []).append(e1rm)

    if not week_e1rm:
        return {**INSUFFICIENT_DATA, "reason": f"No qualifying e1RM estimates for {exercise_name}"}
    xs = sorted(week_e1rm.keys())
    ys = [max(week_e1rm[w]) for w in xs]
    if len(xs) < 2:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 2 effective training weeks with {exercise_name} data"}

    result = theilslopes(ys, xs)
    slope, intercept = result[0], result[1]
    predicted = [intercept + slope * x for x in xs]
    mean_y = sum(ys) / len(ys)
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, predicted))
    r_squared = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 0.0

    return {
        "slope_kg_per_week": round(slope, 2),
        "r2": round(r_squared, 3),
        "points": [(round(float(x), 1), round(y, 1)) for x, y in zip(xs, ys)],
        "method": "theilsen",
        "deload_weeks_excluded": deload_count,
    }


def volume_intensity_correlation(sessions: list[dict], exercise_name: str, program_start: str = "") -> dict:
    if not program_start:
        program_start = _infer_program_start(sessions)
    name_lower = exercise_name.lower()
    weekly_volume: dict[int, float] = {}
    weekly_intensity: dict[int, float] = {}
    weekly_count: dict[int, int] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _session_week_num(s, program_start)
        if wk is None:
            continue
        for ex in s.get("exercises", []):
            if ex.get("name", "").lower() != name_lower:
                continue
            kg = _num(ex.get("kg") or 0)
            sets = _num(ex.get("sets", 0))
            reps = _num(ex.get("reps", 0))
            weekly_volume[wk] = weekly_volume.get(wk, 0) + sets * reps * kg
            weekly_intensity[wk] = weekly_intensity.get(wk, 0) + kg
            weekly_count[wk] = weekly_count.get(wk, 0) + 1
    weeks = sorted(weekly_volume.keys())
    if len(weeks) < 3:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 3 weeks of {exercise_name} data"}
    vol_series = [weekly_volume[w] for w in weeks]
    int_series = [weekly_intensity[w] / weekly_count[w] for w in weeks]
    return {
        "pearson_r": round(_pearson(vol_series, int_series), 3),
        "volume_series": [(w, round(v, 0)) for w, v in zip(weeks, vol_series)],
        "intensity_series": [(w, round(i, 1)) for w, i in zip(weeks, int_series)],
    }


def rpe_drift(
    sessions: list[dict],
    exercise_name: str,
    program_start: str = "",
    window_weeks: int = 4,
    phases: list[dict] | None = None,
) -> dict:
    if not program_start:
        program_start = _infer_program_start(sessions)
    ex_sessions = _get_exercise_sessions(sessions, exercise_name)
    if len(ex_sessions) < 3:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 3 completed sessions with {exercise_name}"}

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
        wk = _session_week_num(s, program_start)
        if wk is None:
            continue
        rpe = None
        rpe_val = s.get("session_rpe")
        if rpe_val is not None:
            rpe = _num(rpe_val)
        else:
            for ex in s.get("exercises", []):
                if ex.get("name", "").lower() == exercise_name.lower():
                    ex_rpe = ex.get("rpe")
                    rpe = _num(ex_rpe) if ex_rpe is not None else None
                    break
        if rpe is None:
            continue
        points.append((wk, float(rpe)))

    if len(points) < 3:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 3 RPE data points for {exercise_name}"}

    use_residual = False
    phase_targets: dict[int, float] = {}
    if phases:
        for phase in phases:
            t_min = phase.get("target_rpe_min")
            t_max = phase.get("target_rpe_max")
            if t_min is not None and t_max is not None:
                try:
                    midpoint = (_num(t_min) + _num(t_max)) / 2.0
                    for w in range(int(phase.get("start_week", 0)), int(phase.get("end_week", 0)) + 1):
                        phase_targets[w] = midpoint
                except (ValueError, TypeError):
                    pass
        if phase_targets:
            use_residual = True

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    if use_residual:
        residuals = [(wk, rpe - phase_targets[wk]) for wk, rpe in points if wk in phase_targets]
        if len(residuals) >= 3:
            xs = [r[0] for r in residuals]
            ys = [r[1] for r in residuals]
        else:
            use_residual = False

    if len(xs) >= 2:
        slope, intercept, _, _ = theilslopes(ys, xs)
        predicted = [intercept + slope * x for x in xs]
        mean_y = sum(ys) / len(ys)
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        ss_res = sum((y - p) ** 2 for y, p in zip(ys, predicted))
        r2 = 1.0 - (ss_res / ss_tot) if abs(ss_tot) > 1e-12 else 0.0
    else:
        slope, r2 = 0.0, 0.0

    direction = "up" if slope >= 0.1 else ("down" if slope <= -0.1 else "stable")
    flag = "fatigue" if slope >= 0.1 else ("adaptation" if slope <= -0.1 else None)

    return {
        "slope": round(slope, 3),
        "drift_direction": direction,
        "flag": flag,
        "r2": round(r2, 3),
        "mode": "residual" if use_residual else "raw",
    }


def fatigue_index(
    sessions: list[dict],
    days: int = 14,
    glossary: list[dict] | None = None,
    current_maxes: dict | None = None,
    program_start: str = "",
) -> dict:
    """Composite fatigue: 0.40*failed_ratio + 0.35*composite_spike + 0.25*rpe_stress.

    skip_rate intentionally excluded — resting reduces fatigue, not increases it.
    rpe_stress = clamp((avg_session_rpe - 6.0) / 4.0, 0, 1)
    """
    ref = date.today()
    cutoff = ref - timedelta(days=days)
    recent = [s for s in sessions if (d := _parse_date(s.get("date", ""))) is not None and d >= cutoff]

    if len(recent) < 2:
        return {**INSUFFICIENT_DATA, "reason": f"Need at least 2 sessions in the last {days} days"}

    # Component 1: failed compound sets ratio (40%)
    total_compound_sets = 0
    failed_compound_sets = 0
    for s in recent:
        for ex in s.get("exercises", []):
            name_lower = ex.get("name", "").lower()
            if any(kw in name_lower for kw in ["squat", "deadlift", "bench", "press", "row", "rdl", "pullup", "chinup"]):
                sets = _num(ex.get("sets", 0))
                total_compound_sets += sets
                failed_compound_sets += _count_failed_sets(ex)
    failed_ratio = _clamp(failed_compound_sets / total_compound_sets, 0, 1) if total_compound_sets > 0 else 0

    # Component 2: composite dimensional spike (35%)
    composite_spike = 0.0
    if glossary is not None and program_start:
        weekly_fatigue = _weekly_fatigue_by_dimension(recent, glossary, program_start, current_maxes or {})
        spike_result = _compute_dimensional_spike(weekly_fatigue)
        composite_spike = spike_result.get("composite") or 0.0
    else:
        this_week_start = ref - timedelta(days=7)
        this_week_load = 0.0
        prev_weeks_load = []
        for week_offset in range(1, 4):
            wk_start = ref - timedelta(days=7 * (week_offset + 1))
            wk_end = ref - timedelta(days=7 * week_offset)
            wk_load = sum(
                _num(ex.get("sets", 0)) * _num(ex.get("reps", 0)) * _num(ex.get("kg", 0))
                for s in sessions
                for ex in s.get("exercises", [])
                if (d := _parse_date(s.get("date", ""))) and wk_start <= d < wk_end
            )
            if wk_load > 0:
                prev_weeks_load.append(wk_load)
        this_week_load = sum(
            _num(ex.get("sets", 0)) * _num(ex.get("reps", 0)) * _num(ex.get("kg", 0))
            for s in sessions
            for ex in s.get("exercises", [])
            if (d := _parse_date(s.get("date", ""))) and d >= this_week_start
        )
        avg_prev = sum(prev_weeks_load) / len(prev_weeks_load) if prev_weeks_load else 0
        composite_spike = _clamp((this_week_load - avg_prev) / avg_prev, 0, 1) if avg_prev > 0 else 0

    # Component 3: RPE stress (25%) — captures RPE 9-10 grinding even without failures
    session_rpes = [
        _num(s.get("session_rpe"))
        for s in recent
        if s.get("completed") and s.get("session_rpe") is not None
    ]
    if session_rpes:
        avg_rpe = sum(session_rpes) / len(session_rpes)
        rpe_stress = _clamp((avg_rpe - 6.0) / 4.0, 0.0, 1.0)
    else:
        rpe_stress = 0.0

    score = round(0.40 * failed_ratio + 0.35 * composite_spike + 0.25 * rpe_stress, 3)

    flags = []
    if failed_ratio > 0.15:
        flags.append("failed_sets_spike")
    if composite_spike > 0.20:
        flags.append("volume_spike")
    if rpe_stress > 0.50:
        flags.append("high_rpe_stress")
    if score >= 0.6:
        flags.append("overreaching_risk")

    if glossary is not None and program_start:
        weekly_fatigue = _weekly_fatigue_by_dimension(recent, glossary, program_start, current_maxes or {})
        acwr_result = _compute_dimensional_acwr(weekly_fatigue)
        dims = acwr_result.get("dimensions", {})
        if dims.get("neural") is not None and dims["neural"] > 1.3:
            flags.append("neural_overload")
        if dims.get("axial") is not None and dims["axial"] > 1.3:
            flags.append("axial_overload")

    return {
        "score": score,
        "components": {
            "failed_compound_ratio": round(failed_ratio, 3),
            "composite_spike": round(composite_spike, 3),
            "rpe_stress": round(rpe_stress, 3),
        },
        "flags": flags,
    }


def session_compliance(program: dict, weeks: int = 4) -> dict:
    """All weeks counted — no deload/break exclusions."""
    sessions = program.get("sessions", [])
    meta = program.get("meta", {})
    program_start = meta.get("program_start", "")
    current_week = _calculate_current_week(program_start)
    cutoff_week = max(1, current_week - weeks + 1)

    sessions_in_window = [
        s for s in sessions
        if s.get("status") in ("planned", "logged", "completed", "skipped")
        and cutoff_week <= int(s.get("week_number", 0)) <= current_week
    ]
    planned_count = len(sessions_in_window)
    completed_count = sum(1 for s in sessions_in_window if s.get("status") in ("logged", "completed"))
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
    """90th percentile of qualifying e1RM estimates over last N days. Min 3 sets/lift."""
    cutoff = date.today() - timedelta(days=lookback_days)
    all_estimates: dict[str, list[float]] = {"squat": [], "bench": [], "deadlift": []}

    for s in sessions:
        d = _parse_date(s.get("date", ""))
        if d is None or d < cutoff:
            continue
        if s.get("status", "") in ("planned", "skipped"):
            continue
        session_rpe = s.get("session_rpe")
        for ex in s.get("exercises", []):
            if _count_failed_sets(ex) > 0:
                continue
            name = ex.get("name", "").lower().strip()
            kg = _num(ex.get("kg", 0))
            reps = int(_num(ex.get("reps", 0)))
            if kg <= 0 or reps <= 0:
                continue
            canonical = {"squat": "squat", "bench press": "bench", "bench": "bench", "deadlift": "deadlift"}.get(name)
            if canonical is None:
                continue
            rpe = session_rpe
            e1rm = None
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
    """Project competition total. Ceiling scales with time to allow meaningful separation
    between near-term and far-out competitions:
      ceiling_pct = 10% + 1% per 2 weeks beyond 8 (max 30%)
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

    # Prefer the most recent completed competition results when available.
    # Fall back to session-derived estimates when no competition data exists.
    comp_maxes = _estimate_maxes_from_comps(program.get("competitions", []))
    session_maxes = _estimate_maxes_from_sessions(sessions)
    maxes = comp_maxes or session_maxes
    if not maxes:
        return {**INSUFFICIENT_DATA, "reason": "No session data to estimate maxes from"}

    bodyweight = _num(meta.get("current_body_weight_kg", meta.get("bodyweight_kg", 0)))
    sex = meta.get("sex", "male").lower()
    total_now = sum(_num(maxes.get(k, 0)) for k in ("squat", "bench", "deadlift"))
    dots_now = calculate_dots(total_now, bodyweight, sex) if bodyweight > 0 and total_now > 0 else 0

    if dots_now >= 400:
        lam, peak_factor = 0.85, 1.05
    elif dots_now < 300:
        lam, peak_factor = 0.96, 1.01
    else:
        lam, peak_factor = 0.90, 1.03

    weeks_taper = 3 if weeks_to_comp >= 12 else (2 if weeks_to_comp >= 8 else 1)

    deload_info = _detect_deloads(sessions, program_start)
    current_week_num = _calculate_current_week(program_start)
    comp_week = current_week_num + weeks_to_comp
    remaining_deloads = [w for w in deload_info if w["is_deload"] and current_week_num <= w["week_num"] <= comp_week]
    planned_deload_weeks = len(remaining_deloads)
    if planned_deload_weeks == 0 and weeks_to_comp > 4:
        planned_deload_weeks = int(weeks_to_comp // 4)

    n_t = max(0, weeks_to_comp - weeks_taper - planned_deload_weeks)

    # Time-proportional ceiling: closer comps get tighter cap (10%),
    # further comps allow more room for legitimate gains (+1% per 2 extra weeks)
    ceiling_pct = 0.10 + max(0.0, (weeks_to_comp - 8.0) / 2.0) * 0.01
    ceiling_pct = min(0.30, ceiling_pct)

    lifts = {}
    has_real_progression = False
    for lift_name in ("squat", "bench", "deadlift"):
        current = maxes.get(lift_name)
        if current is None:
            continue
        try:
            current_kg = _num(current)
        except (ValueError, TypeError):
            continue

        prog = progression_rate(sessions, lift_name, program_start)
        delta_w = prog.get("slope_kg_per_week", 0)
        r2 = prog.get("r2", 0)
        if prog.get("status") != "insufficient_data":
            has_real_progression = True

        projected_gain = delta_w * lam * (1 - lam ** n_t) / (1 - lam) if n_t > 0 and delta_w > 0 else 0
        comp_max = (current_kg + projected_gain) * peak_factor

        ceiling = current_kg * (1.0 + ceiling_pct)
        clamped = bool(comp_max > ceiling)
        comp_max = max(current_kg, min(comp_max, ceiling))

        lifts[lift_name] = {
            "current": round(current_kg, 1),
            "projected": round(comp_max, 1),
            "slope_kg_per_week": delta_w,
            "confidence": round(_clamp(r2, 0, 1), 2),
            "ceiling_clamped": clamped,
        }

    if not lifts:
        return {**INSUFFICIENT_DATA, "reason": "No lift maxes found (squat, bench, deadlift)"}
    if not has_real_progression:
        return {**INSUFFICIENT_DATA, "reason": "Insufficient session data to estimate progression"}

    total = sum(v["projected"] for v in lifts.values())
    avg_confidence = sum(v["confidence"] for v in lifts.values()) / len(lifts)

    return {
        "squat": lifts.get("squat", {}).get("projected"),
        "bench": lifts.get("bench", {}).get("projected"),
        "deadlift": lifts.get("deadlift", {}).get("projected"),
        "total": round(total, 1),
        "confidence": round(avg_confidence, 2),
        "weeks_to_comp": round(weeks_to_comp, 1),
        "method": "session_estimated",
        "lifts": lifts,
    }


def compute_inol(
    sessions: list[dict],
    program_start: str = "",
    current_maxes: dict | None = None,
) -> dict:
    """INOL per lift per week. Returns avg_inol across the window. Flags on avg."""
    if not current_maxes:
        current_maxes = _estimate_maxes_from_sessions(sessions)
    if not current_maxes:
        return {**INSUFFICIENT_DATA, "reason": "No current maxes available for INOL calculation"}
    if not program_start:
        program_start = _infer_program_start(sessions)

    lift_names = {"squat": "squat", "bench press": "bench", "bench": "bench", "deadlift": "deadlift"}
    per_lift_per_week: dict[str, dict[int, float]] = {}

    for s in sessions:
        if not s.get("completed"):
            continue
        wk = _session_week_num(s, program_start)
        if wk is None:
            continue
        for ex in s.get("exercises", []):
            canonical = lift_names.get(ex.get("name", "").lower().strip())
            if canonical is None:
                continue
            max_val = current_maxes.get(canonical)
            if not max_val or max_val <= 0:
                continue
            kg = _num(ex.get("kg", 0))
            reps = int(_num(ex.get("reps", 0)))
            sets = int(_num(ex.get("sets", 0)))
            if kg <= 0 or reps <= 0:
                continue
            I = kg / max_val
            denom = max(0.01, 1 - I) if I >= 1.0 else (1 - I)
            inol_contrib = (reps / (100 * denom)) * sets
            per_lift_per_week.setdefault(canonical, {})
            per_lift_per_week[canonical][wk] = per_lift_per_week[canonical].get(wk, 0) + inol_contrib

    if not per_lift_per_week:
        return {**INSUFFICIENT_DATA, "reason": "No qualifying sets for INOL"}

    avg_inol = {
        lift: round(sum(weeks_data.values()) / len(weeks_data), 2)
        for lift, weeks_data in per_lift_per_week.items()
        if weeks_data
    }
    flags = [
        f"low_stimulus_{lift}" if v < 2.0 else f"overreaching_risk_{lift}"
        for lift, v in avg_inol.items()
        if v < 2.0 or v > 4.0
    ]
    rounded = {lift: {str(w): round(v, 2) for w, v in sorted(weeks_data.items())}
               for lift, weeks_data in per_lift_per_week.items()}

    return {"per_lift_per_week": rounded, "avg_inol": avg_inol, "flags": flags}


def compute_acwr(
    sessions: list[dict],
    glossary: list[dict] | None = None,
    program_start: str = "",
    current_maxes: dict | None = None,
) -> dict:
    """ACWR per dimension + composite. Deloads included. Returns insufficient_data if < 5 weeks."""
    if not program_start:
        program_start = _infer_program_start(sessions)
    if not current_maxes:
        current_maxes = _estimate_maxes_from_sessions(sessions)

    weekly_fatigue = _weekly_fatigue_by_dimension(sessions, glossary, program_start, current_maxes or {})
    acwr_result = _compute_dimensional_acwr(weekly_fatigue)

    if acwr_result.get("status") == "insufficient_data":
        return acwr_result

    def _zone(value: float | None) -> str:
        if value is None:
            return "unknown"
        if value < 0.8:
            return "undertraining"
        if value <= 1.3:
            return "optimal"
        if value <= 1.5:
            return "caution"
        return "danger"

    dimensions = {
        dim: {"value": acwr_result.get("dimensions", {}).get(dim), "zone": _zone(acwr_result.get("dimensions", {}).get(dim))}
        for dim in ("axial", "neural", "peripheral", "systemic")
    }
    composite = acwr_result.get("composite")
    return {"composite": composite, "composite_zone": _zone(composite), "dimensions": dimensions}


def compute_attempt_selection(projected_maxes: dict, attempt_pct: dict | None = None) -> dict | None:
    if not projected_maxes:
        return None
    defaults = {"opener": 0.90, "second": 0.955, "third": 1.00}
    raw_pcts = attempt_pct or defaults
    pcts = {
        lift: _num(raw_pcts.get(lift, default))
        for lift, default in defaults.items()
    }

    def _round_to_2_5(val: float) -> float:
        return round(val / 2.5) * 2.5

    result: dict[str, Any] = {}
    third_total = 0.0
    for lift in ("squat", "bench", "deadlift"):
        c_max = projected_maxes.get(lift)
        if c_max is None:
            continue
        c_max = _num(c_max)
        result[lift] = {
            "opener": _round_to_2_5(c_max * pcts["opener"]),
            "second": _round_to_2_5(c_max * pcts["second"]),
            "third": _round_to_2_5(c_max * pcts["third"]),
        }
        third_total += result[lift]["third"]
    if not result:
        return None
    result["total"] = round(third_total, 1)
    result["attempt_pct_used"] = pcts
    return result


def compute_ri_distribution(sessions: list[dict], current_maxes: dict | None = None) -> dict:
    if not current_maxes:
        return {**INSUFFICIENT_DATA, "reason": "No current maxes for RI distribution"}
    lift_names = {"squat": "squat", "bench press": "bench", "bench": "bench", "deadlift": "deadlift"}

    def _bucket(ri: float) -> str:
        return "heavy" if ri > 0.85 else ("moderate" if ri >= 0.70 else "light")

    overall: dict[str, int] = {"heavy": 0, "moderate": 0, "light": 0}
    per_lift: dict[str, dict[str, int]] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        for ex in s.get("exercises", []):
            canonical = lift_names.get(ex.get("name", "").lower().strip())
            if canonical is None:
                continue
            max_val = current_maxes.get(canonical)
            if not max_val or max_val <= 0:
                continue
            kg = _num(ex.get("kg", 0))
            sets = int(_num(ex.get("sets", 0)))
            if kg <= 0 or sets <= 0:
                continue
            b = _bucket(kg / max_val)
            overall[b] += sets
            per_lift.setdefault(canonical, {"heavy": 0, "moderate": 0, "light": 0})
            per_lift[canonical][b] += sets

    total = sum(overall.values())
    if total == 0:
        return {**INSUFFICIENT_DATA, "reason": "No qualifying sets for RI distribution"}

    buckets = ["heavy", "moderate", "light"]
    overall_out = {b: {"count": overall[b], "pct": round(overall[b] / total * 100, 1)} for b in buckets}
    per_lift_out = {
        lift: {b: {"count": counts[b], "pct": round(counts[b] / max(sum(counts.values()), 1) * 100, 1)} for b in buckets}
        for lift, counts in per_lift.items()
    }
    return {"overall": overall_out, "per_lift": per_lift_out}


def compute_specificity_ratio(sessions: list[dict], glossary: list[dict] | None = None) -> dict:
    sbd_names = {"squat", "bench press", "bench", "deadlift"}
    total_sets = sbd_sets = secondary_sets = 0
    category_lookup: dict[str, str] = {}
    if glossary:
        for ex in glossary:
            category_lookup[ex.get("name", "").lower().strip()] = ex.get("category", "")
    for s in sessions:
        if not s.get("completed"):
            continue
        for ex in s.get("exercises", []):
            sets = int(_num(ex.get("sets", 0)))
            if sets <= 0:
                continue
            name_lower = ex.get("name", "").lower().strip()
            total_sets += sets
            if name_lower in sbd_names:
                sbd_sets += sets
            elif glossary and category_lookup.get(name_lower, "") in ("squat", "bench", "deadlift"):
                secondary_sets += sets
    if total_sets == 0:
        return {**INSUFFICIENT_DATA, "reason": "No working sets for specificity ratio"}
    return {
        "narrow": round(sbd_sets / total_sets, 3),
        "broad": round((sbd_sets + secondary_sets) / total_sets, 3),
        "total_sets": total_sets,
        "sbd_sets": sbd_sets,
        "secondary_sets": secondary_sets,
    }


def compute_readiness_score(
    sessions: list[dict],
    program: dict,
    glossary: list[dict] | None = None,
    program_start: str = "",
) -> dict:
    """R = (1 - (0.30*F_norm + 0.25*D_rpe + 0.20*S_bw + 0.15*M_rate + 0.10*(1-C/100))) * 100"""
    if not program_start:
        program_start = program.get("meta", {}).get("program_start", "")
    phases = program.get("phases", [])

    fatigue = fatigue_index(sessions, days=14, glossary=glossary,
                            current_maxes=_estimate_maxes_from_sessions(sessions),
                            program_start=program_start)
    f_norm = fatigue.get("score", 0) if "score" in fatigue else 0.5

    ref = date.today()
    cutoff = ref - timedelta(days=14)
    recent_sessions = [s for s in sessions if (d := _parse_date(s.get("date", ""))) and d >= cutoff]
    rpe_vals = [_num(s.get("session_rpe")) for s in recent_sessions if s.get("completed") and s.get("session_rpe") is not None]
    avg_rpe = sum(rpe_vals) / len(rpe_vals) if rpe_vals else 7.5

    current_week = _calculate_current_week(program_start)
    current_phase = _find_current_phase(phases, current_week)
    target_rpe_mid = 7.5
    if current_phase:
        t_min = current_phase.get("target_rpe_min")
        t_max = current_phase.get("target_rpe_max")
        if t_min is not None and t_max is not None:
            target_rpe_mid = (_num(t_min) + _num(t_max)) / 2.0
    d_rpe = _clamp((avg_rpe - target_rpe_mid) / 2, 0, 1)

    bw_entries = sorted(
        [(d, _num(s.get("body_weight_kg")))
         for s in sessions
         if s.get("body_weight_kg") is not None and (d := _parse_date(s.get("date", "")))]
    )
    recent_bw = [b for _, b in bw_entries[-7:]]
    if len(recent_bw) >= 2:
        mean_bw = sum(recent_bw) / len(recent_bw)
        cv = math.sqrt(sum((b - mean_bw) ** 2 for b in recent_bw) / len(recent_bw)) / mean_bw if mean_bw > 0 else 0
        s_bw = _clamp(cv / 0.03, 0, 1)
    else:
        s_bw = 0.5

    total_sets = sum(int(_num(ex.get("sets", 0))) for s in recent_sessions for ex in s.get("exercises", []) if int(_num(ex.get("sets", 0))) > 0)
    failed_sets = sum(_count_failed_sets(ex) for s in recent_sessions for ex in s.get("exercises", []))
    m_rate = _clamp(failed_sets / total_sets, 0, 1) if total_sets > 0 else 0

    c_pct = session_compliance(program, weeks=2).get("compliance_pct", 50)
    score = round(_clamp((1 - (0.30 * f_norm + 0.25 * d_rpe + 0.20 * s_bw + 0.15 * m_rate + 0.10 * (1 - c_pct / 100))) * 100, 0, 100), 1)
    zone = "green" if score > 75 else ("yellow" if score >= 50 else "red")

    return {
        "score": score,
        "zone": zone,
        "components": {
            "fatigue_norm": round(f_norm, 3),
            "rpe_drift": round(d_rpe, 3),
            "bw_stability": round(s_bw, 3),
            "miss_rate": round(m_rate, 3),
            "compliance_pct": c_pct,
        },
    }


def weekly_analysis(
    program: dict,
    sessions: list[dict],
    ref_date: Optional[str] = None,
    weeks: int = 1,
    block: Optional[str] = None,
    glossary: list[dict] | None = None,
) -> dict:
    """Full weekly analysis — single entry point for tools and API."""
    meta = program.get("meta", {})
    phases = program.get("phases", [])
    program_start = meta.get("program_start", "")

    current_week = _calculate_current_week(program_start)
    current_phase = _find_current_phase(phases, current_week)
    phase_name = current_phase.get("name", "Unknown") if current_phase else "Unknown"

    # Block filter
    if block:
        sessions = [s for s in sessions if s.get("block", "current") == block]

    # Date-window filter → recent_sessions
    ref = _parse_date(ref_date) if ref_date else date.today()
    cutoff = ref - timedelta(weeks=weeks)
    recent_sessions = sorted(
        [s for s in sessions if (d := _parse_date(s.get("date", ""))) and d >= cutoff],
        key=lambda s: s.get("date", ""),
        reverse=True,
    )

    # Completed sessions in window — used by all windowed metrics
    # (INOL, ACWR, RI distribution, specificity, fatigue dimensions, readiness)
    completed_in_window = [s for s in recent_sessions if s.get("status") in ("logged", "completed")]

    # Exercise stats: completed sessions only, to avoid inflated counts from planned sessions
    exercise_stats: dict[str, dict[str, Any]] = {}
    for s in completed_in_window:
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

    sessions_analyzed = len(completed_in_window)

    # Identify main lifts (from completed sessions only)
    exercise_names = {ex.get("name", "").lower().strip() for s in completed_in_window for ex in s.get("exercises", []) if ex.get("name")}
    tracked_lifts = []
    lift_alias_map = {}
    for canonical, output_key in [("squat", "squat"), ("bench press", "bench"), ("deadlift", "deadlift"), ("bench", "bench")]:
        if canonical in exercise_names and output_key not in lift_alias_map:
            lift_alias_map[output_key] = canonical
            if output_key not in tracked_lifts:
                tracked_lifts.append(output_key)

    # Per-lift analysis (progression/volume use full block history for slope accuracy)
    lifts_report = {}
    all_flags = []
    for lift_key in tracked_lifts:
        ex_name = lift_alias_map.get(lift_key, lift_key)
        lift_data: dict[str, Any] = {}

        prog = progression_rate(sessions, ex_name, program_start)
        if "slope_kg_per_week" in prog:
            lift_data["progression_rate_kg_per_week"] = prog["slope_kg_per_week"]
            lift_data["r2"] = prog.get("r2", 0)
        else:
            lift_data["progression_rate_kg_per_week"] = None
            lift_data["r2"] = None

        vol_corr = volume_intensity_correlation(sessions, ex_name, program_start)
        if "volume_series" in vol_corr and len(vol_corr["volume_series"]) >= 2:
            vols = [v[1] for v in vol_corr["volume_series"]]
            intens = [i[1] for i in vol_corr["intensity_series"]]
            prev_vol = vols[-2]
            prev_int = intens[-2]
            lift_data["volume_change_pct"] = round(((vols[-1] - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0, 1)
            lift_data["intensity_change_pct"] = round(((intens[-1] - prev_int) / prev_int * 100) if prev_int > 0 else 0, 1)

        drift = rpe_drift(sessions, ex_name, program_start, phases=phases)
        if "drift_direction" in drift:
            lift_data["rpe_trend"] = drift["drift_direction"]
            if drift.get("flag"):
                all_flags.append(f"{ex_name}_rpe_{drift['flag']}")
        else:
            lift_data["rpe_trend"] = "unknown"

        lift_data["failed_sets"] = int(sum(
            _count_failed_sets(ex)
            for s in completed_in_window
            for ex in s.get("exercises", [])
            if ex.get("name", "").lower().strip() == ex_name
        ))
        lifts_report[ex_name] = lift_data

    # Maxes are estimated from the latest completed competition when possible,
    # otherwise from the 90th percentile of qualifying session e1RMs.
    comp_maxes_raw = _estimate_maxes_from_comps(program.get("competitions", []))
    session_maxes_raw = _estimate_maxes_from_sessions(sessions)
    current_maxes_raw = comp_maxes_raw or session_maxes_raw

    # Fatigue index uses windowed sessions (days = weeks * 7)
    fatigue = fatigue_index(sessions, days=weeks * 7, glossary=glossary,
                            current_maxes=current_maxes_raw, program_start=program_start)
    fatigue_score = fatigue.get("score") if "score" in fatigue else None
    fatigue_components = fatigue.get("components", {}) if "components" in fatigue else {}
    if fatigue.get("flags"):
        all_flags.extend(fatigue["flags"])

    compliance_result = session_compliance(program, weeks=min(weeks, 4))
    compliance_obj = {
        "phase": compliance_result.get("phase", "Unknown"),
        "planned": compliance_result.get("planned_sessions", 0),
        "completed": compliance_result.get("completed_sessions", 0),
        "pct": compliance_result.get("compliance_pct", 0),
    }

    # Deload detection (from full block history for accurate detection)
    deload_info_raw = _detect_deloads(sessions, program_start)
    deload_info = {
        "deload_weeks": [d["week_num"] for d in deload_info_raw if d["is_deload"]],
        "break_weeks": [d["week_num"] for d in deload_info_raw if d["is_break"]],
        "effective_training_weeks": sum(1 for d in deload_info_raw if d["effective_index"] >= 0),
    }

    # Current maxes output
    maxes_method = "comp_results" if comp_maxes_raw else ("session_estimated" if session_maxes_raw else "none")
    current_maxes_out: dict[str, Any] = {}
    if current_maxes_raw:
        for lk in ("squat", "bench", "deadlift"):
            val = current_maxes_raw.get(lk)
            if val is not None:
                current_maxes_out[lk] = round(_num(val), 1)
    current_maxes_out["method"] = maxes_method

    # DOTS
    estimated_dots = None
    bodyweight = _num(meta.get("bodyweight_kg", 0))
    sex = meta.get("sex", "").lower()
    if bodyweight > 0 and sex in ("male", "female") and len(current_maxes_out) >= 3:
        total_kg = sum(current_maxes_out.get(lk, 0) for lk in ("squat", "bench", "deadlift"))
        if total_kg > 0:
            estimated_dots = calculate_dots(total_kg, bodyweight, sex)

    # Meet projections
    projections: list[dict[str, Any]] = []
    projection_reason = None
    today = date.today()
    upcoming = [
        c for c in sorted(program.get("competitions", []), key=lambda x: x.get("date", ""))
        if c.get("status") in ("confirmed", "optional") and (d := _parse_date(c.get("date", ""))) and d > today
    ]
    to_project = [upcoming[0], upcoming[-1]] if len(upcoming) >= 2 else upcoming[:1]

    for comp in to_project:
        proj = meet_projection(program, sessions, comp_date=comp["date"])
        if "total" in proj:
            projections.append({
                "total": proj["total"],
                "confidence": proj["confidence"],
                "weeks_to_comp": proj.get("weeks_to_comp"),
                "method": proj.get("method"),
                "comp_name": comp.get("name"),
                "lifts": proj.get("lifts", {}),
            })

    if not projections and not to_project and meta.get("comp_date"):
        proj = meet_projection(program, sessions, comp_date=meta["comp_date"])
        if "total" in proj:
            projections.append({"total": proj["total"], "confidence": proj["confidence"],
                                 "weeks_to_comp": proj.get("weeks_to_comp"), "method": proj.get("method"),
                                 "comp_name": None, "lifts": proj.get("lifts", {})})
        else:
            projection_reason = proj.get("reason", "Insufficient data for projection")

    # Attempt selection
    attempt_selection = None
    if projections:
        attempt_pct = meta.get("attempt_pct")
        first_proj_lifts = projections[0].get("lifts", {})
        projected_maxes = {
            lift: data.get("projected") for lift, data in first_proj_lifts.items()
            if isinstance(data, dict) and data.get("projected") is not None
        }
        if projected_maxes:
            attempt_selection = compute_attempt_selection(projected_maxes, attempt_pct)

    # -----------------------------------------------------------------------
    # All windowed metrics — use completed_in_window so they respond to
    # the weeks selector. current_maxes_raw uses wider lookback (42d) for
    # accuracy and is shared.
    # -----------------------------------------------------------------------

    # Fatigue dimensions
    fatigue_dimensions = None
    if glossary is not None:
        weekly_dim = _weekly_fatigue_by_dimension(completed_in_window, glossary, program_start, current_maxes_raw or {})
        acwr = _compute_dimensional_acwr(weekly_dim)
        spike = _compute_dimensional_spike(weekly_dim)
        weekly_rounded = {wk: {k: round(v, 1) for k, v in dims.items()} for wk, dims in sorted(weekly_dim.items())}
        fatigue_dimensions = {
            "weekly": weekly_rounded,
            "acwr": acwr,
            "spike": spike,
            "dimension_weights": {"axial": 0.30, "neural": 0.30, "peripheral": 0.25, "systemic": 0.15},
        }

    inol_result = compute_inol(completed_in_window, program_start, current_maxes_raw)
    acwr_result = compute_acwr(completed_in_window, glossary, program_start, current_maxes_raw)
    ri_result = compute_ri_distribution(completed_in_window, current_maxes_raw)
    specificity_result = compute_specificity_ratio(completed_in_window, glossary)
    readiness_result = compute_readiness_score(completed_in_window, program, glossary, program_start)

    if "flags" in inol_result and inol_result["flags"]:
        all_flags.extend(inol_result["flags"])

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
        "sessions_analyzed": sessions_analyzed,
        "exercise_stats": exercise_stats,
        "deload_info": deload_info,
        "fatigue_dimensions": fatigue_dimensions,
        "inol": inol_result if "status" not in inol_result else None,
        "acwr": acwr_result if "status" not in acwr_result else None,
        "ri_distribution": ri_result if "status" not in ri_result else None,
        "specificity_ratio": specificity_result if "status" not in specificity_result else None,
        "readiness_score": readiness_result,
        "attempt_selection": attempt_selection,
    }


# ---------------------------------------------------------------------------
# Renderer helpers
# ---------------------------------------------------------------------------

def _calculate_current_week(program_start: str) -> int:
    if not program_start:
        return 1
    try:
        start = datetime.strptime(program_start, "%Y-%m-%d").date()
        days_since = (date.today() - start).days
        return max(1, (days_since // 7) + 1)
    except ValueError:
        return 1


def _find_current_phase(phases: list[dict], current_week: int) -> Optional[dict]:
    for phase in phases:
        if phase.get("start_week", 0) <= current_week <= phase.get("end_week", 0):
            return phase
    return None


def _infer_program_start(sessions: list[dict]) -> str:
    dates = [d for s in sessions if (d := _parse_date(s.get("date", "")))]
    return min(dates).isoformat() if dates else ""
