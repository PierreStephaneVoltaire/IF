"""Temporal timezone tool plugin — convert datetime between IANA timezones.

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


def _convert_timezone(datetime_str: str, from_tz: str, to_tz: str) -> Dict[str, Any]:
    import dateparser
    from zoneinfo import ZoneInfo

    parsed = dateparser.parse(datetime_str)
    if parsed is None:
        return {"error": f"Could not parse datetime: {datetime_str!r}"}

    try:
        from_zone = ZoneInfo(from_tz)
        to_zone = ZoneInfo(to_tz)
    except Exception as e:
        return {"error": f"Timezone lookup failed: {e}"}

    try:
        localized = parsed.replace(tzinfo=from_zone)
        converted = localized.astimezone(to_zone)
    except Exception as e:
        return {"error": f"Conversion failed: {e}"}

    def _fmt_offset(dt):
        utc_off = dt.strftime("%z")
        return f"{utc_off[:3]}:{utc_off[3:]}"

    return {
        "original": str(localized),
        "converted": str(converted),
        "from_tz": from_tz,
        "to_tz": to_tz,
        "from_offset": _fmt_offset(localized),
        "to_offset": _fmt_offset(converted),
    }


class ConvertTimezoneAction(Action):
    datetime_str: str = Field(
        description="The datetime string to convert (ISO 8601, YYYY-MM-DD HH:MM, or common formats)"
    )
    from_tz: str = Field(
        description='IANA timezone to convert from (e.g., "America/New_York", "UTC")'
    )
    to_tz: str = Field(
        description='IANA timezone to convert to (e.g., "Europe/London", "Asia/Tokyo")'
    )


class ConvertTimezoneObservation(Observation):
    pass


class ConvertTimezoneExecutor(ToolExecutor[ConvertTimezoneAction, ConvertTimezoneObservation]):
    def __call__(self, action: ConvertTimezoneAction, conversation=None) -> ConvertTimezoneObservation:
        result = _convert_timezone(action.datetime_str, action.from_tz, action.to_tz)
        return ConvertTimezoneObservation.from_text(_format_result(result))


class ConvertTimezoneTool(ToolDefinition[ConvertTimezoneAction, ConvertTimezoneObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["ConvertTimezoneTool"]:
        return [cls(
            description=(
                "Convert any datetime string between two IANA timezones "
                '(e.g., "America/New_York", "Europe/London", "Asia/Tokyo"). '
                "Handles daylight saving time automatically via the IANA database. "
                "Accepts ISO 8601, YYYY-MM-DD HH:MM, or common formats. "
                "Returns both the converted datetime and the UTC offset for each timezone at that moment."
            ),
            action_type=ConvertTimezoneAction,
            observation_type=ConvertTimezoneObservation,
            executor=ConvertTimezoneExecutor(),
        )]


register_tool("ConvertTimezoneTool", ConvertTimezoneTool)


def get_tools() -> List[Tool]:
    return [Tool(name="ConvertTimezoneTool")]


def get_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "convert_timezone": {
            "name": "convert_timezone",
            "description": (
                "Convert any datetime string between two IANA timezones "
                '(e.g., "America/New_York", "Europe/London", "Asia/Tokyo"). '
                "Handles daylight saving time automatically via the IANA database. "
                "Accepts ISO 8601, YYYY-MM-DD HH:MM, or common formats. "
                "Returns both the converted datetime and the UTC offset for each timezone at that moment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime_str": {
                        "type": "string",
                        "description": "The datetime string to convert (ISO 8601, YYYY-MM-DD HH:MM, or common formats)",
                    },
                    "from_tz": {
                        "type": "string",
                        "description": 'IANA timezone to convert from (e.g., "America/New_York", "UTC")',
                    },
                    "to_tz": {
                        "type": "string",
                        "description": 'IANA timezone to convert to (e.g., "Europe/London", "Asia/Tokyo")',
                    },
                },
                "required": ["datetime_str", "from_tz", "to_tz"],
            },
        },
    }


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "convert_timezone":
        result = _convert_timezone(args["datetime_str"], args["from_tz"], args["to_tz"])
        return _format_result(result)
    return f"Unknown temporal_timezone tool: {name}"
