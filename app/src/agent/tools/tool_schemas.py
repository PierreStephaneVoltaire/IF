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

PLAN_APPEND_SCHEMA = {
    "name": "plan_append",
    "description": (
        "Append markdown content to a plan file under {sandbox}/plans/. "
        "Creates the file if missing. Use checkbox state convention: "
        "'- [ ]' open, '- [x]' done, '- [!]' needs adjustment, '- [?]' blocked. "
        "Subagents emit '- [!]' entries to signal the main agent that a step needs revisiting."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Plan file path relative to plans/ (e.g. 'supplement-bucket'). '.md' auto-appended."
            },
            "content": {"type": "string", "description": "Markdown content to append."},
            "prepend_timestamp": {
                "type": "boolean",
                "description": "If true (default), prefix the block with a UTC timestamp comment.",
                "default": True,
            },
        },
        "required": ["path", "content"],
    },
}

PLAN_READ_SCHEMA = {
    "name": "plan_read",
    "description": (
        "Read a plan file under {sandbox}/plans/. "
        "Returns content up to max_lines; longer files are truncated with an ellipsis marker."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Plan file path relative to plans/."},
            "max_lines": {
                "type": "integer",
                "description": "Maximum lines to return before truncating.",
                "default": 500,
            },
        },
        "required": ["path"],
    },
}

PLAN_LIST_SCHEMA = {
    "name": "plan_list",
    "description": "List all plan files under {sandbox}/plans/ with size and last-modified time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

PLAN_GREP_SCHEMA = {
    "name": "plan_grep",
    "description": (
        "Regex-search across plan files under {sandbox}/plans/. "
        "Returns matching lines as 'file:lineno:content'. "
        "Use pattern '- \\[!\\]' for adjustment flags or '- \\[ \\]' for open items."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for."},
            "path": {
                "type": "string",
                "description": "Optional: limit search to a single plan file. Empty = search all.",
                "default": "",
            },
        },
        "required": ["pattern"],
    },
}

# System tool schemas that specialists can reference by snake_case name
_SYSTEM_TOOL_SCHEMAS: Dict[str, dict] = {
    "terminal_execute": TERMINAL_EXECUTE_SCHEMA,
    "get_current_date": GET_CURRENT_DATE_SCHEMA,
    "plan_append": PLAN_APPEND_SCHEMA,
    "plan_read": PLAN_READ_SCHEMA,
    "plan_list": PLAN_LIST_SCHEMA,
    "plan_grep": PLAN_GREP_SCHEMA,
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
