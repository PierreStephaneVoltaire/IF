"""OpenRouter-compatible function schemas for domain tools.

Delegates to the external tool registry for health, finance, diary, and proposal
tool schemas. Keeps system tool schemas (terminal_execute, get_current_date, file tools)
hardcoded.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from orchestrator.executor import TERMINAL_EXECUTE_SCHEMA

logger = logging.getLogger(__name__)

GET_CURRENT_DATE_SCHEMA = {
    "name": "get_current_date",
    "description": (
        "Get the current date and time from the server. "
        "Use this whenever you need to know today's date for scheduling, "
        "calculations, session lookups, or any temporal context."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

# System tool schemas that specialists can reference by snake_case name
_SYSTEM_TOOL_SCHEMAS: Dict[str, dict] = {
    "terminal_execute": TERMINAL_EXECUTE_SCHEMA,
    "get_current_date": GET_CURRENT_DATE_SCHEMA,
}


def get_schemas_for_specialist(tool_names: List[str]) -> List[Dict[str, Any]]:
    """Resolve a specialist's tool names to OpenRouter function schemas.

    Resolves system tools first, then falls through to the external tool
    registry for domain tools (health, finance, etc.).

    Args:
        tool_names: Tool names from specialist config

    Returns:
        List of OpenRouter-compatible function schemas
    """
    schemas: List[Dict[str, Any]] = []

    # Always include terminal_execute
    if "terminal_execute" not in tool_names:
        schemas.append(TERMINAL_EXECUTE_SCHEMA)

    for name in tool_names:
        # Check system tools first
        if name in _SYSTEM_TOOL_SCHEMAS:
            schemas.append(_SYSTEM_TOOL_SCHEMAS[name])
            continue

        # Fall through to external tool registry
        try:
            from agent.tool_registry import get_tool_registry
            registry = get_tool_registry()
            schema = registry.get_schema(name)
            if schema:
                schemas.append(schema)
            else:
                logger.debug(f"[ToolSchemas] Unknown tool '{name}' for specialist, skipping")
        except Exception:
            logger.debug(f"[ToolSchemas] Tool registry not available, skipping '{name}'")

    return schemas


async def execute_domain_tool(tool_name: str, args: Dict[str, Any]) -> str:
    """Execute a domain tool by name via the external tool registry.

    Args:
        tool_name: The tool name (e.g., "health_get_program")
        args: Parsed arguments dict

    Returns:
        Result string
    """
    try:
        from agent.tool_registry import get_tool_registry
        registry = get_tool_registry()
        return await registry.execute_tool(tool_name, args)
    except Exception as e:
        logger.error(f"[ToolSchemas] Error executing {tool_name}: {e}")
        return f"ERROR: {type(e).__name__}: {e}"
