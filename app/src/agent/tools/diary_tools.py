"""Diary tools for write-only entries and signal computation.

Provides tools for:
- write_diary_entry(): Write a diary entry with TTL
- compute_diary_signal(): Distill entries into a signal score

Design principles:
- Entries NEVER surface to user - write-only from portal
- TTL is the privacy model - 3-day expiry is architectural
- Signals are distilled, never include raw content
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Sequence

from pydantic import Field

from openhands.sdk import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor
from agent.tools.base import TextObservation

logger = logging.getLogger(__name__)


# =============================================================================
# Helper functions
# =============================================================================

def _run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def _format_result(result: Any) -> str:
    """Format a result (dict or str) as a string for Observation."""
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


# =============================================================================
# Core async functions
# =============================================================================

async def _get_table(table_name: str):
    """Get DynamoDB table reference."""
    import boto3
    from config import AWS_REGION
    return boto3.resource("dynamodb", region_name=AWS_REGION).Table(table_name)


async def write_diary_entry(content: str, user_pk: str = "operator") -> Dict[str, Any]:
    """Write a diary entry with TTL.

    Args:
        content: Raw rant/journal text
        user_pk: User partition key

    Returns:
        Dict with success status and entry metadata (NOT content)
    """
    from config import (
        IF_DIARY_ENTRIES_TABLE_NAME,
        DIARY_TTL_DAYS,
    )

    table = await _get_table(IF_DIARY_ENTRIES_TABLE_NAME)

    now = datetime.now(timezone.utc)
    sk = f"entry#{now.isoformat()}"

    # TTL = created_at + 3 days (in unix timestamp)
    expires_at = int((now + timedelta(days=DIARY_TTL_DAYS)).timestamp())

    item = {
        "pk": user_pk,
        "sk": sk,
        "content": content,  # NEVER returned to user
        "created_at": now.isoformat(),
        "expires_at": expires_at,
    }

    try:
        table.put_item(Item=item)
        logger.info(f"[diary] Wrote entry {sk} for {user_pk}, expires in {DIARY_TTL_DAYS} days")

        return {
            "success": True,
            "entry_sk": sk,
            "created_at": now.isoformat(),
            "expires_in_days": DIARY_TTL_DAYS,
            # NOTE: content is NEVER included in response
        }
    except Exception as e:
        logger.error(f"[diary] Failed to write entry: {e}")
        return {"success": False, "error": str(e)}


async def _get_unexpired_entries(user_pk: str) -> List[Dict[str, Any]]:
    """Get all non-expired diary entries for a user."""
    from config import IF_DIARY_ENTRIES_TABLE_NAME

    table = await _get_table(IF_DIARY_ENTRIES_TABLE_NAME)

    now_ts = int(datetime.now(timezone.utc).timestamp())

    try:
        response = table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
            FilterExpression("expires_at > :now"),
            ExpressionAttributeValues={
                ":pk": user_pk,
                ":prefix": "entry#",
                ":now": now_ts,
            },
        )
        return response.get("Items", [])
    except Exception as e:
        logger.error(f"[diary] Failed to query entries: {e}")
        return []


async def _get_previous_signal(user_pk: str) -> Optional[Dict[str, Any]]:
    """Get the previous signal for trend computation."""
    from config import IF_DIARY_SIGNALS_TABLE_NAME

    table = await _get_table(IF_DIARY_SIGNALS_TABLE_NAME)

    try:
        response = table.get_item(Key={"pk": user_pk, "sk": "signal#latest"})
        return response.get("Item")
    except Exception as e:
        logger.debug(f"[diary] No previous signal: {e}")
        return None


async def compute_diary_signal(user_pk: str = "operator") -> Dict[str, Any]:
    """Compute diary signal from unexpired entries.

    This function:
    1. Reads all non-expired entries
    2. Calls CONDENSER_MODEL with entries + previous signal
    3. Writes to if-diary-signals: signal#<now> + overwrites signal#latest
    4. NEVER includes raw entry content in output

    Returns:
        Dict with computed signal (distilled only, no raw content)
    """
    from config import (
        IF_DIARY_SIGNALS_TABLE_NAME,
        DIARY_SIGNAL_MODEL,
        OPENROUTER_API_KEY,
    )

    entries = await _get_unexpired_entries(user_pk)
    previous_signal = await _get_previous_signal(user_pk)

    if not entries:
        return {
            "success": False,
            "error": "No unexpired entries to analyze",
            "entry_count": 0,
        }

    # Prepare entry summaries (NOT raw content) for the model
    entry_summaries = [
        {
            "created_at": e["created_at"],
            "word_count": len(e.get("content", "").split()),
        }
        for e in entries
    ]

    # Build prompt for signal computation
    prompt = f"""Analyze the following diary entry metadata and previous signal to compute a new mental health signal.

PREVIOUS SIGNAL (if any):
{json.dumps(previous_signal, indent=2, default=str) if previous_signal else "None"}

