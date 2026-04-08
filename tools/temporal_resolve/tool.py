"""Temporal resolve tool plugin — parse natural language date/time phrases into concrete dates."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict


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


async def execute(name: str, args: Dict[str, Any]) -> str:
    if name == "resolve_temporal_phrase":
        result = _resolve_phrase(args["phrase"])
        return _format_result(result)
    return f"Unknown temporal_resolve tool: {name}"
