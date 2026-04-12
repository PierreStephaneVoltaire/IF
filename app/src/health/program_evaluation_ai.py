"""LLM-powered full-block program evaluation for powerlifting programs.

This uses the full completed/current block context plus planned sessions,
competition targets, athlete measurements, lift profiles, nutrition trends,
and the deterministic analytics report to produce a conservative program
assessment.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

import httpx

from config import LLM_BASE_URL, OPENROUTER_API_KEY
from health.analytics import weekly_analysis
from health.prompt_context import (
    FORMULA_REFERENCE,
    summarize_bodyweight_trend,
    summarize_completed_sessions,
    summarize_competitions,
    summarize_diet_context,
    summarize_lift_profiles,
    summarize_measurements,
    summarize_phases,
    summarize_planned_sessions,
    summarize_program_meta,
    summarize_supplements,
)
from models.router import resolve_preset_to_model

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
You are an objective sports scientist evaluating a powerlifting program.

Your job is performance analysis only. You are not a cheerleader and you are
not trying to redesign the whole program. The current block is assumed to be
deliberate. You should identify what is working, what is not working, and the
smallest useful changes that improve the athlete's chance of placing well.

Hard constraints:
- Do NOT recommend dropping a competition.
- Do NOT overhaul the full program unless there is a serious issue that would
  clearly stop the athlete from reaching the stated competition goals.
- Be conservative. Prefer "continue as is" or "monitor and adjust later" over
  large changes.
- Consider the athlete's lift style profiles and measurements. A metric that
  looks suboptimal in isolation may be acceptable for this athlete.
- Evaluate every competition in the block, but treat the final competition as
  the primary goal and earlier competitions as practice / preparation.
- Use the provided formulas / analysis context so the report is grounded in how
  the metrics were generated.

Return valid JSON only using the tool schema. Keep the recommendations small,
specific, and practical.
"""

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "report_program_evaluation",
        "description": "Report a conservative performance evaluation for a powerlifting block",
        "parameters": {
            "type": "object",
            "properties": {
                "stance": {
                    "type": "string",
                    "enum": ["continue", "monitor", "adjust", "critical"],
                    "description": "Overall recommendation stance",
                },
                "summary": {
                    "type": "string",
                    "description": "2-4 sentence overall summary of the block",
                },
                "what_is_working": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "what_is_not_working": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "competition_alignment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "competition": {"type": "string"},
                            "role": {"type": "string", "enum": ["primary", "practice"]},
                            "weeks_to_comp": {"type": ["number", "null"]},
                            "alignment": {"type": "string", "enum": ["good", "mixed", "poor"]},
                            "reason": {"type": "string"},
                        },
                        "required": ["competition", "role", "alignment", "reason"],
                    },
                },
                "small_changes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "change": {"type": "string"},
                            "why": {"type": "string"},
                            "risk": {"type": "string"},
                            "priority": {"type": "string", "enum": ["low", "moderate", "high"]},
                        },
                        "required": ["change", "why", "risk", "priority"],
                    },
                },
                "monitoring_focus": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "conclusion": {
                    "type": "string",
                    "description": "Short final recommendation",
                },
                "insufficient_data": {
                    "type": "boolean",
                },
                "insufficient_data_reason": {
                    "type": "string",
                },
            },
            "required": ["stance", "summary", "what_is_working", "what_is_not_working", "competition_alignment", "small_changes", "monitoring_focus", "conclusion"],
        },
    },
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _current_block_sessions(program: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in program.get("sessions", []) if (s.get("block") or "current") == "current"]


