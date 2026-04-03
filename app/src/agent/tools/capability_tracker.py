
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
from agent.tools.base import TextObservation

from memory.user_facts import (
    FactCategory,
    FactSource,
    get_user_fact_store
)

from agent.tools.user_facts import _current_cache_key, _current_context_id, get_current_context_id



def _log_capability_gap(
    content: str,
    context: str,
    workaround: Optional[str] = None
) -> str:
    context_id = get_current_context_id()
    if not context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()
        gap_id = store.log_capability_gap(
            context_id=context_id,
            content=content,
            trigger_context=context,
            cache_key=_current_cache_key,
            workaround=workaround,
        )
        return f"Capability gap logged (ID: {gap_id})"
    except Exception as e:
        return f"Error logging capability gap: {str(e)}"


def _list_capability_gaps(min_triggers: int = 1) -> str:
    context_id = get_current_context_id()
    if not context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()
        gaps = store.list_capability_gaps(
            context_id=context_id,
            min_triggers=min_triggers
        )
        
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



class LogCapabilityGapAction(Action):
    content: str = Field(description="What the agent cannot do")
    context: str = Field(description="The specific request that triggered this gap")
    workaround: Optional[str] = Field(default=None, description="Any workaround suggested")


class ListCapabilityGapsAction(Action):
    min_triggers: int = Field(default=1, description="Minimum trigger count to include")



class LogCapabilityGapObservation(TextObservation):
    pass


class ListCapabilityGapsObservation(TextObservation):
    pass



class LogCapabilityGapExecutor(ToolExecutor[LogCapabilityGapAction, LogCapabilityGapObservation]):
    def __call__(self, action: LogCapabilityGapAction, conversation=None) -> LogCapabilityGapObservation:
        result = _log_capability_gap(action.content, action.context, action.workaround)
        return LogCapabilityGapObservation.from_text(result)


class ListCapabilityGapsExecutor(ToolExecutor[ListCapabilityGapsAction, ListCapabilityGapsObservation]):
    def __call__(self, action: ListCapabilityGapsAction, conversation=None) -> ListCapabilityGapsObservation:
        result = _list_capability_gaps(action.min_triggers)
        return ListCapabilityGapsObservation.from_text(result)



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



register_tool("LogCapabilityGapTool", LogCapabilityGapTool)
register_tool("ListCapabilityGapsTool", ListCapabilityGapsTool)


def get_capability_tracker_tools() -> List[Tool]:

    return [
        Tool(name="LogCapabilityGapTool"),
        Tool(name="ListCapabilityGapsTool"),
    ]
