"""AI-powered exercise ROI / correlation analysis for powerlifting programs.

Analyzes whether accessory exercise volume trends correlate with improvements
in the main competition lifts (Squat, Bench, Deadlift).

Only produces anatomically plausible correlations — exercises working muscles
not involved in a given lift are excluded to avoid spurious correlations.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from config import LLM_BASE_URL, OPENROUTER_API_KEY, MODEL_ROUTER_MODEL

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert powerlifting coach analyzing training data to identify which accessory exercises
correlate with improvements in Squat, Bench Press, and Deadlift performance.

Your job is to find meaningful, anatomically plausible correlations between accessory exercise
volume/intensity trends and changes in the big 3 competition lift e1RM estimates.

CRITICAL RULES:
1. Only flag correlations where the muscles worked by the exercise are ANATOMICALLY INVOLVED
   in that big lift. For example:
   - Tricep work → Bench Press (yes, triceps are primary movers)
   - Leg Press → Squat (yes, quads overlap)
   - Lat Pulldown → Deadlift (yes, lats stabilize the pull)
   - Bicep Curls → Bench Press (no, biceps are not primary movers in bench)
   - Calf Raises → Squat (no, calves play negligible role in squat mechanics)

2. HIGH CORRELATION between anatomically UNRELATED exercises and a big lift is a FALSE POSITIVE.
   Do NOT report these – they are likely explained by general training frequency or coincidence.

3. Use the athlete's stated lift profiles (style, muscle dominance, sticking points) to
   contextualize relevance. For example:
   - A tricep-dominant bencher → tricep accessories are MORE likely to matter
   - A quad-dominant squatter → leg press/hack squat matter MORE than hamstring work
   - Sticking point at lockout → exercises targeting the lockout muscles are MORE relevant

4. For each finding, provide:
   - exercise: name of the accessory exercise
   - lift: which competition lift (squat, bench, or deadlift)
   - correlation_direction: "positive" (more volume = better performance), "negative", or "unclear"
   - strength: "strong", "moderate", or "weak"
   - reasoning: 2-3 sentences explaining WHY this correlation makes biomechanical sense
   - caveat: note that correlation ≠ causation and any confounds

5. If there is INSUFFICIENT DATA (fewer than 4 distinct weeks, missing e1RM data, or no
   meaningful accessory volume), return an empty findings array with a note.

6. Be conservative. It is better to report fewer high-confidence findings than many speculative ones.
   Omit findings with weak statistical backing or questionable anatomical relevance.

7. Do NOT analyze squat vs deadlift correlation or bench vs squat — the user only wants
   accessory → main lift analysis.

Output ONLY valid JSON in the format specified by the tool call.
"""

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "report_correlation_findings",
        "description": "Report accessory exercise to big lift correlation findings",
        "parameters": {
            "type": "object",
            "properties": {
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "exercise": {"type": "string"},
                            "lift": {"type": "string", "enum": ["squat", "bench", "deadlift"]},
                            "correlation_direction": {"type": "string", "enum": ["positive", "negative", "unclear"]},
                            "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                            "reasoning": {"type": "string"},
                            "caveat": {"type": "string"},
                        },
                        "required": ["exercise", "lift", "correlation_direction", "strength", "reasoning", "caveat"],
                    },
                },
                "summary": {
                    "type": "string",
                    "description": "1-2 sentence overall summary of the correlation analysis",
                },
                "insufficient_data": {
                    "type": "boolean",
                    "description": "True if data is insufficient for meaningful analysis",
                },
                "insufficient_data_reason": {
                    "type": "string",
                    "description": "If insufficient_data is true, explain why",
                },
            },
            "required": ["findings", "summary"],
        },
    },
}


def _build_weekly_e1rm(sessions: list[dict], cutoff_str: str) -> dict[int, dict[str, float]]:
    """Build weekly best e1RM estimates per big lift from sessions."""
    weekly: dict[int, dict[str, float]] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        if s.get("date", "") < cutoff_str:
            continue
        if (s.get("block") or "current") != "current":
            continue
        wn = s.get("week_number", 0)
        if wn <= 0:
            continue

        for ex in s.get("exercises", []):
            name_lower = ex.get("name", "").lower()
            kg = ex.get("kg") or 0
            reps = ex.get("reps") or 0
            if kg <= 0 or reps <= 0:
                continue

            # Estimate e1RM via Epley formula
            e1rm = kg * (1 + reps / 30) if reps < 30 else kg

            # Map to big lift
            lift = None
            if "squat" in name_lower and "back" not in name_lower.replace("backout", ""):
                lift = "squat"
            elif name_lower in ("bench press", "bench") or (
                "bench" in name_lower and "press" in name_lower and "incline" not in name_lower
                and "close" not in name_lower and "pause" not in name_lower and "spoto" not in name_lower
            ):
                lift = "bench"
            elif "deadlift" in name_lower and "rdl" not in name_lower and "romanian" not in name_lower:
                lift = "deadlift"

            if lift:
                if wn not in weekly:
                    weekly[wn] = {}
                weekly[wn][lift] = max(weekly[wn].get(lift, 0), e1rm)

    return weekly