CURRENT ENTRIES (metadata only, {len(entries)} entries):
{json.dumps(entry_summaries, indent=2)}

Based on the entry frequency, timing patterns, and previous signal trend, compute a new signal.

You MUST respond with ONLY a JSON object (no markdown, no explanation):
{{
  "score": <float 0-10, where 10 is best>,
  "trend": "<improving_fast|improving_slow|stable|declining_slow|declining_fast>",
  "themes": ["<theme1>", "<theme2>"],
  "life_load": "<low|moderate|high|overwhelming>",
  "social_battery": "<depleted|low|moderate|high|full>",
  "note": "<1-sentence summary WITHOUT referencing specific diary content>"
}}

CRITICAL: The note must describe the signal pattern WITHOUT revealing any diary content.
Example good note: "Slight decline in energy indicators with moderate life pressure"
Example bad note: "User mentioned work stress and sleep issues" (too specific)
"""

    # Call the model
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DIARY_SIGNAL_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        content = result["choices"][0]["message"]["content"]
        # Strip any markdown code blocks if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        signal = json.loads(content)

    except Exception as e:
        logger.error(f"[diary] Model call failed: {e}")
        return {"success": False, "error": f"Model call failed: {e}"}

    # Add metadata
    now = datetime.now(timezone.utc)
    signal["computed_at"] = now.isoformat()
    signal["entry_count_used"] = len(entries)

    # Write to DynamoDB
    table = await _get_table(IF_DIARY_SIGNALS_TABLE_NAME)

    try:
        # Write historical record
        history_sk = f"signal#{now.isoformat()}"
        table.put_item(Item={"pk": user_pk, "sk": history_sk, **signal})

        # Overwrite latest pointer
        table.put_item(Item={"pk": user_pk, "sk": "signal#latest", **signal})

        logger.info(f"[diary] Computed signal for {user_pk}: score={signal.get('score')}, trend={signal.get('trend')}")

        return {
            "success": True,
            "signal": signal,
            "entries_analyzed": len(entries),
        }

    except Exception as e:
        logger.error(f"[diary] Failed to write signal: {e}")
        return {"success": False, "error": f"Failed to write signal: {e}"}


# =============================================================================
# Tool Definitions
# =============================================================================

class WriteDiaryEntryAction(Action):
    content: str = Field(description="Raw journal/rant text to write")
    user_pk: str = Field(default="operator", description="User partition key")


class WriteDiaryEntryObservation(TextObservation):
    pass


class WriteDiaryEntryExecutor(ToolExecutor[WriteDiaryEntryAction, WriteDiaryEntryObservation]):
    def __call__(self, action: WriteDiaryEntryAction, conversation=None) -> WriteDiaryEntryObservation:
        result = _run_async(write_diary_entry(action.content, action.user_pk))
        return WriteDiaryEntryObservation.from_text(_format_result(result))


class WriteDiaryEntryTool(ToolDefinition[WriteDiaryEntryAction, WriteDiaryEntryObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["WriteDiaryEntryTool"]:
        return [cls(
            description=(
                "Write a diary entry. Use when the user wants to vent, journal, or record thoughts. "
                "Entries are private (never shown back to user) and auto-expire after 3 days."
            ),
            action_type=WriteDiaryEntryAction,
            observation_type=WriteDiaryEntryObservation,
            executor=WriteDiaryEntryExecutor(),
        )]


class ComputeDiarySignalAction(Action):
    user_pk: str = Field(default="operator", description="User partition key")


class ComputeDiarySignalObservation(TextObservation):
    pass


class ComputeDiarySignalExecutor(ToolExecutor[ComputeDiarySignalAction, ComputeDiarySignalObservation]):
    def __call__(self, action: ComputeDiarySignalAction, conversation=None) -> ComputeDiarySignalObservation:
        result = _run_async(compute_diary_signal(action.user_pk))
        return ComputeDiarySignalObservation.from_text(_format_result(result))


class ComputeDiarySignalTool(ToolDefinition[ComputeDiarySignalAction, ComputeDiarySignalObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["ComputeDiarySignalTool"]:
        return [cls(
            description=(
                "Compute a mental health signal from recent diary entries. "
                "Returns a score (0-10), trend, themes, life_load, and social_battery. "
                "Use when asked about overall mental state or to trigger signal update."
            ),
            action_type=ComputeDiarySignalAction,
            observation_type=ComputeDiarySignalObservation,
            executor=ComputeDiarySignalExecutor(),
        )]


# =============================================================================
# Register all tools
# =============================================================================

register_tool("WriteDiaryEntryTool", WriteDiaryEntryTool)
register_tool("ComputeDiarySignalTool", ComputeDiarySignalTool)


# =============================================================================
# Getter function
# =============================================================================

def get_diary_tools() -> List[Tool]:
    """Get all diary tools for session initialization."""
    return [
        Tool(name="WriteDiaryEntryTool"),
        Tool(name="ComputeDiarySignalTool"),
    ]
