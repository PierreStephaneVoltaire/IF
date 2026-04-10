"""Health analytics and export API endpoints.

GET /v1/health/analysis/weekly  — structured weekly analysis JSON
GET /v1/health/export/xlsx      — download program as Excel
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
        result = weekly_analysis(program, sessions, weeks=weeks, block=block)
        return result
    except Exception as e:
        logger.error(f"[HealthAnalytics] weekly_analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
