"""Temporal duration tool plugin — calculate duration between two dates.

Exports:
    get_tools()       → SDK Tool objects (side effect: register_tool() calls)
    get_schemas()     → snake_case name → JSON schema
    execute(name, args) → async dispatcher for non-agentic path
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Sequence

from pydantic import Field

from openhands.sdk import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _format_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


def _calculate_duration(start_date_str: str, end_date_str: str) -> Dict[str, Any]:
    import dateparser
    from dateutil.relativedelta import relativedelta

    start = dateparser.parse(start_date_str)
    if start is None:
        return {"error": f"Could not parse start_date: {start_date_str!r}"}

    end = dateparser.parse(end_date_str)
    if end is None:
        return {"error": f"Could not parse end_date: {end_date_str!r}"}

    delta = relativedelta(end, start)
    total_days = (end - start).days
    weeks = total_days // 7

    parts = []
    if delta.years:
        parts.append(f"{delta.years} year{'s' if delta.years != 1 else ''}")
    if delta.months:
        parts.append(f"{delta.months} month{'s' if delta.months != 1 else ''}")
    if delta.days:
        parts.append(f"{delta.days} day{'s' if delta.days != 1 else ''}")

    description = ", ".join(parts) if parts else "0 days"

    return {
        "years": delta.years,
        "months": delta.months,
        "days": delta.days,
        "weeks": weeks,
        "hours": abs(total_days * 24),
        "total_days": total_days,
        "description": description,
    }


class TimeDurationAction(Action):
    start_date: str = Field(
        description="Start date (ISO 8601, YYYY-MM-DD, or natural language like 'january 1st', 'next monday')"
    )
    end_date: str = Field(
        description="End date (ISO 8601, YYYY-MM-DD, or natural language like 'december 31st', 'in 3 months')"
    )


class TimeDurationObservation(Observation):
    pass


class TimeDurationExecutor(ToolExecutor[TimeDurationAction, TimeDurationObservation]):
    def __call__(self, action: TimeDurationAction, conversation=None) -> TimeDurationObservation:
        result = _calculate_duration(action.start_date, action.end_date)
        return TimeDurationObservation.from_text(_format_result(result))


class TimeDurationTool(ToolDefinition[TimeDurationAction, TimeDurationObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["TimeDurationTool"]:
        return [cls(
            description=(
                "Compute the precise duration between two dates in multiple units. "
                "Returns the difference broken down into years, months, weeks, days, and hours. "
                'Useful for answering "how long until...", "how many days between...", or '
                '"it\'s been X since...". Accepts ISO 8601, YYYY-MM-DD, or natural language '
                "phrases (resolved via dateparser)."
            ),
            action_type=TimeDurationAction,
            observation_type=TimeDurationObservation,
            executor=TimeDurationExecutor(),
        )]


register_tool("TimeDurationTool", TimeDurationTool)


def get_tools() -> List[Tool]:
    return [Tool(name="TimeDurationTool")]


def get_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "time_duration": {
            "name": "time_duration",
            "description": (
                "Compute the precise duration between two dates in multiple units. "
                "Returns the difference broken down into years, months, weeks, days, and hours. "
                'Useful for answering "how long until...", "how many days between...", or '
                '"it\'s been X since...". Accepts ISO 8601, YYYY-MM-DD, or natural language '
                "phrases (resolved via dateparser)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO 8601, YYYY-MM-DD, or natural language like 'january 1st', 'next monday')",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO 8601, YYYY-MM-DD, or natural language like 'december 31st', 'in 3 months')",
                    },
                },
                "required": ["start_date", "end_date"],
            },
        },
    }


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "time_duration":
        result = _calculate_duration(args["start_date"], args["end_date"])
        return _format_result(result)
    return f"Unknown temporal_duration tool: {name}"