def _build_weekly_accessory_volume(sessions: list[dict], cutoff_str: str) -> dict[int, dict[str, float]]:
    """Build weekly volume (sets × reps × kg) per accessory exercise."""
    weekly: dict[int, dict[str, float]] = {}
    big_lift_names = frozenset(["squat", "bench", "bench press", "deadlift"])

    for s in sessions:
        if not s.get("completed"):
            continue
        if s.get("date", "") < cutoff_str:
            continue
        if (s.get("block") or "current") != "current":
            continue
        wn = s.get("week_number", 0)
        if wn <= 0:
            continue

        for ex in s.get("exercises", []):
            name = ex.get("name", "")
            name_lower = name.lower().strip()

            # Skip main competition lifts (keep accessories)
            if name_lower in big_lift_names:
                continue
            if name_lower in ("squat", "bench press", "deadlift"):
                continue

            vol = (ex.get("sets") or 0) * (ex.get("reps") or 0) * (ex.get("kg") or 0)
            if vol <= 0:
                continue

            if wn not in weekly:
                weekly[wn] = {}
            weekly[wn][name] = weekly[wn].get(name, 0) + vol

    return weekly


def _build_user_message(
    weeks: int,
    window_start: str,
    weekly_e1rm: dict,
    weekly_accessory: dict,
    lift_profiles: list[dict],
    athlete_measurements: dict | None = None,
    caloric_status: str | None = None,
    bodyweight_trend: dict | None = None,
    weeks_to_primary_comp: float | None = None,
) -> str:
    lines = [f"## Analysis window: Last {weeks} weeks (from {window_start})\n"]

    if weeks_to_primary_comp is not None:
        lines.append(f"**Weeks to primary competition:** {weeks_to_primary_comp:.1f}\n")

    # Lift profiles
    if lift_profiles:
        lines.append("## Athlete Lift Profiles\n")
        for p in lift_profiles:
            lift = p.get("lift", "?")
            lines.append(f"### {lift.title()}")
            if p.get("style_notes"):
                lines.append(f"  Style: {p['style_notes']}")
            if p.get("sticking_points"):
                lines.append(f"  Sticking points: {p['sticking_points']}")
            if p.get("primary_muscle"):
                lines.append(f"  Primary muscle: {p['primary_muscle']}")
            if p.get("volume_tolerance"):
                lines.append(f"  Volume tolerance: {p['volume_tolerance']}")
        lines.append("")

    # Athlete measurements
    if athlete_measurements and any(v for v in athlete_measurements.values()):
        lines.append("## Athlete Measurements\n")
        for k, v in athlete_measurements.items():
            if v is not None:
                lines.append(f"  {k.replace('_', ' ')}: {v}")
        lines.append("")

    # Caloric / body weight context
    if caloric_status:
        lines.append(f"**Caloric status:** {caloric_status}\n")
    if bodyweight_trend:
        direction = bodyweight_trend.get("direction", "unclear")
        change = bodyweight_trend.get("change")
        latest = bodyweight_trend.get("latest")
        if latest is not None:
            change_str = f" ({'+' if change and change > 0 else ''}{change} kg over window)" if change is not None else ""
            lines.append(f"**Body weight trend:** {latest} kg, {direction}{change_str}\n")

    # Weekly e1RM table
    all_weeks = sorted(set(list(weekly_e1rm.keys()) + list(weekly_accessory.keys())))
    if not all_weeks:
        lines.append("No data available.\n")
        return "\n".join(lines)

    lines.append("## Weekly e1RM Estimates (kg)\n")
    lines.append("| Week | Squat | Bench | Deadlift |")
    lines.append("|------|-------|-------|----------|")
    for wn in all_weeks:
        e = weekly_e1rm.get(wn, {})
        squat = f"{e.get('squat', 0):.1f}" if e.get("squat") else "-"
        bench = f"{e.get('bench', 0):.1f}" if e.get("bench") else "-"
        dead = f"{e.get('deadlift', 0):.1f}" if e.get("deadlift") else "-"
        lines.append(f"| W{wn} | {squat} | {bench} | {dead} |")
    lines.append("")

    # Top accessories by total volume
    acc_totals: dict[str, float] = {}
    for wn, exes in weekly_accessory.items():
        for name, vol in exes.items():
            acc_totals[name] = acc_totals.get(name, 0) + vol

    top_accessories = sorted(acc_totals.items(), key=lambda x: -x[1])[:20]

    if top_accessories:
        lines.append("## Weekly Accessory Volume (sets × reps × kg) — Top 20\n")
        header = "| Week | " + " | ".join(name for name, _ in top_accessories) + " |"
        sep = "|------|" + "|".join("---" for _ in top_accessories) + "|"
        lines.append(header)
        lines.append(sep)
        for wn in all_weeks:
            row = f"| W{wn} | "
            for name, _ in top_accessories:
                vol = weekly_accessory.get(wn, {}).get(name, 0)
                row += (f"{vol:.0f}" if vol else "-") + " | "
            lines.append(row)
        lines.append("")

    lines.append(
        "## Task\nAnalyze the data above. Identify which accessory exercises have volume trends "
        "that plausibly correlate with changes in Squat, Bench, or Deadlift e1RM. "
        "Only report anatomically relevant correlations as per the system instructions."
    )
    return "\n".join(lines)


