"""Shared context builders for health AI prompts.

These helpers turn the current program state into compact, structured
prompt sections for correlation / block evaluation models.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from analytics import calculate_dots


def _num(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_date(value: str | None) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_dots(total_kg: float, bodyweight_kg: float, sex: str) -> float | None:
    if total_kg <= 0 or bodyweight_kg <= 0:
        return None
    try:
        return calculate_dots(total_kg, bodyweight_kg, sex)
    except Exception:
        return None


def _serialize_wellness(wellness: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(wellness, dict):
        return None
    values = {key: wellness.get(key) for key in ("sleep", "soreness", "mood", "stress", "energy", "recorded_at")}
    if all(values.get(key) is None for key in ("sleep", "soreness", "mood", "stress", "energy")):
        return None
    return values


def summarize_program_meta(meta: dict[str, Any]) -> dict[str, Any]:
    last_comp = meta.get("last_comp") or {}
    last_results = last_comp.get("results") or {}
    return {
        "program_name": meta.get("program_name"),
        "program_start": meta.get("program_start"),
        "comp_date": meta.get("comp_date"),
        "federation": meta.get("federation"),
        "practicing_for": meta.get("practicing_for"),
        "version_label": meta.get("version_label"),
        "weight_class_kg": meta.get("weight_class_kg"),
        "current_body_weight_kg": meta.get("current_body_weight_kg"),
        "current_body_weight_lb": meta.get("current_body_weight_lb"),
        "target_total_kg": meta.get("target_total_kg"),
        "target_squat_kg": meta.get("target_squat_kg"),
        "target_bench_kg": meta.get("target_bench_kg"),
        "target_dl_kg": meta.get("target_dl_kg"),
        "height_cm": meta.get("height_cm"),
        "arm_wingspan_cm": meta.get("arm_wingspan_cm"),
        "leg_length_cm": meta.get("leg_length_cm"),
        "attempt_pct": meta.get("attempt_pct"),
        "last_comp": {
            "date": last_comp.get("date"),
            "body_weight_kg": last_comp.get("body_weight_kg"),
            "weight_class_kg": last_comp.get("weight_class_kg"),
            "results": last_results or None,
        } if last_comp else None,
    }


def summarize_lift_profiles(lift_profiles: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not lift_profiles:
        return []
    ordered: list[dict[str, Any]] = []
    for lift in ("squat", "bench", "deadlift"):
        profile = next((p for p in lift_profiles if p.get("lift") == lift), None)
        if not profile:
            continue
        ordered.append({
            "lift": profile.get("lift"),
            "style_notes": profile.get("style_notes") or "",
            "sticking_points": profile.get("sticking_points") or "",
            "primary_muscle": profile.get("primary_muscle") or "",
            "volume_tolerance": profile.get("volume_tolerance") or "moderate",
            "stimulus_coefficient": profile.get("stimulus_coefficient", 1.0),
        })
    return ordered


def summarize_phases(phases: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not phases:
        return []
    ordered = sorted(phases, key=lambda p: int(p.get("start_week", 0) or 0))
    return [
        {
            "name": phase.get("name"),
            "intent": phase.get("intent", ""),
            "start_week": phase.get("start_week"),
            "end_week": phase.get("end_week"),
            "target_rpe_min": phase.get("target_rpe_min"),
            "target_rpe_max": phase.get("target_rpe_max"),
            "days_per_week": phase.get("days_per_week"),
            "notes": phase.get("notes", ""),
        }
        for phase in ordered
    ]


def summarize_measurements(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "height_cm": meta.get("height_cm"),
        "arm_wingspan_cm": meta.get("arm_wingspan_cm"),
        "leg_length_cm": meta.get("leg_length_cm"),
        "current_body_weight_kg": meta.get("current_body_weight_kg"),
        "weight_class_kg": meta.get("weight_class_kg"),
    }


def summarize_competitions(program: dict[str, Any], reference_date: date | None = None) -> dict[str, Any]:
    meta = program.get("meta", {})
    competitions = sorted(program.get("competitions", []), key=lambda c: c.get("date", ""))
    reference_date = reference_date or date.today()
    sex = str(meta.get("sex", "male")).lower()
    fallback_bw = _num(meta.get("current_body_weight_kg", meta.get("bodyweight_kg", 0)))

    rows: list[dict[str, Any]] = []
    primary = competitions[-1] if competitions else None
    for idx, comp in enumerate(competitions):
        comp_date = _parse_date(comp.get("date"))
        weeks_to_comp = round(((comp_date - reference_date).days / 7.0), 1) if comp_date else None
        bodyweight = _num(comp.get("body_weight_kg")) or fallback_bw
        results = comp.get("results") or {}
        targets = comp.get("targets") or {}
        row: dict[str, Any] = {
            "name": comp.get("name"),
            "date": comp.get("date"),
            "status": comp.get("status"),
            "role": "primary" if primary is comp else ("practice" if idx < len(competitions) - 1 else "primary"),
            "weeks_to_comp": weeks_to_comp,
            "weight_class_kg": comp.get("weight_class_kg"),
            "bodyweight_kg": bodyweight if bodyweight > 0 else None,
            "actual_total_kg": None,
            "actual_dots": None,
            "target_total_kg": None,
            "target_dots": None,
        }
        if results:
            total = _num(results.get("total_kg"))
            if total > 0:
                row["actual_total_kg"] = round(total, 1)
                row["actual_dots"] = _safe_dots(total, bodyweight, sex)
        if targets:
            total = _num(targets.get("total_kg"))
            if total > 0:
                row["target_total_kg"] = round(total, 1)
                row["target_dots"] = _safe_dots(total, bodyweight, sex)
        rows.append(row)

    return {
        "primary_competition": rows[-1] if rows else None,
        "competitions": rows,
    }


def summarize_bodyweight_trend(
    sessions: list[dict[str, Any]],
    reference_date: date | None = None,
    window_start: date | None = None,
) -> dict[str, Any]:
    reference_date = reference_date or date.today()
    points = []
    for session in sessions:
        if not (session.get("completed") or session.get("status") in ("logged", "completed")):
            continue
        bw = session.get("body_weight_kg")
        if bw is None:
            continue
        d = _parse_date(session.get("date"))
        if d is None:
            continue
        if window_start and d < window_start:
            continue
        points.append({"date": d.isoformat(), "kg": round(_num(bw), 1)})

    points.sort(key=lambda p: p["date"])
    if len(points) < 2:
        return {"points": points, "latest": None, "change": None, "direction": "unclear"}

    latest = points[-1]["kg"]
    oldest = points[0]["kg"]
    change = round(latest - oldest, 1)
    if change > 0.25:
        direction = "gain"
    elif change < -0.25:
        direction = "loss"
    else:
        direction = "stable"

    return {
        "points": points[-8:],
        "latest": latest,
        "oldest": oldest,
        "change": change,
        "direction": direction,
        "entries": len(points),
    }


def summarize_diet_context(
    program: dict[str, Any],
    reference_date: date | None = None,
    window_start: date | None = None,
    bodyweight_trend: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reference_date = reference_date or date.today()
    diet_notes = program.get("diet_notes", [])
    if window_start:
        diet_notes = [n for n in diet_notes if (d := _parse_date(n.get("date"))) and d >= window_start]

    if not diet_notes:
        return {"status": "unclear", "reason": "No diet notes available"}

    calories = [float(n["avg_daily_calories"]) for n in diet_notes if n.get("avg_daily_calories") is not None]
    protein = [float(n["avg_protein_g"]) for n in diet_notes if n.get("avg_protein_g") is not None]
    carbs = [float(n["avg_carb_g"]) for n in diet_notes if n.get("avg_carb_g") is not None]
    fat = [float(n["avg_fat_g"]) for n in diet_notes if n.get("avg_fat_g") is not None]
    sleep = [float(n["avg_sleep_hours"]) for n in diet_notes if n.get("avg_sleep_hours") is not None]
    consistent = sum(1 for n in diet_notes if n.get("consistent"))

    latest = diet_notes[-1]
    prev = diet_notes[-2] if len(diet_notes) > 1 else None
    latest_calories = latest.get("avg_daily_calories")
    prev_calories = prev.get("avg_daily_calories") if prev else None
    change = None
    if latest_calories is not None and prev_calories is not None:
        change = round(float(latest_calories) - float(prev_calories), 1)

    status = "unclear"
    reasoning = "Insufficient data for an exact calorie status."
    if latest_calories is not None:
        if change is not None and change <= -150:
            status = "deficit"
            reasoning = "Calorie intake trended down relative to the prior note window."
        elif change is not None and change >= 150:
            status = "surplus"
            reasoning = "Calorie intake trended up relative to the prior note window."
        elif bodyweight_trend and bodyweight_trend.get("direction") == "loss":
            status = "deficit"
            reasoning = "Body weight is drifting down, which is consistent with a deficit."
        elif bodyweight_trend and bodyweight_trend.get("direction") == "gain":
            status = "surplus"
            reasoning = "Body weight is drifting up, which is consistent with a surplus."
        else:
            status = "maintenance"
            reasoning = "No strong calorie or bodyweight signal suggests a large surplus/deficit."

    return {
        "status": status,
        "reasoning": reasoning,
        "latest_avg_calories": latest_calories,
        "previous_avg_calories": prev_calories,
        "calories_change": change,
        "avg_calories": round(sum(calories) / len(calories), 0) if calories else None,
        "avg_protein_g": round(sum(protein) / len(protein), 0) if protein else None,
        "avg_carb_g": round(sum(carbs) / len(carbs), 0) if carbs else None,
        "avg_fat_g": round(sum(fat) / len(fat), 0) if fat else None,
        "avg_sleep_hours": round(sum(sleep) / len(sleep), 1) if sleep else None,
        "consistency_pct": round((consistent / len(diet_notes)) * 100, 1) if diet_notes else None,
        "entries": len(diet_notes),
    }


def _serialize_planned_exercise_for_prompt(ex: dict[str, Any]) -> dict[str, Any]:
    kg = ex.get("kg") or 0
    rpe = ex.get("rpe_target") or ex.get("rpe")
    load_source = ex.get("load_source")

    if load_source == "rpe" or (kg == 0 and rpe is not None):
        return {
            "name": ex["name"],
            "sets": ex.get("sets"),
            "reps": ex.get("reps"),
            "load": f"@RPE {rpe}",
            "load_type": "rpe",
            "rpe_target": rpe,
        }
    if load_source == "unresolvable" or (kg == 0 and rpe is None):
        return {
            "name": ex["name"],
            "sets": ex.get("sets"),
            "reps": ex.get("reps"),
            "load": "unspecified",
            "load_type": "unspecified",
        }
    return {
        "name": ex["name"],
        "sets": ex.get("sets"),
        "reps": ex.get("reps"),
        "load": f"{kg}kg",
        "load_type": "absolute",
        "kg": kg,
        "rpe_target": rpe,
    }


def summarize_planned_sessions(
    sessions: list[dict[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    planned = [s for s in sessions if not (s.get("completed") or s.get("status") in ("logged", "completed")) and (s.get("status") in (None, "planned", "skipped") or not s.get("status"))]
    planned.sort(key=lambda s: s.get("date", ""))
    if limit is not None:
        planned = planned[:limit]

    rows: list[dict[str, Any]] = []
    for session in planned:
        exercises = session.get("planned_exercises") or session.get("exercises") or []
        serialized_exercises = [_serialize_planned_exercise_for_prompt(ex) for ex in exercises if ex.get("name")]
        rows.append({
            "date": session.get("date"),
            "day": session.get("day"),
            "week_number": session.get("week_number"),
            "phase": (session.get("phase") or {}).get("name") if isinstance(session.get("phase"), dict) else session.get("phase_name") or session.get("phase"),
            "status": session.get("status") or "planned",
            "exercises": serialized_exercises,
            "session_notes": session.get("session_notes") or "",
            "wellness": _serialize_wellness(session.get("wellness")),
        })
    return rows


def summarize_completed_sessions(
    sessions: list[dict[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    completed = [s for s in sessions if s.get("completed") or s.get("status") in ("logged", "completed")]
    completed.sort(key=lambda s: s.get("date", ""))
    if limit is not None:
        completed = completed[:limit]

    rows: list[dict[str, Any]] = []
    for session in completed:
        exercises = session.get("exercises") or []
        rows.append({
            "date": session.get("date"),
            "day": session.get("day"),
            "week_number": session.get("week_number"),
            "phase": (session.get("phase") or {}).get("name") if isinstance(session.get("phase"), dict) else session.get("phase_name") or session.get("phase"),
            "status": session.get("status") or "completed",
            "session_rpe": session.get("session_rpe"),
            "body_weight_kg": session.get("body_weight_kg"),
            "notes": session.get("session_notes") or "",
            "wellness": _serialize_wellness(session.get("wellness")),
            "exercises": [
                {
                    "name": ex.get("name"),
                    "sets": ex.get("sets"),
                    "reps": ex.get("reps"),
                    "kg": ex.get("kg"),
                    "rpe": ex.get("rpe"),
                    "failed": ex.get("failed", False),
                    "failed_sets": ex.get("failed_sets"),
                }
                for ex in exercises
                if ex.get("name")
            ],
        })
    return rows


def summarize_supplements(program: dict[str, Any]) -> dict[str, Any]:
    supplements = [
        {
            "name": supp.get("name"),
            "dose": supp.get("dose"),
        }
        for supp in program.get("supplements", [])
        if supp.get("name")
    ]

    phases: list[dict[str, Any]] = []
    for phase in program.get("supplement_phases", []):
        phases.append({
            "phase": phase.get("phase"),
            "phase_name": phase.get("phase_name"),
            "notes": phase.get("notes", ""),
            "block": phase.get("block"),
            "start_week": phase.get("start_week"),
            "end_week": phase.get("end_week"),
            "items": [
                {
                    "name": item.get("name"),
                    "dose": item.get("dose"),
                    "notes": item.get("notes", ""),
                }
                for item in (phase.get("items") or [])
                if item.get("name")
            ],
            "peak_week_protocol": phase.get("peak_week_protocol") or {},
        })

    return {
        "supplements": supplements,
        "supplement_phases": phases,
    }


def summarize_exercise_roi(
    program: dict[str, Any],
    sessions: list[dict[str, Any]] | None = None,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """Return top-N accessory exercises ranked by |pearson_r| between weekly
    volume and average intensity (via `volume_intensity_correlation`).

    Each row contains the exercise name, pearson_r, and a short numeric
    fingerprint of the volume/intensity series so the LLM can sanity-check
    the signal. Accessories only — the three big competition lifts are
    excluded because they're analyzed separately.
    """
    from analytics import volume_intensity_correlation

    sessions = sessions if sessions is not None else program.get("sessions", [])
    program_start = program.get("meta", {}).get("program_start", "") or ""
    big_lifts = frozenset(["squat", "bench", "bench press", "deadlift"])

    exercise_names: set[str] = set()
    for s in sessions:
        if not (s.get("completed") or s.get("status") in ("logged", "completed")):
            continue
        for ex in s.get("exercises", []):
            name = (ex.get("name") or "").strip()
            if not name:
                continue
            if name.lower() in big_lifts:
                continue
            exercise_names.add(name)

    rows: list[dict[str, Any]] = []
    for name in exercise_names:
        result = volume_intensity_correlation(sessions, name, program_start)
        r = result.get("pearson_r")
        if r is None:
            continue
        rows.append({
            "exercise": name,
            "pearson_r": r,
            "weeks_observed": len(result.get("volume_series") or []),
            "volume_series": result.get("volume_series") or [],
            "intensity_series": result.get("intensity_series") or [],
        })

    rows.sort(key=lambda row: abs(float(row["pearson_r"] or 0.0)), reverse=True)
    return rows[:top_n]


FORMULA_REFERENCE = """\
HOW THE ANALYSIS PAGE METRICS ARE CALCULATED

