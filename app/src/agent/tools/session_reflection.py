
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
    SessionReflection,
    get_user_fact_store
)
from agent.tools.user_facts import _current_cache_key, get_current_context_id


def _store_session_reflection(
    session_id: str,
    summary: str,
    what_worked: List[str],
    what_failed: List[str],
    operator_satisfaction: str,
    new_facts_stored: int,
    capability_gaps_hit: List[str],
    misconceptions_found: List[str],
    open_threads: List[str],
    meta_notes: str,
    preset_used: str,
    preset_fit_score: float
) -> str:

    from datetime import datetime, timezone

    context_id = get_current_context_id()
    if not context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()
        now = datetime.now(timezone.utc).isoformat()

        existing = store.search(
            context_id=context_id,
            query=session_id,
            category=FactCategory.SESSION_REFLECTION,
            limit=1,
        )

        if existing:
            old_fact = existing[0]
            reflection_metadata = old_fact.metadata if hasattr(old_fact, 'metadata') else {}
            reflection = SessionReflection.from_dict(reflection_metadata)

            reflection.summary = summary
            reflection.what_worked = what_worked
            reflection.what_failed = what_failed
            reflection.operator_satisfaction = operator_satisfaction
            reflection.new_facts_stored = new_facts_stored
            reflection.capability_gaps_hit = capability_gaps_hit
            reflection.misconceptions_found = misconceptions_found
            reflection.open_threads = open_threads
            reflection.meta_notes = meta_notes
            reflection.preset_used = preset_used
            reflection.preset_fit_score = preset_fit_score

            # Update by superseding the old fact
            new_fact = store.supersede(
                context_id=context_id,
                old_fact_id=old_fact.id,
                new_content=f"Session reflection: {summary[:100]}",
                reason="Session reflection update",
                cache_key=_current_cache_key,
            )
            return f"Session reflection updated (ID: {new_fact.id})"

        reflection = SessionReflection(
            session_id=session_id,
            summary=summary,
            what_worked=what_worked,
            what_failed=what_failed,
            operator_satisfaction=operator_satisfaction,
            new_facts_stored=new_facts_stored,
            capability_gaps_hit=capability_gaps_hit,
            misconceptions_found=misconceptions_found,
            open_threads=open_threads,
            meta_notes=meta_notes,
            preset_used=preset_used,
            preset_fit_score=preset_fit_score,
            created_at=now,
        )

        store.add(
            context_id=context_id,
            content=f"Session reflection: {summary[:100]}",
            category=FactCategory.SESSION_REFLECTION,
            source=FactSource.MODEL_OBSERVED,
            confidence=0.8,
            cache_key=_current_cache_key,
            metadata=reflection.to_dict(),
        )
        return f"Session reflection stored"

    except Exception as e:
        return f"Error storing session reflection: {str(e)}"



class StoreSessionReflectionAction(Action):
    session_id: str = Field(description="The conversation ID")
    summary: str = Field(description="Brief summary of what happened")
    what_worked: List[str] = Field(default_factory=list, description="Approaches that worked")
    what_failed: List[str] = Field(default_factory=list, description="Approaches that failed")
    operator_satisfaction: str = Field(default="neutral", description="positive, neutral, or negative")
    new_facts_stored: int = Field(default=0, description="Count of facts captured")
    capability_gaps_hit: List[str] = Field(default_factory=list, description="Gap IDs triggered")
    misconceptions_found: List[str] = Field(default_factory=list, description="Misconception IDs")
    open_threads: List[str] = Field(default_factory=list, description="Unresolved questions")
    meta_notes: str = Field(default="", description="Free-form reflection")
    preset_used: str = Field(default="", description="Routing preset used")
    preset_fit_score: float = Field(default=0.0, description="Self-assessed routing fit 0.0-1.0")



class StoreSessionReflectionObservation(TextObservation):
    pass



class StoreSessionReflectionExecutor(ToolExecutor[StoreSessionReflectionAction, StoreSessionReflectionObservation]):
    def __call__(self, action: StoreSessionReflectionAction, conversation=None) -> StoreSessionReflectionObservation:
        result = _store_session_reflection(
            action.session_id,
            action.summary,
            action.what_worked,
            action.what_failed,
            action.operator_satisfaction,
            action.new_facts_stored,
            action.capability_gaps_hit,
            action.misconceptions_found,
            action.open_threads,
            action.meta_notes,
            action.preset_used,
            action.preset_fit_score
        )
        return StoreSessionReflectionObservation.from_text(result)



class StoreSessionReflectionTool(ToolDefinition[StoreSessionReflectionAction, StoreSessionReflectionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["StoreSessionReflectionTool"]:
        return [cls(
            description=(
                "Store a rich session reflection after substantive conversations (>5 turns). "
                "Captures what worked, what failed, and what was learned. Per Directive 2-16."
            ),
            action_type=StoreSessionReflectionAction,
            observation_type=StoreSessionReflectionObservation,
            executor=StoreSessionReflectionExecutor(),
        )]



register_tool("StoreSessionReflectionTool", StoreSessionReflectionTool)


def get_session_reflection_tools() -> List[Tool]:

    return [
        Tool(name="StoreSessionReflectionTool"),
    ]