async def generate_correlation_report(
    sessions: list[dict],
    lift_profiles: list[dict],
    weeks: int,
    window_start: str,
    program: dict | None = None,
) -> dict[str, Any]:
    """Call LLM to generate correlation findings for the given session window."""
    weekly_e1rm = _build_weekly_e1rm(sessions, window_start)
    weekly_accessory = _build_weekly_accessory_volume(sessions, window_start)

    distinct_weeks = len(set(list(weekly_e1rm.keys()) + list(weekly_accessory.keys())))
    if distinct_weeks < 4:
        return {
            "findings": [],
            "summary": "Insufficient data for correlation analysis.",
            "insufficient_data": True,
            "insufficient_data_reason": f"Only {distinct_weeks} weeks of data found. Need at least 4.",
        }

    # Build enriched context
    meta = program.get("meta", {}) if program else {}
    athlete_measurements = {
        "height_cm": meta.get("height_cm"),
        "arm_wingspan_cm": meta.get("arm_wingspan_cm"),
        "leg_length_cm": meta.get("leg_length_cm"),
        "weight_class_kg": meta.get("weight_class_kg"),
        "current_body_weight_kg": meta.get("current_body_weight_kg"),
    }

    # Weeks to primary comp
    try:
        from health.prompt_context import summarize_competitions, summarize_bodyweight_trend, summarize_diet_context
        comp_summary = summarize_competitions(program)
        primary = comp_summary.get("primary_competition") or {}
        weeks_to_primary_comp = primary.get("weeks_to_comp")

        bw_trend = summarize_bodyweight_trend(program.get("sessions", []))
        caloric_context = summarize_diet_context(program, bodyweight_trend=bw_trend)
        caloric_status = caloric_context.get("status", "unclear")
        bodyweight_trend = bw_trend
    except Exception:
        weeks_to_primary_comp = None
        caloric_status = None
        bodyweight_trend = None

    user_msg = _build_user_message(
        weeks, window_start, weekly_e1rm, weekly_accessory, lift_profiles,
        athlete_measurements=athlete_measurements,
        caloric_status=caloric_status,
        bodyweight_trend=bodyweight_trend,
        weeks_to_primary_comp=weeks_to_primary_comp,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL_ROUTER_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "tools": [_TOOL_SCHEMA],
                    "tool_choice": "required",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices in LLM response")

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            raise ValueError("No tool calls in LLM response")

        args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
        args = json.loads(args_str)

        return {
            "findings": args.get("findings", []),
            "summary": args.get("summary", ""),
            "insufficient_data": args.get("insufficient_data", False),
            "insufficient_data_reason": args.get("insufficient_data_reason", ""),
        }

    except Exception as e:
        logger.error(f"[CorrelationAI] generation failed: {e}")
        return {
            "findings": [],
            "summary": f"AI analysis failed: {e}",
            "insufficient_data": True,
            "insufficient_data_reason": str(e),
        }
