"""Health module tool functions.

Nine tool functions for health/powerlifting operations. Each is a plain async def
that returns a dict. No side effects outside of DynamoDB writes.

Uses dependency injection via init_tools() to receive the ProgramStore instance.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from health.program_store import ProgramStore, ProgramNotFoundError

logger = logging.getLogger(__name__)


# Module-level store instance (set via init_tools)
_store: Optional[ProgramStore] = None
_rag: Optional[Any] = None  # HealthDocsRAG type, avoid circular import


def init_tools(store: ProgramStore, rag: Any = None) -> None:
    """Initialize tools with store instance.
    
    Called at startup from main.py after ProgramStore is created.
    
    Args:
        store: ProgramStore instance for program operations
        rag: Optional HealthDocsRAG instance for document search
    """
    global _store, _rag
    _store = store
    _rag = rag
    logger.info("[HealthTools] Initialized with store and rag")


def _get_store() -> ProgramStore:
    """Get the store instance, raising if not initialized."""
    if _store is None:
        raise RuntimeError("Health tools not initialized. Call init_tools() first.")
    return _store


# =============================================================================
# Tool Functions
# =============================================================================

async def health_get_program() -> dict:
    """Get the full training program.
    
    Returns:
        Full program dict from cache or DynamoDB
        
    Raises:
        ProgramNotFoundError: If no program exists
        RuntimeError: If store not initialized or DynamoDB fails
    """
    store = _get_store()
    return await store.get_program()


async def health_comp_countdown() -> dict:
    """Calculate competition countdown metrics.
    
    Uses program.meta.comp_date and current date to calculate:
    - Days and weeks until competition
    - Current training week and phase
    - Whether currently in a break period
    - Number of remaining sessions
    
    Returns:
        {
            "days_to_comp": 98,
            "weeks_to_comp": 14,
            "current_week": 2,
            "current_phase": "Hypertrophy",
            "in_break": false,
            "next_break": null,
            "sessions_remaining": 52
        }
        
    Raises:
        ProgramNotFoundError: If no program exists
        RuntimeError: If store not initialized or DynamoDB fails
    """
    store = _get_store()
    program = await store.get_program()
    
    meta = program.get("meta", {})
    comp_date_str = meta.get("comp_date")
    
    today = date.today()
    
    # Calculate days/weeks to comp
    if comp_date_str:
        try:
            comp_date = datetime.strptime(comp_date_str, "%Y-%m-%d").date()
            days_to_comp = (comp_date - today).days
            weeks_to_comp = days_to_comp // 7
        except ValueError:
            days_to_comp = None
            weeks_to_comp = None
    else:
        days_to_comp = None
        weeks_to_comp = None
    
    # Calculate current week from program start
    program_start_str = meta.get("program_start")
    if program_start_str:
        try:
            program_start = datetime.strptime(program_start_str, "%Y-%m-%d").date()
            days_since_start = (today - program_start).days
            current_week = max(1, (days_since_start // 7) + 1)
        except ValueError:
            current_week = 1
    else:
        current_week = 1
    
    # Find current phase
    phases = program.get("phases", [])
    current_phase = None
    for phase in phases:
        start_week = phase.get("start_week", 0)
        end_week = phase.get("end_week", 0)
        if start_week <= current_week <= end_week:
            current_phase = phase.get("name", "Unknown")
            break
    
    # Check if in break period
    breaks = program.get("breaks", [])
    in_break = False
    next_break = None
    
    for break_period in breaks:
        try:
            break_start = datetime.strptime(
                break_period.get("start", ""), "%Y-%m-%d"
            ).date()
            break_end = datetime.strptime(
                break_period.get("end", ""), "%Y-%m-%d"
            ).date()
            
            if break_start <= today <= break_end:
                in_break = True
                break
            
            # Track next break
            if break_start > today:
                if next_break is None or break_start < datetime.strptime(
                    next_break, "%Y-%m-%d"
                ).date():
                    next_break = break_period.get("start")
        except (ValueError, KeyError):
            continue
    
    # Count remaining sessions
    sessions = program.get("sessions", [])
    sessions_remaining = sum(
        1 for s in sessions
        if not s.get("completed", False)
    )
    
    return {
        "days_to_comp": days_to_comp,
        "weeks_to_comp": weeks_to_comp,
        "current_week": current_week,
        "current_phase": current_phase,
        "in_break": in_break,
        "next_break": next_break,
        "sessions_remaining": sessions_remaining,
    }


async def health_update_session(date_str: str, patch: dict) -> dict:
    """Update a session by date with the given patch.
    
    Validates date format and patch keys before applying.
    
    Args:
        date_str: ISO8601 date string (YYYY-MM-DD)
        patch: Dict with session fields to update
        
    Allowed patch keys:
        - completed: bool
        - session_rpe: float
        - body_weight_kg: float
        - session_notes: str
        - exercises: list
        
    Returns:
        Updated session dict (not full program)
        
    Raises:
        ValueError: If date format invalid, patch keys invalid, or session not found
        RuntimeError: If store not initialized or DynamoDB fails
    """
    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")
    
    # Validate patch keys
    allowed_keys = {"completed", "session_rpe", "body_weight_kg", "session_notes", "exercises"}
    unknown_keys = set(patch.keys()) - allowed_keys
    if unknown_keys:
        raise ValueError(f"Unknown patch keys: {unknown_keys}. Allowed: {allowed_keys}")
    
    store = _get_store()
    updated_program = await store.update_session(date_str, patch)
    
    # Find and return the updated session
    sessions = updated_program.get("sessions", [])
    for session in sessions:
        if session.get("date") == date_str:
            return session
    
    # Should not reach here if update_session worked correctly
    raise RuntimeError(f"Session update succeeded but session not found: {date_str}")


async def health_new_version(change_reason: str, patches: list[dict]) -> dict:
    """Create a new major version of the program.
    
    Args:
        change_reason: Human-readable reason for the version change
        patches: List of patches, each with "path" and "value" keys
                Example: {"path": "sessions[0].exercises[1].kg", "value": 180}
        
    Returns:
        {"new_version": int, "change_reason": str}
        
    Raises:
        ValueError: If patch format invalid
        RuntimeError: If store not initialized or DynamoDB fails
    """
    store = _get_store()
    updated_program = await store.new_version(patches, change_reason)
    
    version_label = updated_program.get("meta", {}).get("version_label", "unknown")
    
    return {
        "new_version": version_label,
        "change_reason": change_reason,
    }


def kg_to_lb(kg: float) -> dict:
    """Convert kilograms to pounds.
    
    Args:
        kg: Weight in kilograms
        
    Returns:
        {"kg": kg, "lb": rounded_pounds}
        
    Raises:
        ValueError: If kg <= 0
    """
    if kg <= 0:
        raise ValueError("kg must be positive")
    
    lb = round(kg * 2.20462, 1)
    return {"kg": kg, "lb": lb}


def lb_to_kg(lb: float) -> dict:
    """Convert pounds to kilograms.
    
    Args:
        lb: Weight in pounds
        
    Returns:
        {"lb": lb, "kg": rounded_kg}
        
    Raises:
        ValueError: If lb <= 0
    """
    if lb <= 0:
        raise ValueError("lb must be positive")
    
    kg = round(lb / 2.20462, 2)
    return {"lb": lb, "kg": kg}


def ipf_weight_classes(sex: str) -> dict:
    """Get IPF weight classes for the given sex.
    
    Static data - no network calls.
    
    Args:
        sex: "M" or "F"
        
    Returns:
        {
            "sex": "M",
            "classes_kg": [59, 66, 74, 83, 93, 105, 120, "120+"],
            "operator_class_kg": 83  # From program or null
        }
        
    Raises:
        ValueError: If sex not in ["M", "F"]
    """
    if sex not in ["M", "F"]:
        raise ValueError(f"Invalid sex: {sex}. Must be 'M' or 'F'.")
    
    CLASSES = {
        "M": [59, 66, 74, 83, 93, 105, 120, "120+"],
        "F": [47, 52, 57, 63, 69, 76, 84, "84+"],
    }
    
    # Try to get operator's weight class from program
    operator_class_kg = None
    if _store is not None:
        try:
            # This is sync but we're in a sync function
            # The cache should be warm after startup
            import asyncio
            loop = asyncio.get_running_loop()
            # Create a task to get the program
            future = asyncio.ensure_future(_store.get_program())
            try:
                program = loop.run_until_complete(future)
                operator_class_kg = program.get("meta", {}).get("weight_class_kg")
            except:
                # Cache might not be warm, that's okay
                pass
        except RuntimeError:
            # No running loop, try to get from cache directly
            if _store._cache is not None:
                operator_class_kg = _store._cache.get("meta", {}).get("weight_class_kg")
    
    return {
        "sex": sex,
        "classes_kg": CLASSES[sex],
        "operator_class_kg": operator_class_kg,
    }


def pct_of_max(max_kg: float, pct: float) -> dict:
    """Calculate percentage of max weight.
    
    Args:
        max_kg: Maximum weight in kg
        pct: Percentage (0-150, not 0-1)
        
    Returns:
        {
            "max_kg": 185.0,
            "pct": 85.0,
            "raw_kg": 157.25,
            "rounded_2_5_kg": 157.5,
            "lb": 347.2
        }
        
    Raises:
        ValueError: If max_kg <= 0 or pct not in (0, 150]
    """
    if max_kg <= 0:
        raise ValueError("max_kg must be positive")
    if not (0 < pct <= 150):
        raise ValueError("pct must be in range (0, 150]")
    
    raw_kg = max_kg * (pct / 100)
    rounded_2_5_kg = round(raw_kg / 2.5) * 2.5
    lb = round(raw_kg * 2.20462, 1)
    
    return {
        "max_kg": max_kg,
        "pct": pct,
        "raw_kg": round(raw_kg, 2),
        "rounded_2_5_kg": rounded_2_5_kg,
        "lb": lb,
    }


async def calculate_attempts(
    lift: str,
    opener_kg: float,
    j1_override: float | None = None,
    j2_override: float | None = None,
    last_felt: str | None = None,
) -> dict:
    """Calculate competition attempts based on program preferences.
    
    Args:
        lift: "squat", "bench", or "deadlift"
        opener_kg: First attempt weight in kg
        j1_override: Override jump 1 from program prefs (optional)
        j2_override: Override jump 2 from program prefs (optional)
        last_felt: "hard" to halve j2 (optional)
        
    Returns:
        {
            "lift": "squat",
            "attempt_1_kg": 160.0,
            "attempt_2_kg": 180.0,
            "attempt_3_kg": 200.0,
            "jumps_used": {"j1": 20, "j2": 20},
            "warnings": ["Attempt 3 exceeds current max..."]
        }
        
    Raises:
        ValueError: If lift not in valid list
    """
    valid_lifts = ["squat", "bench", "deadlift"]
    if lift not in valid_lifts:
        raise ValueError(f"Invalid lift: {lift}. Must be one of {valid_lifts}")
    
    store = _get_store()
    program = await store.get_program()
    
    # Get default jumps from program prefs
    operator_prefs = program.get("operator_prefs", {})
    attempt_jumps = operator_prefs.get("attempt_jumps", {})
    lift_jumps = attempt_jumps.get(lift, {"j1": 10, "j2": 10})
    
    j1 = j1_override if j1_override is not None else lift_jumps.get("j1", 10)
    j2 = j2_override if j2_override is not None else lift_jumps.get("j2", 10)
    
    # Adjust j2 if last felt hard
    if last_felt == "hard":
        j2 = round(j2 / 2 / 2.5) * 2.5  # Halve and round to nearest 2.5
    
    # Calculate attempts
    attempt_1 = opener_kg
    attempt_2 = round((attempt_1 + j1) / 2.5) * 2.5
    attempt_3 = round((attempt_2 + j2) / 2.5) * 2.5
    
    # Get current max for validation
    current_maxes = program.get("current_maxes", {})
    current_max = current_maxes.get(lift)
    
    warnings = []
    
    # Warn if opener < 70% of max
    if current_max:
        min_opener = current_max * 0.7
        if opener_kg < min_opener:
            warnings.append(
                f"Opener {opener_kg}kg is below 70% of current max ({current_max}kg). "
                f"Consider an opener of at least {round(min_opener / 2.5) * 2.5}kg."
            )
        
        # Warn if attempt 3 exceeds max
        if attempt_3 > current_max:
            warnings.append(
                f"Attempt 3 ({attempt_3}kg) exceeds current max of {current_max}kg — "
                "confirm this is a target PR."
            )
    
    return {
        "lift": lift,
        "attempt_1_kg": attempt_1,
        "attempt_2_kg": attempt_2,
        "attempt_3_kg": attempt_3,
        "jumps_used": {"j1": j1, "j2": j2},
        "warnings": warnings,
    }


async def days_until(target_date: str, label: str = "target") -> dict:
    """Calculate days until a target date.
    
    Args:
        target_date: ISO8601 date string (YYYY-MM-DD)
        label: Human label for the milestone (e.g., "comp", "deload start")
        
    Returns:
        {
            "label": "comp",
            "target_date": "2026-06-14",
            "today": "2026-03-07",
            "days_remaining": 99,
            "weeks_remaining": 14,
            "days_elapsed_since": null,
            "is_past": false
        }
        
    Raises:
        ValueError: If target_date format invalid
    """
    # Validate date format
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format: {target_date}. Expected YYYY-MM-DD.")
    
    today = date.today()
    today_str = today.isoformat()
    
    delta = (target - today).days
    
    if delta > 0:
        # Future date
        return {
            "label": label,
            "target_date": target_date,
            "today": today_str,
            "days_remaining": delta,
            "weeks_remaining": delta // 7,
            "days_elapsed_since": None,
            "is_past": False,
        }
    else:
        # Past date
        return {
            "label": label,
            "target_date": target_date,
            "today": today_str,
            "days_remaining": 0,
            "weeks_remaining": 0,
            "days_elapsed_since": abs(delta),
            "is_past": True,
        }


async def health_rag_search(query: str, n_results: int = 4) -> list[dict]:
    """Search health documents using semantic search.
    
    Thin wrapper over HealthDocsRAG.query().
    
    Args:
        query: Search query
        n_results: Number of results to return (default 4)
        
    Returns:
        [{"text": str, "source": str, "score": float}, ...]
        
    Raises:
        RuntimeError: If RAG not initialized or search fails
    """
    if _rag is None:
        raise RuntimeError("Health RAG not initialized. Call init_tools() with rag parameter.")
    
    return await _rag.query(query, n_results=n_results)
