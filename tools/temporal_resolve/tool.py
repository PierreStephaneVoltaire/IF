"""Temporal resolve tool plugin — parse natural language date/time phrases into concrete dates.

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


def _resolve_phrase(phrase: str) -> Dict[str, Any]:
    import dateparser

    parsed = dateparser.parse(
        phrase,
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": datetime.now(timezone.utc),
        },
    )
    if parsed is None:
        return {"error": f"Could not parse phrase: {phrase!r}", "phrase": phrase}

    now = datetime.now(timezone.utc)
    is_past = parsed < now
    diff = parsed - now if not is_past else now - parsed
    days = abs(diff.days)

    if days == 0:
        relative = "today"
    elif days == 1:
        relative = "tomorrow" if not is_past else "yesterday"
    elif days < 7:
        relative = f"in {days} days" if not is_past else f"{days} days ago"
    elif days < 30:
        weeks = days // 7
        relative = f"in {weeks} week{'s' if weeks != 1 else ''}" if not is_past else f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif days < 365:
        months = days // 30
        relative = f"in ~{months} month{'s' if months != 1 else ''}" if not is_past else f"~{months} month{'s' if months != 1 else ''} ago"
    else:
        years = days // 365
        relative = f"in ~{years} year{'s' if years != 1 else ''}" if not is_past else f"~{years} year{'s' if years != 1 else ''} ago"

    return {
        "phrase": phrase,
        "date": parsed.strftime("%Y-%m-%d"),
        "day_of_week": parsed.strftime("%A"),
        "relative_description": relative,
        "is_past": is_past,
    }


class ResolveTemporalPhraseAction(Action):
    phrase: str = Field(
        description=(
            "A natural language temporal expression to resolve. "
            'Examples: "next monday", "in 3 days", "2 weeks from friday", '
            '"end of month", "march 15", "2025-12-25", "next monday at 3pm"'
        )
    )


class ResolveTemporalPhraseObservation(Observation):
    pass


class ResolveTemporalPhraseExecutor(ToolExecutor[ResolveTemporalPhraseAction, ResolveTemporalPhraseObservation]):
    def __call__(self, action: ResolveTemporalPhraseAction, conversation=None) -> ResolveTemporalPhraseObservation:
        result = _resolve_phrase(action.phrase)
        return ResolveTemporalPhraseObservation.from_text(_format_result(result))


class ResolveTemporalPhraseTool(ToolDefinition[ResolveTemporalPhraseAction, ResolveTemporalPhraseObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["ResolveTemporalPhraseTool"]:
        return [cls(
            description=(
                "Parse human-readable temporal expressions and return structured date/time information. "
                'Handles relative phrases ("next monday", "in 3 days", "2 weeks from friday", "end of month"), '
                'absolute phrases ("march 15", "2025-12-25"), and combined expressions ("next monday at 3pm"). '
                "Returns the resolved date, day of week, and a human-readable description of how far in the future/past it is."
            ),
            action_type=ResolveTemporalPhraseAction,
            observation_type=ResolveTemporalPhraseObservation,
            executor=ResolveTemporalPhraseExecutor(),
        )]


register_tool("ResolveTemporalPhraseTool", ResolveTemporalPhraseTool)


def get_tools() -> List[Tool]:
    return [Tool(name="ResolveTemporalPhraseTool")]


def get_schemas() -> Dict[str, Dict[str, Any]]:
    return {
        "resolve_temporal_phrase": {
            "name": "resolve_temporal_phrase",
            "description": (
                "Parse human-readable temporal expressions and return structured date/time information. "
                'Handles relative phrases ("next monday", "in 3 days", "2 weeks from friday", "end of month"), '
                'absolute phrases ("march 15", "2025-12-25"), and combined expressions ("next monday at 3pm"). '
                "Returns the resolved date, day of week, and a human-readable description of how far in the future/past it is."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": (
                            "A natural language temporal expression to resolve. "
                            'Examples: "next monday", "in 3 days", "march 15 2025", "next monday at 3pm"'
                        ),
                    },
                },
                "required": ["phrase"],
            },
        },
    }


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "resolve_temporal_phrase":
        result = _resolve_phrase(args["phrase"])
        return _format_result(result)
    return f"Unknown temporal_resolve tool: {name}"
