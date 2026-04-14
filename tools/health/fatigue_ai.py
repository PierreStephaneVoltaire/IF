"""LLM-based 4-dimensional fatigue profile estimation for exercises.

Uses OpenRouter to call a fast model with tool calling to get structured
fatigue profile estimates (axial, neural, peripheral, systemic).
"""
from __future__ import annotations

import json
import logging

import httpx

from config import LLM_BASE_URL, OPENROUTER_API_KEY, MODEL_ROUTER_MODEL

logger = logging.getLogger(__name__)

_DEFAULT_FATIGUE_PROFILE = {
    "axial": 0.3,
    "neural": 0.3,
    "peripheral": 0.5,
    "systemic": 0.3,
}

_SYSTEM_PROMPT = """\
You are a sports science expert estimating fatigue profiles for resistance training exercises.

For each exercise, estimate 4 fatigue dimensions on a 0.0-1.0 scale:

1. **Axial** (0.0-1.0): Spinal compression loading. How much compressive force goes through the spine.
   - Squats/Deadlifts: 0.7-0.9
   - Overhead press: 0.4-0.6
   - Bench press: 0.1-0.3
   - Isolation exercises: 0.0-0.1

2. **Neural** (0.0-1.0): Central nervous system demand baseline (before intensity scaling).
   - Heavy compounds near 1RM: 0.7-0.9
   - Moderate compounds: 0.4-0.6
   - Machine/isolation: 0.1-0.3
   - Cardio-only movements: 0.0-0.1

3. **Peripheral** (0.0-1.0): Local muscle damage potential. How much muscle tissue is stressed.
   - Big compound movements: 0.6-0.8
   - Medium compounds: 0.4-0.6
   - Isolation: 0.3-0.5
   - Bodyweight/rehab: 0.1-0.3

4. **Systemic** (0.0-1.0): Cardiovascular/metabolic demand.
   - Deadlifts: 0.7-0.9
   - Squats: 0.5-0.7
   - Upper body compounds: 0.3-0.5
   - Isolation: 0.1-0.3

Calibration anchors:
- Competition squat: axial=0.85, neural=0.80, peripheral=0.75, systemic=0.60
- Competition bench: axial=0.20, neural=0.70, peripheral=0.65, systemic=0.35
- Competition deadlift: axial=0.90, neural=0.90, peripheral=0.80, systemic=0.80
- Bicep curl: axial=0.00, neural=0.10, peripheral=0.40, systemic=0.10
- Face pulls: axial=0.00, neural=0.05, peripheral=0.25, systemic=0.05

ATHLETE CONTEXT (when provided):
If the user message includes athlete body metrics (bodyweight, height, arm wingspan, leg
length) or a lift profile (style notes, sticking points, volume tolerance), treat them as
soft modifiers — not hard overrides — on the estimate for exercises where those leverages
matter. Examples: long femurs relative to torso tend to shift squat fatigue toward axial
and systemic; short arms on a bench presser reduce bar path length and can lower peripheral
on bench variations; a reported quad-dominant squat style raises peripheral on squat
variations. When metrics are missing, ignore leverages entirely — do not speculate.

DO NOT FACTOR IN:
- Diet, calories, macros, water intake, or sleep — these are tracked separately and are
  out of scope for this estimate.
- Supplements or ergogenic aids — not in scope here.
- Training history, recent fatigue, or programming context — estimate the exercise in
  isolation.

Rules:
- Round all values to nearest 0.05
- Consider equipment, muscles involved, and movement pattern
- Provide brief reasoning for the estimate; if athlete metrics or lift profile influenced
  the estimate, say which field and in which direction
"""

_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "estimate_fatigue_profile",
        "description": "Estimate 4-dimensional fatigue profile for an exercise",
        "parameters": {
            "type": "object",
            "properties": {
                "axial": {"type": "number", "description": "Spinal compression loading 0.0-1.0"},
                "neural": {"type": "number", "description": "CNS demand baseline 0.0-1.0"},
                "peripheral": {"type": "number", "description": "Local muscle damage potential 0.0-1.0"},
                "systemic": {"type": "number", "description": "Cardiovascular/metabolic demand 0.0-1.0"},
                "reasoning": {"type": "string", "description": "Brief explanation of the estimates"},
            },
            "required": ["axial", "neural", "peripheral", "systemic", "reasoning"],
        },
    },
}


def _round_to_nearest(value: float, step: float = 0.05) -> float:
    return round(round(value / step) * step, 2)


