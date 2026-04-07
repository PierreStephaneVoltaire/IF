"""Temporal from-unix tool plugin — convert Unix timestamp to structured datetime.

Exports:
    get_tools()       → SDK Tool objects (side effect: register_tool() calls)
    get_schemas()     → snake_case name → JSON schema
    execute(name, args) → async dispatcher for non-agentic path
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
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


def _relative_description(dt: datetime) -> str:
    from dateutil.relativedelta import relativedelta

    now = datetime.now(timezone.utc)
    diff = relativedelta(dt.replace(tzinfo=timezone.utc), now)
    total_days = (dt.replace(tzinfo=timezone.utc) - now).days
    is_future = total_days > 0
    days = abs(total_days)

    if days == 0:
        return "today"
    elif days == 1:
        return "tomorrow" if is_future else "yesterday"
    elif days < 7:
        return f"in {days} days" if is_future else f"{days} days ago"
    elif days < 30:
        weeks = days // 7
        return f"in {weeks} week{'s' if weeks != 1 else ''}" if is_future else f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif days < 365:
        months = days // 30
        return f"in ~{months} month{'s' if months != 1 else ''}" if is_future else f"~{months} month{'s' if months != 1 else ''} ago"
    else:
        years = days // 365
        return f"in ~{years} year{'s' if years != 1 else ''}" if is_future else f"~{years} year{'s' if years != 1 else ''} ago"


def _unix_to_datetime(unix_timestamp: float) -> Dict[str, Any]:
    try:
        ts = float(unix_timestamp)
    except (ValueError, TypeError):
        return {"error": f"Invalid timestamp: {unix_timestamp!r}"}

    # Auto-detect milliseconds
    if abs(ts) > 1e12:
        ts = ts / 1000.0

    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, OSError, OverflowError) as e:
        return {"error": f"Timestamp out of range: {e}"}

    return {
        "unix_timestamp": int(unix_timestamp),
        "iso8601": dt.isoformat(),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "day_of_week": dt.strftime("%A"),
        "human_readable": dt.strftime("%B %d, %Y at %I:%M %p UTC"),
        "relative_description": _relative_description(dt),
    }


class UnixToDatetimeAction(Action):
    unix_timestamp: float = Field(
        description="Unix timestamp (seconds or milliseconds since epoch) to convert"
    )


class UnixToDatetimeObservation(Observation):
    pass


class UnixToDatetimeExecutor(ToolExecutor[UnixToDatetimeAction, UnixToDatetimeObservation]):
    def __call__(self, action: UnixToDatetimeAction, conversation=None) -> UnixToDatetimeObservation:
        result = _unix_to_datetime(action.unix_timestamp)
        return UnixToDatetimeObservation.from_text(_format_result(result))


class UnixToDatetimeTool(ToolDefinition[UnixToDatetimeAction, UnixToDatetimeObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UnixToDatetimeTool"]:
        return [cls(
            description=(
                "Convert a Unix timestamp (seconds or milliseconds since epoch) into a structured datetime representation. "
                'Returns the ISO 8601 format, human-readable date and time, day of week, and relative description '
                '(e.g., "3 days ago", "in 2 weeks"). '
                "Auto-detects seconds vs milliseconds based on magnitude (timestamps > 10^12 treated as milliseconds)."
            ),
            action_type=UnixToDatetimeAction,
            observation_type=UnixToDatetimeObservation,
            executor=UnixToDatetimeExecutor(),
        )]


register_tool("UnixToDatetimeTool", UnixToDatetimeTool)


def get_tools() -> List[Tool]:
    return [Tool(name="UnixToDatetimeTool")]


def get_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "unix_to_datetime": {
            "name": "unix_to_datetime",
            "description": (
                "Convert a Unix timestamp (seconds or milliseconds since epoch) into a structured datetime representation. "
                'Returns the ISO 8601 format, human-readable date and time, day of week, and relative description '
                '(e.g., "3 days ago", "in 2 weeks"). '
                "Auto-detects seconds vs milliseconds based on magnitude (timestamps > 10^12 treated as milliseconds)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "unix_timestamp": {
                        "type": "number",
                        "description": "Unix timestamp (seconds or milliseconds since epoch) to convert",
                    },
                },
                "required": ["unix_timestamp"],
            },
        },
    }


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "unix_to_datetime":
        result = _unix_to_datetime(args["unix_timestamp"])
        return _format_result(result)
    return f"Unknown temporal_from_unix tool: {name}"
