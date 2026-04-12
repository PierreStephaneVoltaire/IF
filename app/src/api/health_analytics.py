"""Health analytics and export API endpoints.

GET /v1/health/analysis/weekly  — structured weekly analysis JSON
GET /v1/health/export/xlsx      — download program as Excel
POST /v1/health/fatigue-profile/estimate — AI fatigue profile estimation
"""
from __future__ import annotations

import logging
import os
import tempfile
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)


def _sanitize_decimals(obj):
    """Recursively convert Decimal to float/int in nested dicts and lists.

    DynamoDB returns Decimal for all numeric types via boto3.
    This ensures downstream code only deals with native Python types.
    """
    if isinstance(obj, Decimal):
        # If it's an integer value, return int; otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_decimals(v) for v in obj]
    return obj


def _get_glossary_sync(table_name: str) -> list[dict]:
    """Fetch glossary from DynamoDB (pk='operator', sk='glossary#v1')."""
    import boto3
    from config import IF_HEALTH_TABLE_NAME

    dynamodb = boto3.resource("dynamodb", region_name="ca-central-1")
    table = dynamodb.Table(table_name)
    resp = table.get_item(Key={"pk": "operator", "sk": "glossary#v1"})
    item = resp.get("Item")
    if not item:
        return []
    return _sanitize_decimals(item.get("exercises", []))


router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/analysis/weekly")
async def get_weekly_analysis(
    weeks: int = Query(default=1, ge=1, le=52),
    block: str = Query(default="current"),
):
    """Return structured weekly analysis JSON."""
    from health.program_store import ProgramStore
    from health.analytics import weekly_analysis
    from config import IF_HEALTH_TABLE_NAME

    try:
        store = ProgramStore(IF_HEALTH_TABLE_NAME)
        program = _sanitize_decimals(await store.get_program())
        sessions = program.get("sessions", [])
        glossary = _get_glossary_sync(IF_HEALTH_TABLE_NAME)
        result = weekly_analysis(program, sessions, weeks=weeks, block=block, glossary=glossary)
        return result
    except Exception as e:
        logger.error(f"[HealthAnalytics] weekly_analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/correlation")
async def get_correlation_report(
    weeks: int = Query(default=4, ge=4, le=52),
    block: str = Query(default="current"),
    refresh: bool = Query(default=False),
):
    """Return AI-powered exercise ROI correlation report, cached in DynamoDB.

    Cache key: corr_report#<window_start_monday>_<weeks>w
    The window_start is the Monday of the week that is `weeks` weeks ago.
    """
    from datetime import datetime, timedelta

    try:
        from health.program_store import ProgramStore
        from health.correlation_ai import generate_correlation_report
        from config import IF_HEALTH_TABLE_NAME
        import boto3
        # --- Compute window_start (normalize to Monday) ---
        today = datetime.utcnow().date()
        raw_cutoff = today - timedelta(weeks=weeks)
        # Round back to Monday of that week
        days_since_monday = raw_cutoff.weekday()  # 0=Mon
        window_start = raw_cutoff - timedelta(days=days_since_monday)
        window_start_str = window_start.isoformat()
        cache_sk = f"corr_report#{window_start_str}_{weeks}w"

        dynamodb = boto3.resource("dynamodb", region_name="ca-central-1")
        table = dynamodb.Table(IF_HEALTH_TABLE_NAME)

        # --- Check cache ---
        if not refresh:
            cached = table.get_item(Key={"pk": "operator", "sk": cache_sk}).get("Item")
            if cached and cached.get("report"):
                report = _sanitize_decimals(cached["report"])
                report["cached"] = True
                report["generated_at"] = cached.get("generated_at", "")
                report["window_start"] = window_start_str
                report["weeks"] = weeks
                return report

        # --- Generate fresh report ---
        store = ProgramStore(IF_HEALTH_TABLE_NAME)
        program = _sanitize_decimals(await store.get_program())
        sessions = program.get("sessions", [])
        lift_profiles = program.get("lift_profiles", [])

        report = await generate_correlation_report(
            sessions=sessions,
            lift_profiles=lift_profiles,
            weeks=weeks,
            window_start=window_start_str,
        )

        generated_at = datetime.utcnow().isoformat() + "Z"

        # --- Cache in DynamoDB ---
        table.put_item(Item={
            "pk": "operator",
            "sk": cache_sk,
            "report": report,
            "generated_at": generated_at,
            "window_start": window_start_str,
            "weeks": weeks,
        })

        report["cached"] = False
        report["generated_at"] = generated_at
        report["window_start"] = window_start_str
        report["weeks"] = weeks
        return report

    except Exception as e:
        logger.error(f"[HealthAnalytics] correlation_report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fatigue-profile/estimate")
async def estimate_fatigue_profile_endpoint(request: dict):
    """Estimate fatigue profile for an exercise using AI."""
    from health.fatigue_ai import estimate_fatigue_profile

    result = await estimate_fatigue_profile(request)
    return result


@router.get("/export/xlsx")
async def export_xlsx(background_tasks: BackgroundTasks):
    """Export the full program to an Excel (.xlsx) file."""
    from health.program_store import ProgramStore
    from health.export import build_program_xlsx
    from config import IF_HEALTH_TABLE_NAME

    try:
        store = ProgramStore(IF_HEALTH_TABLE_NAME)
        program = _sanitize_decimals(await store.get_program())

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        build_program_xlsx(program, path)

        background_tasks.add_task(os.unlink, path)

        return FileResponse(
            path=path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="program_history.xlsx",
            background=background_tasks,
        )
    except Exception as e:
        logger.error(f"[HealthAnalytics] export_xlsx failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
