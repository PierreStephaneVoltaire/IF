"""Temporal city time tool plugin — current date/time for major cities worldwide.

Exports:
    get_tools()       → SDK Tool objects (side effect: register_tool() calls)
    get_schemas()     → snake_case name → JSON schema
    execute(name, args) → async dispatcher for non-agentic path
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Sequence
from zoneinfo import ZoneInfo

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


CITY_TIMEZONES: Dict[str, str] = {
    # North America
    "new york": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "chicago": "America/Chicago",
    "houston": "America/Chicago",
    "phoenix": "America/Phoenix",
    "philadelphia": "America/New_York",
    "san antonio": "America/Chicago",
    "san diego": "America/Los_Angeles",
    "dallas": "America/Chicago",
    "san jose": "America/Los_Angeles",
    "toronto": "America/Toronto",
    "montreal": "America/Montreal",
    "vancouver": "America/Vancouver",
    "mexico city": "America/Mexico_City",
    # South America
    "sao paulo": "America/Sao_Paulo",
    "buenos aires": "America/Argentina/Buenos_Aires",
    "rio de janeiro": "America/Sao_Paulo",
    "santiago": "America/Santiago",
    "lima": "America/Lima",
    "bogota": "America/Bogota",
    # Europe
    "london": "Europe/London",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "madrid": "Europe/Madrid",
    "rome": "Europe/Rome",
    "amsterdam": "Europe/Amsterdam",
    "brussels": "Europe/Brussels",
    "vienna": "Europe/Vienna",
    "prague": "Europe/Prague",
    "warsaw": "Europe/Warsaw",
    "stockholm": "Europe/Stockholm",
    "oslo": "Europe/Oslo",
    "copenhagen": "Europe/Copenhagen",
    "helsinki": "Europe/Helsinki",
    "dublin": "Europe/Dublin",
    "lisbon": "Europe/Lisbon",
    "athens": "Europe/Athens",
    "zurich": "Europe/Zurich",
    # Asia
    "tokyo": "Asia/Tokyo",
    "seoul": "Asia/Seoul",
    "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai",
    "hong kong": "Asia/Hong_Kong",
    "singapore": "Asia/Singapore",
    "bangkok": "Asia/Bangkok",
    "mumbai": "Asia/Kolkata",
    "dubai": "Asia/Dubai",
    "istanbul": "Europe/Istanbul",
    "jakarta": "Asia/Jakarta",
    "manila": "Asia/Manila",
    # Africa
    "cairo": "Africa/Cairo",
    "lagos": "Africa/Lagos",
    "johannesburg": "Africa/Johannesburg",
    "nairobi": "Africa/Nairobi",
    "casablanca": "Africa/Casablanca",
    # Oceania
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "auckland": "Pacific/Auckland",
}


def _get_city_time(city: str) -> Dict[str, Any]:
    normalized = city.strip().lower()
    tz_name = CITY_TIMEZONES.get(normalized)
    if not tz_name:
        return {
            "error": f"City '{city}' not recognized.",
            "supported_cities": sorted(CITY_TIMEZONES.keys()),
        }

    now = datetime.now(ZoneInfo(tz_name))
    utc_offset = now.strftime("%z")
    formatted_offset = f"{utc_offset[:3]}:{utc_offset[3:]}"

    return {
        "city": normalized.title(),
        "timezone": tz_name,
        "datetime": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "utc_offset": formatted_offset,
        "day_of_week": now.strftime("%A"),
    }


class GetCityTimeAction(Action):
    city: str = Field(
        description="City name to get the current time for (e.g. 'Tokyo', 'new york', 'London')"
    )


class GetCityTimeObservation(Observation):
    pass


class GetCityTimeExecutor(ToolExecutor[GetCityTimeAction, GetCityTimeObservation]):
    def __call__(self, action: GetCityTimeAction, conversation=None) -> GetCityTimeObservation:
        result = _get_city_time(action.city)
        return GetCityTimeObservation.from_text(_format_result(result))


class GetCityTimeTool(ToolDefinition[GetCityTimeAction, GetCityTimeObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["GetCityTimeTool"]:
        return [cls(
            description=(
                "Return the current local time, date, timezone identifier, and UTC offset for a given city. "
                "Supports ~50 major cities worldwide. If the city isn't recognized, returns a list of supported cities. "
                "Useful for scheduling across time zones, checking business hours, or coordinating with people in other locations."
            ),
            action_type=GetCityTimeAction,
            observation_type=GetCityTimeObservation,
            executor=GetCityTimeExecutor(),
        )]


register_tool("GetCityTimeTool", GetCityTimeTool)


def get_tools() -> List[Tool]:
    return [Tool(name="GetCityTimeTool")]


def get_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "get_city_time": {
            "name": "get_city_time",
            "description": (
                "Return the current local time, date, timezone identifier, and UTC offset for a given city. "
                "Supports ~50 major cities worldwide. If the city isn't recognized, returns a list of supported cities. "
                "Useful for scheduling across time zones, checking business hours, or coordinating with people in other locations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name to get the current time for (e.g. 'Tokyo', 'new york', 'London')",
                    },
                },
                "required": ["city"],
            },
        },
    }


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "get_city_time":
        result = _get_city_time(args["city"])
        return _format_result(result)
    return f"Unknown temporal_city_time tool: {name}"
