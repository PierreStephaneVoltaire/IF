"""Capability gap tracking tools.

These tools allow the agent to log when it cannot fulfill a request,
building a pipeline for tool development suggestions.

Tools:
- log_capability_gap: Log when agent cannot fulfill a request
- list_capability_gaps: List all logged capability gaps by priority
"""
from __future__ import annotations
from typing import List, Optional, Sequence

from pydantic import Field

from openhands.sdk import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor

from memory.user_facts import (
    FactCategory,
    FactSource,
    get_user_fact_store
)

# Session context injection (set by session.py via user_facts module)
from agent.tools.user_facts import _current_cache_key


# ============================================================================
# Plain Python implementations
# ============================================================================

def _log_capability_gap(
    content: str,
    context: str,
    workaround: Optional[str] = None
) -> str:
    """Log a capability gap when agent cannot fulfill a request.
    
    Use this when you encounter a request you cannot fulfill natively —
    mathematical computation, email sending, calendar access, web browsing,
    real-time data beyond available MCP servers, or any other functional limitation.
    
    Args:
        content: What the agent cannot do (e.g., "Cannot send emails")
        context: The specific request that triggered this gap
        workaround: Any workaround suggested to the operator (optional)
        
    Returns:
        Confirmation with gap ID
    """
    try:
        store = get_user_fact_store()
        gap_id = store.log_capability_gap(
            content=content,
            context=context,
            cache_key=_current_cache_key,
            workaround=workaround,
        )
        return f"Capability gap logged (ID: {gap_id})"
    except Exception as e:
        return f"Error logging capability gap: {str(e)}"


def _list_capability_gaps(min_triggers: int = 1) -> str:
    """List all capability gaps ranked by priority.
    
    Shows gaps that have been triggered at least min_triggers times.
    
    Args:
        min_triggers: Minimum trigger count to include (default 1)
        
    Returns:
        Formatted list of capability gaps
    """
    try:
        store = get_user_fact_store()
        gaps = store.list_capability_gaps(min_triggers=min_triggers)
        
        if not gaps:
            return "No capability gaps logged."
        
        output = [f"Capability Gaps ({len(gaps)} total):", ""]
        for i, gap in enumerate(gaps, 1):
            output.append(f"{i}. [{gap.status}] {gap.content}")
            output.append(f"   Triggers: {gap.trigger_count}, Priority: {gap.priority_score:.2f}")
            if gap.workaround:
                output.append(f"   Workaround: {gap.workaround}")
            if gap.suggested_tool:
                output.append(f"   Suggested tool: {gap.suggested_tool}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error listing gaps: {str(e)}"


# ============================================================================
# Action classes
# ============================================================================

class LogCapabilityGapAction(Action):
    content: str = Field(description="What the agent cannot do")
    context: str = Field(description="The specific request that triggered this gap")
    workaround: Optional[str] = Field(default=None, description="Any workaround suggested")


class ListCapabilityGapsAction(Action):
    min_triggers: int = Field(default=1, description="Minimum trigger count to include")


# ============================================================================
# Observation classes
# ============================================================================

class LogCapabilityGapObservation(Observation):
    pass


class ListCapabilityGapsObservation(Observation):
    pass


# ============================================================================
# Executor classes
# ============================================================================

class LogCapabilityGapExecutor(ToolExecutor[LogCapabilityGapAction, LogCapabilityGapObservation]):
    def __call__(self, action: LogCapabilityGapAction, conversation=None) -> LogCapabilityGapObservation:
        result = _log_capability_gap(action.content, action.context, action.workaround)
        return LogCapabilityGapObservation.from_text(result)


class ListCapabilityGapsExecutor(ToolExecutor[ListCapabilityGapsAction, ListCapabilityGapsObservation]):
    def __call__(self, action: ListCapabilityGapsAction, conversation=None) -> ListCapabilityGapsObservation:
        result = _list_capability_gaps(action.min_triggers)
        return ListCapabilityGapsObservation.from_text(result)


# ============================================================================
# ToolDefinition classes
# ============================================================================

class LogCapabilityGapTool(ToolDefinition[LogCapabilityGapAction, LogCapabilityGapObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["LogCapabilityGapTool"]:
        return [cls(
            description=(
                "Log a capability gap when you cannot fulfill a request natively. "
                "Use for: math computation, email, calendar, web browsing, real-time data, "
                "or any functional limitation. Per Directive 2-17."
            ),
            action_type=LogCapabilityGapAction,
            observation_type=LogCapabilityGapObservation,
            executor=LogCapabilityGapExecutor(),
        )]


class ListCapabilityGapsTool(ToolDefinition[ListCapabilityGapsAction, ListCapabilityGapsObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["ListCapabilityGapsTool"]:
        return [cls(
            description=(
                "List all logged capability gaps ranked by priority. "
                "Shows what the agent cannot do and how often it's been requested."
            ),
            action_type=ListCapabilityGapsAction,
            observation_type=ListCapabilityGapsObservation,
            executor=ListCapabilityGapsExecutor(),
        )]


# ============================================================================
# Registration
# ============================================================================

register_tool("LogCapabilityGapTool", LogCapabilityGapTool)
register_tool("ListCapabilityGapsTool", ListCapabilityGapsTool)


def get_capability_tracker_tools() -> List[Tool]:
    """Return Tool specs for capability tracking tools."""
    return [
        Tool(name="LogCapabilityGapTool"),
        Tool(name="ListCapabilityGapsTool"),
    ]
