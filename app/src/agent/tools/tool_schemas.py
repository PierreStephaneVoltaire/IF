"""OpenRouter-compatible function schemas for domain tools.

Delegates to the external tool registry for health, finance, diary, and proposal
tool schemas. Keeps system tool schemas (terminal_execute, file tools, search tools)
hardcoded.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from orchestrator.executor import TERMINAL_EXECUTE_SCHEMA

logger = logging.getLogger(__name__)


def get_schemas_for_specialist(tool_names: List[str]) -> List[Dict[str, Any]]:
    """Resolve a specialist's tool names to OpenRouter function schemas.

    Always includes terminal_execute in addition to the specialist's
    configured tools. Falls through to the external tool registry for
    any names not found in the system schemas.

    Args:
        tool_names: Tool names from specialist config

    Returns:
        List of OpenRouter-compatible function schemas
    """
    schemas = [TERMINAL_EXECUTE_SCHEMA]  # All specialists get terminal access

    try:
        from agent.tool_registry import get_tool_registry
        registry = get_tool_registry()
        for name in tool_names:
            if name == "terminal_execute":
                continue
            schema = registry.get_schema(name)
            if schema:
                schemas.append(schema)
            else:
                logger.debug(f"[ToolSchemas] Unknown tool '{name}' for specialist, skipping")
        return schemas
    except Exception:
        # Registry not available — fall back to no domain schemas
        logger.debug("[ToolSchemas] Tool registry not available, skipping domain schemas")
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