_BIG_LIFT_KEYS = {
    "squat": "squat",
    "back squat": "squat",
    "bench press": "bench",
    "bench": "bench",
    "deadlift": "deadlift",
    "conventional deadlift": "deadlift",
    "sumo deadlift": "deadlift",
}


def _match_lift_profile(
    exercise: dict,
    lift_profiles: list[dict] | None,
) -> dict | None:
    if not lift_profiles:
        return None
    name = (exercise.get("name") or "").strip().lower()
    category = (exercise.get("category") or "").strip().lower()
    target = _BIG_LIFT_KEYS.get(name) or (category if category in ("squat", "bench", "deadlift") else None)
    if not target:
        return None
    return next((p for p in lift_profiles if (p.get("lift") or "").lower() == target), None)


def _format_athlete_context(meta: dict | None) -> list[str]:
    if not meta:
        return []
    fields = [
        ("bodyweight_kg", meta.get("current_body_weight_kg")),
        ("height_cm", meta.get("height_cm")),
        ("arm_wingspan_cm", meta.get("arm_wingspan_cm")),
        ("leg_length_cm", meta.get("leg_length_cm")),
        ("sex", meta.get("sex")),
    ]
    present = [(k, v) for k, v in fields if v not in (None, "", 0)]
    if not present:
        return []
    lines = ["", "Athlete metrics:"]
    for k, v in present:
        lines.append(f"  {k}: {v}")
    return lines


def _format_lift_profile(profile: dict | None) -> list[str]:
    if not profile:
        return []
    lines = ["", f"Lift profile ({profile.get('lift', '?')}):"]
    for field in ("style_notes", "sticking_points", "primary_muscle", "volume_tolerance"):
        value = profile.get(field)
        if value:
            lines.append(f"  {field}: {value}")
    return lines if len(lines) > 1 else []


def _build_user_message(
    exercise: dict,
    program_meta: dict | None = None,
    lift_profiles: list[dict] | None = None,
) -> str:
    parts = [f"Exercise: {exercise.get('name', 'Unknown')}"]
    if exercise.get("category"):
        parts.append(f"Category: {exercise['category']}")
    if exercise.get("equipment"):
        parts.append(f"Equipment: {exercise['equipment']}")
    if exercise.get("primary_muscles"):
        parts.append(f"Primary muscles: {', '.join(exercise['primary_muscles'])}")
    if exercise.get("secondary_muscles"):
        parts.append(f"Secondary muscles: {', '.join(exercise['secondary_muscles'])}")
    if exercise.get("cues"):
        parts.append(f"Cues: {', '.join(exercise['cues'])}")
    if exercise.get("notes"):
        parts.append(f"Notes: {exercise['notes']}")

    parts.extend(_format_athlete_context(program_meta))
    parts.extend(_format_lift_profile(_match_lift_profile(exercise, lift_profiles)))

    return "\n".join(parts)


async def estimate_fatigue_profile(
    exercise: dict,
    program_meta: dict | None = None,
    lift_profiles: list[dict] | None = None,
) -> dict:
    """Call LLM to estimate 4-dimensional fatigue profile for an exercise.

    When `program_meta` (body metrics) or `lift_profiles` are supplied and
    relevant to the exercise, they're included in the prompt as soft context
    to adjust for the athlete's leverages and stated style.
    """
    try:
        user_msg = _build_user_message(exercise, program_meta=program_meta, lift_profiles=lift_profiles)
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "tool_choice": {"type": "function", "function": {"name": "estimate_fatigue_profile"}},
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract tool call arguments
        choices = data.get("choices", [])
        if not choices:
            logger.warning("[FatigueAI] No choices in response")
            return {**_DEFAULT_FATIGUE_PROFILE, "reasoning": "AI estimation failed: no response"}

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            logger.warning("[FatigueAI] No tool calls in response")
            return {**_DEFAULT_FATIGUE_PROFILE, "reasoning": "AI estimation failed: no tool call"}

        args_str = tool_calls[0].get("function", {}).get("arguments", "{}")
        args = json.loads(args_str)

        profile = {
            "axial": _round_to_nearest(float(args.get("axial", 0.3))),
            "neural": _round_to_nearest(float(args.get("neural", 0.3))),
            "peripheral": _round_to_nearest(float(args.get("peripheral", 0.5))),
            "systemic": _round_to_nearest(float(args.get("systemic", 0.3))),
            "reasoning": args.get("reasoning", ""),
        }
        return profile

    except Exception as e:
        logger.error(f"[FatigueAI] estimation failed: {e}")
        return {**_DEFAULT_FATIGUE_PROFILE, "reasoning": f"AI estimation failed: {e}"}
