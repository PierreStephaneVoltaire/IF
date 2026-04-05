"""Discovery tools for the external tool plugin registry.

Provides:
- discover_tools: Lists all registered external tools
- use_tool: Executes an external tool by name
"""
from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from typing import Any, Dict, List, Optional

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
# discover_tools
# =============================================================================

class DiscoverToolsAction(Action):
    pass


class DiscoverToolsObservation(TextObservation):
    pass


class DiscoverToolsExecutor(ToolExecutor[DiscoverToolsAction, DiscoverToolsObservation]):
    def __call__(self, action: DiscoverToolsAction, conversation=None) -> DiscoverToolsObservation:
        try:
            from agent.tool_registry import get_tool_registry
            registry = get_tool_registry()
            tools = registry.list_tools()
        except Exception as e:
            return DiscoverToolsObservation.from_text(f"Tool registry not available: {e}")

        if not tools:
            return DiscoverToolsObservation.from_text("No external tools currently registered.")

        lines = ["## External Tools\n"]
        for t in tools:
            lines.append(f"- **{t['name']}** (v{t['version']}, scope={t['scope']}, {t['tool_count']} tools)")
            lines.append(f"  {t['description']}")

        return DiscoverToolsObservation.from_text("\n".join(lines))


class DiscoverToolsTool(ToolDefinition[DiscoverToolsAction, DiscoverToolsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DiscoverToolsTool"]:
        return [cls(
            description=(
                "List all registered external tool plugins. "
                "Shows name, version, scope, and description for each plugin."
            ),
            action_type=DiscoverToolsAction,
            observation_type=DiscoverToolsObservation,
            executor=DiscoverToolsExecutor(),
        )]


register_tool("DiscoverToolsTool", DiscoverToolsTool)


# =============================================================================
# use_tool
# =============================================================================

class UseToolAction(Action):
    tool_name: str = Field(description="Snake-case name of the external tool to execute (e.g., 'health_get_program')")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments dict for the tool")


class UseToolObservation(TextObservation):
    pass


class UseToolExecutor(ToolExecutor[UseToolAction, UseToolObservation]):
    def __call__(self, action: UseToolAction, conversation=None) -> UseToolObservation:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        async def _execute():
            from agent.tool_registry import get_tool_registry
            registry = get_tool_registry()
            return await registry.execute_tool(action.tool_name, action.arguments)

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _execute()).result()
        else:
            result = asyncio.run(_execute())

        return UseToolObservation.from_text(result)


class UseToolTool(ToolDefinition[UseToolAction, UseToolObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UseToolTool"]:
        return [cls(
            description=(
                "Execute an external tool by its snake-case name. "
                "Use discover_tools first to see available tools. "
                "Pass the tool name and an arguments dict."
            ),
            action_type=UseToolAction,
            observation_type=UseToolObservation,
            executor=UseToolExecutor(),
        )]


register_tool("UseToolTool", UseToolTool)


# =============================================================================
# Getter
# =============================================================================

def get_discovery_tools() -> List[Tool]:
    return [
        Tool(name="DiscoverToolsTool"),
        Tool(name="UseToolTool"),
    ]