- Estimated 1RM: conservative RPE-table estimate for qualifying sets, or 90th percentile of
  qualifying session e1RMs when no comp result is available. Current maxes are therefore
  estimated 1 rep maxes, not true tested maxes.
- Progression rate: Theil-Sen slope of e1RM over effective training weeks, with deload and break
  weeks excluded. Fit quality is normalized MAD; Kendall tau is reported alongside the slope.
- RPE drift: Theil-Sen slope on raw or phase-residual RPE. Uses the same fit-quality reporting.
- Fatigue model: axial and peripheral scale nonlinearly with load, neural uses an intensity gate
  plus sqrt(load), systemic adds a modest absolute-load and intensity term.
- Fatigue index: 0.40 × failed compound set ratio + 0.35 × composite fatigue spike + 0.25 × RPE stress.
  RPE stress = clamp((avg_session_rpe - 7.5) / 2.5, 0, 1).
- INOL: reps / (100 × sqrt((1 - min(intensity ratio, 0.995))^2 + 0.02^2)) aggregated per lift per week,
  then multiplied by the lift profile stimulus coefficient. Defaults are per-lift, with optional overrides.
- ACWR: daily EWMA acute workload divided by daily EWMA chronic workload, with a weighted composite
  and phase-aware planned-overreach labeling.
- Relative intensity distribution: sets bucketed by load ratio vs estimated 1RM.
- Specificity ratio: SBD sets divided by total sets, plus a broader version that includes same-category work.
- Readiness score: weighted composite of fatigue, RPE drift, subjective wellness, short-term performance trend, and bodyweight deviation.
- DOTS: 500 × total / polynomial(bodyweight) using the sex-specific coefficients.
- Attempt selection: projected comp max × attempt percentages, rounded to the nearest 2.5 kg.
"""
