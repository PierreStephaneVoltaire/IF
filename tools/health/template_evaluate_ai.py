"""AI-powered evaluation of training templates.

Analyzes a template against an athlete's profile, competition timeline,
and current metrics to produce a recommendation stance and suggestions.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import LLM_BASE_URL, OPENROUTER_API_KEY, ANALYSIS_MODEL, ANALYSIS_MODEL_THINKING_BUDGET

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are evaluating a powerlifting training template against an athlete's
current profile and competition timeline.

RULES:
- Be specific and data-cited. Reference weeks, exercises, phases by name.
- stance values: "continue" | "monitor" | "adjust" | "critical"
  "continue"  — template is well-matched to athlete profile and timeline
  "monitor"   — viable but has elements to watch
  "adjust"    — specific changes recommended before applying
  "critical"  — template is poorly matched or potentially harmful
- strengths and weaknesses: minimum 2 each if data supports it
- suggestions: each must cite the specific data point motivating it
- projected_readiness_at_comp: integer 0-100, use readiness formula logic
- Do not invent data not present in the input.
- If athlete_context fields are null or absent, note the missing context
  and adjust confidence accordingly. Do not refuse to evaluate.

PLANNED SESSION INTERPRETATION:
- Sets with load_type "rpe" and no kg: treat as intensity-regulated.
  Estimate relative intensity as RPE 10 ≈ 100%, RPE 9 ≈ 96%, RPE 8 ≈ 92%,
  RPE 7 ≈ 88% of current e1RM for qualitative volume assessment.
- Sets with load_type "percentage": use load_value × e1RM for intensity.
- Sets with load_type "unresolvable": exclude from volume assessment,
  note as incomplete data.
- Never cite kg projections for RPE-based sets. Use language like
  "RPE 8 prescribed" or "intensity-regulated volume".

Return JSON only:
{
  "stance": "continue | monitor | adjust | critical",
  "summary": "2-3 sentence plain English summary",
  "strengths": ["string"],
  "weaknesses": ["string"],
  "suggestions": [
    {
      "type": "string",
      "week": number | null,
      "phase": "string | null",
      "exercise": "string | null",
      "rationale": "string citing specific data"
    }
  ],
  "projected_readiness_at_comp": number,
  "data_citations": ["string"]
}
"""

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "report_template_evaluation",
        "description": "Report the evaluation of a training template",
        "parameters": {
            "type": "object",
            "properties": {
                "stance": {"type": "string", "enum": ["continue", "monitor", "adjust", "critical"]},
                "summary": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "week": {"type": ["number", "null"]},
                            "phase": {"type": ["string", "null"]},
                            "exercise": {"type": ["string", "null"]},
                            "rationale": {"type": "string"}
                        },
                        "required": ["type", "rationale"]
                    }
                },
                "projected_readiness_at_comp": {"type": "number"},
                "data_citations": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["stance", "summary", "strengths", "weaknesses", "suggestions", "projected_readiness_at_comp"]
        }
    }
}

def _sanitize_floats(obj: Any) -> Any:
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

async def generate_template_evaluate_report(
    template: dict[str, Any],
    athlete_context: dict[str, Any]
) -> dict[str, Any]:
    """Call the LLM to evaluate a template against athlete context."""
    user_msg = json.dumps({
        "template": template,
        "athlete_context": athlete_context
    }, indent=2)

    logger.info(f"[TemplateEvaluateAI] model={ANALYSIS_MODEL} payload_chars={len(user_msg)}")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": ANALYSIS_MODEL,
                    "thinking": {"type": "enabled", "budget_tokens": ANALYSIS_MODEL_THINKING_BUDGET},
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "tools": [_TOOL_SCHEMA],
                    "tool_choice": {"type": "function", "function": {"name": "report_template_evaluation"}},
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
                return _sanitize_floats(json.loads(content))
            raise ValueError("No tool calls in LLM response")

        args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
        return _sanitize_floats(json.loads(args_str))

    except Exception as e:
        logger.error(f"[TemplateEvaluateAI] evaluation failed: {e}")
        return {
            "stance": "monitor",
            "summary": f"AI evaluation failed: {e}",
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "projected_readiness_at_comp": 50
        }
