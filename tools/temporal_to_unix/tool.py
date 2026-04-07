"""Temporal to-unix tool plugin — parse datetime string and return Unix timestamp.

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


def _datetime_to_unix(datetime_str: str) -> Dict[str, Any]:
    import dateparser

    parsed = dateparser.parse(datetime_str)
    if parsed is None:
        return {"error": f"Could not parse datetime string: {datetime_str!r}"}

    return {
        "unix_timestamp": int(parsed.timestamp()),
        "iso8601": parsed.isoformat(),
        "human_readable": parsed.strftime("%B %d, %Y at %I:%M %p"),
    }


class DatetimeToUnixAction(Action):
    datetime_str: str = Field(
        description=(
            "A datetime string to parse (ISO 8601, RFC 2822, common formats, "
            "or natural language like 'march 15 2025 3pm')"
        )
    )


class DatetimeToUnixObservation(Observation):
    pass


class DatetimeToUnixExecutor(ToolExecutor[DatetimeToUnixAction, DatetimeToUnixObservation]):
    def __call__(self, action: DatetimeToUnixAction, conversation=None) -> DatetimeToUnixObservation:
        result = _datetime_to_unix(action.datetime_str)
        return DatetimeToUnixObservation.from_text(_format_result(result))


class DatetimeToUnixTool(ToolDefinition[DatetimeToUnixAction, DatetimeToUnixObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DatetimeToUnixTool"]:
        return [cls(
            description=(
                'Parse any recognized datetime string (ISO 8601, RFC 2822, common formats, or natural language like "march 15 2025 3pm") '
                "and return the equivalent Unix timestamp (seconds since epoch). "
                "Also returns the parsed ISO 8601 representation and a human-readable rendering for verification."
            ),
            action_type=DatetimeToUnixAction,
            observation_type=DatetimeToUnixObservation,
            executor=DatetimeToUnixExecutor(),
        )]


register_tool("DatetimeToUnixTool", DatetimeToUnixTool)


def get_tools() -> List[Tool]:
    return [Tool(name="DatetimeToUnixTool")]


def get_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "datetime_to_unix": {
            "name": "datetime_to_unix",
            "description": (
                'Parse any recognized datetime string (ISO 8601, RFC 2822, common formats, or natural language like "march 15 2025 3pm") '
                "and return the equivalent Unix timestamp (seconds since epoch). "
                "Also returns the parsed ISO 8601 representation and a human-readable rendering for verification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {
                        "type": "string",
                        "description": (
                            "A datetime string to parse (ISO 8601, RFC 2822, common formats, "
                            "or natural language like 'march 15 2025 3pm')"
                        ),
                    },
                },
                "required": ["datetime_str"],
            },
        },
    }


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "datetime_to_unix":
        result = _datetime_to_unix(args["datetime_str"])
        return _format_result(result)
    return f"Unknown temporal_to_unix tool: {name}"
