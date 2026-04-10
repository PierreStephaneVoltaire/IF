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

Rules:
- Round all values to nearest 0.05
- Consider equipment, muscles involved, and movement pattern
- Provide brief reasoning for the estimate
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


def _build_user_message(exercise: dict) -> str:
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
    return "\n".join(parts)


async def estimate_fatigue_profile(exercise: dict) -> dict:
    """Call LLM to estimate 4-dimensional fatigue profile for an exercise."""
    try:
        user_msg = _build_user_message(exercise)
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
