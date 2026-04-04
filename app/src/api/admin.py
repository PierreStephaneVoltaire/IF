"""Admin API endpoints for runtime management."""
from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reload-tools")
async def reload_tools() -> Dict[str, str]:
    """Reload all external tool plugins from disk.

    Re-scans the tools directory, installs any new dependencies,
    re-imports modules, and re-indexes all plugins.

    Returns per-tool status: "reloaded", "removed", or "failed: <reason>".
    """
    try:
        from agent.tool_registry import get_tool_registry
        registry = get_tool_registry()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        statuses = registry.reload()
        logger.info(f"Tool reload: {statuses}")
        return statuses
    except Exception as e:
        logger.error(f"Tool reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {e}")