def _analysis_weeks(program: dict[str, Any], sessions: list[dict[str, Any]]) -> int:
    meta = program.get("meta", {})
    program_start = _parse_date(meta.get("program_start"))
    if program_start:
        return max(1, ((date.today() - program_start).days // 7) + 1)

    weeks = [int(s.get("week_number") or 0) for s in sessions if s.get("week_number")]
    return max(1, max(weeks) if weeks else 1)


def _sanitize_floats(obj: Any) -> Any:
    """Recursively replace NaN/Inf with None so json.dumps produces valid JSON."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _build_user_message(program: dict[str, Any]) -> str:
    meta = program.get("meta", {})
    sessions = _current_block_sessions(program)
    current_weeks = _analysis_weeks(program, sessions)
    window_start = _parse_date(meta.get("program_start"))

    completed_weeks = sorted({int(s.get("week_number") or 0) for s in sessions if s.get("completed") and s.get("week_number")})
    bodyweight_trend = summarize_bodyweight_trend(sessions, window_start=window_start)
    diet_context = summarize_diet_context(program, window_start=window_start, bodyweight_trend=bodyweight_trend)
    competitions = summarize_competitions(program)
    lift_profiles = summarize_lift_profiles(program.get("lift_profiles"))
    phases = summarize_phases(program.get("phases"))
    measurements = summarize_measurements(meta)
    supplements = summarize_supplements(program)
    completed_sessions = summarize_completed_sessions(sessions)
    planned_sessions = summarize_planned_sessions(sessions)
    weekly_report = weekly_analysis(program, sessions, weeks=current_weeks, block="current")
    current_block_completed_sessions = len([s for s in sessions if s.get("completed")])

    payload = {
        "task": "Evaluate the current powerlifting block and judge how well it is directing the athlete toward the competition goals.",
        "instructions": {
            "tone": "objective sports scientist",
            "stance_preference": "conservative",
            "do_not": [
                "drop a competition",
                "recommend wholesale redesigns unless a serious issue exists",
                "overreact to a single metric without context",
            ],
            "focus": [
                "overall trajectory",
                "what is going right",
                "what is going wrong",
                "goal alignment for each competition",
                "small useful adjustments only",
                "whether to continue as-is, monitor, or make limited changes",
            ],
        },
        "program_meta": summarize_program_meta(meta),
        "phases": phases,
        "full_block_summary": {
            "analysis_weeks": current_weeks,
            "completed_sessions": current_block_completed_sessions,
            "completed_weeks": completed_weeks,
        },
        "completed_block_weeks": completed_weeks,
        "competitions": competitions,
        "lift_profiles": lift_profiles,
        "athlete_measurements": measurements,
        "supplements": supplements,
        "diet_context": diet_context,
        "bodyweight_trend": bodyweight_trend,
        "completed_sessions": completed_sessions,
        "planned_sessions": planned_sessions,
        "weekly_analysis": weekly_report,
        "formula_reference": FORMULA_REFERENCE,
    }

    return json.dumps(_sanitize_floats(payload), indent=2, default=str)


async def generate_program_evaluation_report(program: dict[str, Any]) -> dict[str, Any]:
    """Call the LLM to generate a conservative block evaluation report."""
    user_msg = _build_user_message(program)
    model = resolve_preset_to_model("openrouter/@preset/health")
    logger.info(f"[ProgramEvaluationAI] model={model} payload_chars={len(user_msg)}")

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "tools": [_TOOL_SCHEMA],
                    "tool_choice": "required",
                },
            )
            if resp.status_code >= 400:
                logger.error(f"[ProgramEvaluationAI] HTTP {resp.status_code} from OpenRouter: {resp.text[:2000]}")
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
            "stance": args.get("stance", "monitor"),
            "summary": args.get("summary", ""),
            "what_is_working": args.get("what_is_working", []),
            "what_is_not_working": args.get("what_is_not_working", []),
            "competition_alignment": args.get("competition_alignment", []),
            "small_changes": args.get("small_changes", []),
            "monitoring_focus": args.get("monitoring_focus", []),
            "conclusion": args.get("conclusion", ""),
            "insufficient_data": args.get("insufficient_data", False),
            "insufficient_data_reason": args.get("insufficient_data_reason", ""),
        }

    except Exception as e:
        logger.error(f"[ProgramEvaluationAI] generation failed: {e}")
        return {
            "stance": "monitor",
            "summary": f"AI evaluation failed: {e}",
            "what_is_working": [],
            "what_is_not_working": [],
            "competition_alignment": [],
            "small_changes": [],
            "monitoring_focus": [],
            "conclusion": "Continue monitoring until the AI report can be regenerated.",
            "insufficient_data": True,
            "insufficient_data_reason": str(e),
        }
