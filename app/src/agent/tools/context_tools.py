"""Context tools for signal retrieval and financial context.

Provides tools for:
- get_signals(): Retrieve current mental health/training signals (for auto-injection)
- get_financial_context(): Retrieve full financial profile
- get_context_snapshot(): Combined context from all domains

These tools follow the OpenHands SDK pattern (Action/Observation/Executor/ToolDefinition).
"""
from __future__ import annotations
import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)


# =============================================================================
# Helper functions to run async operations in sync context
# =============================================================================

def _run_async(coro):
    """Run an async coroutine in a sync context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're in an async context, run in a new thread
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
# Core async functions for data retrieval
# =============================================================================

async def _get_diary_signals(user_pk: str) -> Optional[Dict[str, Any]]:
    """Retrieve the latest diary signal from if-diary-signals table."""
    import boto3
    from config import IF_DIARY_SIGNALS_TABLE_NAME, AWS_REGION

    try:
        table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(IF_DIARY_SIGNALS_TABLE_NAME)
        response = table.get_item(Key={"pk": user_pk, "sk": "signal#latest"})
        return response.get("Item")
    except Exception as e:
        logger.debug(f"[context_tools] Failed to get diary signals: {e}")
        return None


async def _get_health_status(user_pk: str) -> Optional[Dict[str, Any]]:
    """Retrieve health/training status from if-health table."""
    import boto3
    from config import IF_HEALTH_TABLE_NAME, AWS_REGION, HEALTH_PROGRAM_PK

    try:
        # Use the configured health PK, not the passed user_pk
        health_pk = HEALTH_PROGRAM_PK
        table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(IF_HEALTH_TABLE_NAME)

        # Get pointer to current program
        pointer = table.get_item(Key={"pk": health_pk, "sk": "program#current"})
        if "Item" not in pointer:
            return None

        ref_sk = pointer["Item"].get("ref_sk")
        if not ref_sk:
            return None

        # Get the actual program
        program = table.get_item(Key={"pk": health_pk, "sk": ref_sk})
        if "Item" not in program:
            return None

        prog = program["Item"]
        meta = prog.get("meta", {})

        return {
            "training_status": "active",  # Could compute from sessions
            "current_week": meta.get("program_start"),
            "target_comp": meta.get("comp_date"),
            "weight_class_kg": meta.get("weight_class_kg"),
        }
    except Exception as e:
        logger.debug(f"[context_tools] Failed to get health status: {e}")
        return None


async def _get_finance_profile(user_pk: str) -> Optional[Dict[str, Any]]:
    """Retrieve full financial profile from if-finance table."""
    import boto3
    from config import IF_FINANCE_TABLE_NAME, AWS_REGION

    try:
        table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(IF_FINANCE_TABLE_NAME)

        # Get pointer to current version
        pointer = table.get_item(Key={"pk": user_pk, "sk": "finance#current"})
        if "Item" not in pointer:
            return None

        ref_sk = pointer["Item"].get("ref_sk")
        if not ref_sk:
            return None

        # Get the actual profile
        profile = table.get_item(Key={"pk": user_pk, "sk": ref_sk})
        if "Item" not in profile:
            return None

        return profile["Item"]
    except Exception as e:
        logger.debug(f"[context_tools] Failed to get finance profile: {e}")
        return None


# =============================================================================
# get_signals - For auto-injection into system prompt
# =============================================================================

async def get_signals(user_pk: str = "operator") -> Dict[str, Any]:
    """Get current signals for context injection.

    Combines diary signals + health status into a unified signal object.
    This is called automatically by completions.py for every request.

    Returns:
        Dict with mental health score, trend, life_load, social_battery, training_status
    """
    # Fetch in parallel
    diary_task = _get_diary_signals(user_pk)
    health_task = _get_health_status(user_pk)

    diary_signals, health_status = await asyncio.gather(diary_task, health_task)

    result = {
        "mental_health_score": None,
        "trend": None,
        "themes": [],
        "life_load": None,
        "social_battery": None,
        "training_status": None,
        "life_chapter": None,
    }

    # Merge diary signals
    if diary_signals:
        result["mental_health_score"] = diary_signals.get("score")
        result["trend"] = diary_signals.get("trend")
        result["themes"] = diary_signals.get("themes", [])
        result["life_load"] = diary_signals.get("life_load")
        result["social_battery"] = diary_signals.get("social_battery")
        # The note field is NOT included - it's for agent only, not user

    # Merge health status
    if health_status:
        result["training_status"] = health_status.get("training_status")
        result["life_chapter"] = "training" if health_status.get("training_status") == "active" else None

    return result


def get_signals_sync(user_pk: str = "operator") -> Dict[str, Any]:
    """Synchronous wrapper for get_signals() for use in completions.py."""
    return _run_async(get_signals(user_pk))


class GetSignalsAction(Action):
    user_pk: str = Field(default="operator", description="User partition key")


class GetSignalsObservation(Observation):
    pass


class GetSignalsExecutor(ToolExecutor[GetSignalsAction, GetSignalsObservation]):
    def __call__(self, action: GetSignalsAction, conversation=None) -> GetSignalsObservation:
        result = _run_async(get_signals(action.user_pk))
        return GetSignalsObservation.from_text(_format_result(result))


class GetSignalsTool(ToolDefinition[GetSignalsAction, GetSignalsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["GetSignalsTool"]:
        return [cls(
            description=(
                "Get current mental health and life signals. "
                "Returns score (0-10), trend, themes, life_load, social_battery, and training status."
            ),
            action_type=GetSignalsAction,
            observation_type=GetSignalsObservation,
            executor=GetSignalsExecutor(),
        )]


# =============================================================================
# get_financial_context - For money/career/goals queries
# =============================================================================

async def get_financial_context(user_pk: str = "operator") -> Dict[str, Any]:
    """Get full financial context for money/career/goals queries.

    Returns the complete versioned finance profile including:
    - Profile (age, employment, income)
    - Goals (short/medium/long term)
    - Risk profile
    - Net worth snapshot
    - Accounts (banking, credit, loans)
    - Investment accounts
    - Monthly cashflow
    - Tax situation
    - Agent context (known biases, recurring questions)
    """
    profile = await _get_finance_profile(user_pk)
    if not profile:
        return {"error": "No financial profile found. Run seed_finance.sh first."}
    return profile


class GetFinancialContextAction(Action):
    user_pk: str = Field(default="operator", description="User partition key")


class GetFinancialContextObservation(Observation):
    pass


class GetFinancialContextExecutor(ToolExecutor[GetFinancialContextAction, GetFinancialContextObservation]):
    def __call__(self, action: GetFinancialContextAction, conversation=None) -> GetFinancialContextObservation:
        result = _run_async(get_financial_context(action.user_pk))
        return GetFinancialContextObservation.from_text(_format_result(result))


class GetFinancialContextTool(ToolDefinition[GetFinancialContextAction, GetFinancialContextObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["GetFinancialContextTool"]:
        return [cls(
            description=(
                "Get the user's full financial context. "
                "Use for questions about money, career, investments, budgeting, or financial goals."
            ),
            action_type=GetFinancialContextAction,
            observation_type=GetFinancialContextObservation,
            executor=GetFinancialContextExecutor(),
        )]


# =============================================================================
# get_context_snapshot - Combined context for cross-domain questions
# =============================================================================

async def get_context_snapshot(user_pk: str = "operator") -> Dict[str, Any]:
    """Get combined context from all domains (~5k tokens).

    Combines:
    - Diary signals (mental health state)
    - Health status (training program)
    - Financial profile

    Use for cross-domain questions like "what should I focus on this month?"
    """
    signals_task = get_signals(user_pk)
    finance_task = get_financial_context(user_pk)

    signals, finance = await asyncio.gather(signals_task, finance_task)

    return {
        "signals": signals,
        "finance": finance,
    }


class GetContextSnapshotAction(Action):
    user_pk: str = Field(default="operator", description="User partition key")


class GetContextSnapshotObservation(Observation):
    pass


class GetContextSnapshotExecutor(ToolExecutor[GetContextSnapshotAction, GetContextSnapshotObservation]):
    def __call__(self, action: GetContextSnapshotAction, conversation=None) -> GetContextSnapshotObservation:
        result = _run_async(get_context_snapshot(action.user_pk))
        return GetContextSnapshotObservation.from_text(_format_result(result))


class GetContextSnapshotTool(ToolDefinition[GetContextSnapshotAction, GetContextSnapshotObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["GetContextSnapshotTool"]:
        return [cls(
            description=(
                "Get a combined snapshot of all user context domains. "
                "Use for cross-domain questions like 'what should I focus on?' or holistic planning."
            ),
            action_type=GetContextSnapshotAction,
            observation_type=GetContextSnapshotObservation,
            executor=GetContextSnapshotExecutor(),
        )]


# =============================================================================
# get_current_date - Time server for current date/time
# =============================================================================

def get_current_date() -> Dict[str, Any]:
    """Get the current date and time from the server.

    Returns:
        Dict with date, time, day_of_week, iso8601, unix_timestamp
    """
    from datetime import date, datetime, timezone
    now = datetime.now(timezone.utc)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "iso8601": now.isoformat(),
        "unix_timestamp": int(now.timestamp()),
    }


class GetCurrentDateAction(Action):
    pass


class GetCurrentDateObservation(Observation):
    pass


class GetCurrentDateExecutor(ToolExecutor[GetCurrentDateAction, GetCurrentDateObservation]):
    def __call__(self, action: GetCurrentDateAction, conversation=None) -> GetCurrentDateObservation:
        result = get_current_date()
        return GetCurrentDateObservation.from_text(_format_result(result))


class GetCurrentDateTool(ToolDefinition[GetCurrentDateAction, GetCurrentDateObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["GetCurrentDateTool"]:
        return [cls(
            description=(
                "Get the current date and time from the server. "
                "Use this whenever you need to know today's date for scheduling, "
                "calculations, session lookups, or any temporal context."
            ),
            action_type=GetCurrentDateAction,
            observation_type=GetCurrentDateObservation,
            executor=GetCurrentDateExecutor(),
        )]


# =============================================================================
# Register all tools
# =============================================================================

register_tool("GetSignalsTool", GetSignalsTool)
register_tool("GetFinancialContextTool", GetFinancialContextTool)
register_tool("GetContextSnapshotTool", GetContextSnapshotTool)
register_tool("GetCurrentDateTool", GetCurrentDateTool)


# =============================================================================
# Getter function
# =============================================================================

def get_context_tools() -> List[Tool]:
    """Get all context tools for session initialization."""
    return [
        Tool(name="GetSignalsTool"),
        Tool(name="GetFinancialContextTool"),
        Tool(name="GetContextSnapshotTool"),
        Tool(name="GetCurrentDateTool"),
    ]
