"""AI-powered estimation of training maxes for accessories.

Used during template application when a required accessory has no e1RM.
Estimates are conservative ratios of primary SBD lifts.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import httpx

from config import LLM_BASE_URL, OPENROUTER_API_KEY, IMPORT_FAST_MODEL

logger = logging.getLogger(__name__)


def _json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

_SYSTEM_PROMPT = """\
You are estimating training maxes for powerlifting accessory exercises
based on an athlete's competition lift maxes, lifting profiles, and past history.

RULES:
- Use anatomical and biomechanical reasoning — relate each accessory to its
  closest primary lift by movement pattern and muscle overlap.
- Consider any provided lifting profiles (e.g., leverages, sticking points) to adjust ratios.
- If 'past_instances' are provided for an exercise (sets, reps, kg, RPE, notes), use them to anchor your estimate. E.g., if they did 100kg x 8 @ RPE 8, that is highly informative! Notes might also indicate if they are new to the movement or experience discomfort.
- Express estimates as a ratio of the relevant primary lift e1RM.
- Be conservative. Underestimating is safer than overestimating.
- Confidence:
    "medium" — well-established ratio (e.g. RDL to deadlift) or solid past history
    "low"    — speculative or unusual exercise with no history

Return JSON only:
{
  "estimates": [
    {
      "exercise": "Romanian Deadlift",
      "e1rm_kg": 145.0,
      "ratio": 0.78,
      "primary_lift_used": "deadlift",
      "basis": "Hip hinge, similar leverages, typically 75-80% of deadlift. Past set of 120kg x8 supports this.",
      "confidence": "medium"
    }
  ]
}
"""

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "report_e1rm_estimates",
        "description": "Report estimated e1RMs for accessory exercises",
        "parameters": {
            "type": "object",
            "properties": {
                "estimates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "exercise": {"type": "string"},
                            "e1rm_kg": {"type": "number"},
                            "ratio": {"type": "number"},
                            "primary_lift_used": {"type": "string", "enum": ["squat", "bench", "deadlift"]},
                            "basis": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["medium", "low"]}
                        },
                        "required": ["exercise", "e1rm_kg", "ratio", "primary_lift_used", "basis", "confidence"]
                    }
                }
            },
            "required": ["estimates"]
        }
    }
}

async def generate_e1rm_backfill_report(
    missing_exercises: list[str],
    current_maxes: dict[str, float],
    lift_profiles: list[dict[str, Any]] | None = None,
    body_metrics: dict[str, Any] | None = None,
    past_instances: dict[str, list[dict[str, Any]]] | None = None
) -> dict[str, Any]:
    """Call the LLM to estimate e1RMs for missing exercises."""
    user_msg = json.dumps({
        "missing_exercises": missing_exercises,
        "current_maxes": current_maxes,
        "lift_profiles": lift_profiles or [],
        "body_metrics": body_metrics or {},
        "past_instances": past_instances or {}
    }, indent=2, default=_json_default)

    logger.info(f"[E1rmBackfillAI] model={IMPORT_FAST_MODEL} payload_chars={len(user_msg)}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": IMPORT_FAST_MODEL,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "tools": [_TOOL_SCHEMA],
                    "tool_choice": {"type": "function", "function": {"name": "report_e1rm_estimates"}},
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
            content = message.get("content", "").strip()
            if content.startswith("{"):
                return json.loads(content)
            raise ValueError("No tool calls in LLM response")

        args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
        return json.loads(args_str)

    except Exception as e:
        logger.error(f"[E1rmBackfillAI] estimation failed: {e}")
        return {
            "estimates": [
                {
                    "exercise": name,
                    "e1rm_kg": 0.0,
                    "ratio": 0.0,
                    "primary_lift_used": "squat",
                    "basis": f"AI estimation failed: {e}",
                    "confidence": "low"
                }
                for name in missing_exercises
            ]
        }
