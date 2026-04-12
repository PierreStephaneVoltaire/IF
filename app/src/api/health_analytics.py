"""Health export API endpoint.

DEPRECATED: The weekly analysis, correlation analysis, and fatigue profile estimation
endpoints have been moved to the tools/health plugin as proper SDK tools. They are now
available through the agent pipeline (specialist delegation) or direct tool invoke
(X-Direct-Tool-Invoke header). Only the xlsx export endpoint remains here because it
returns a binary file that doesn't fit the tool model.
"""
from __future__ import annotations

import logging
import os
import tempfile
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)


def _sanitize_decimals(obj):
    """Recursively convert Decimal to float/int in nested dicts and lists."""
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_decimals(v) for v in obj]
    return obj


router = APIRouter(prefix="/v1/health", tags=["health"])


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
