"""Session reflection tools for post-conversation learning.

These tools allow the agent to store rich session reflections
that capture what worked, what failed, and what was learned.

Tools:
- store_session_reflection: Store a rich reflection after substantive conversations
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
    UserFact,
    FactCategory,
    FactSource,
    SessionReflection,
    get_user_fact_store
)
from agent.tools.user_facts import _current_cache_key


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
    """Store a rich session reflection after a substantive conversation.
    
    This replaces shallow conversation summaries with structured reflections
    that capture what was learned, what worked, and what failed.
    
    Args:
        session_id: The conversation ID
        summary: Brief summary of what happened
        what_worked: List of approaches that produced good outcomes
        what_failed: List of approaches that fell flat
        operator_satisfaction: "positive" | "neutral" | "negative"
        new_facts_stored: Count of facts captured this session
        capability_gaps_hit: List of capability gap IDs triggered
        misconceptions_found: List of misconception IDs corrected
        open_threads: Unresolved questions or tasks
        meta_notes: Free-form agent reflection
        preset_used: Which routing preset handled this
        preset_fit_score: Self-assessed routing accuracy 0.0-1.0
        
    Returns:
        Confirmation with reflection ID
    """
    from datetime import datetime, timezone
    
    try:
        store = get_user_fact_store()
        now = datetime.now(timezone.utc).isoformat()
        
        # Check for existing reflection for this session
        existing = store.search(
            query=session_id,
            category=FactCategory.SESSION_REFLECTION,
            limit=1,
        )
        
        if existing:
            # Update existing reflection
            old_fact = existing[0]
            reflection_metadata = old_fact.metadata if hasattr(old_fact, 'metadata') else {}
            reflection = SessionReflection.from_dict(reflection_metadata)
            
            # Update fields
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
            
            old_fact.metadata = reflection.to_dict()
            store._update_metadata(old_fact)
            return f"Session reflection updated (ID: {old_fact.id})"
        
        # Create new reflection
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
        
        fact = UserFact(
            content=f"Session reflection: {summary[:100]}",
            category=FactCategory.SESSION_REFLECTION,
            source=FactSource.MODEL_OBSERVED,
            confidence=0.8,
            cache_key=_current_cache_key,
            created_at=now,
            updated_at=now,
        )
        fact.metadata = reflection.to_dict()
        
        store.add(fact)
        return f"Session reflection stored (ID: {fact.id})"
        
    except Exception as e:
        return f"Error storing session reflection: {str(e)}"


# ============================================================================
# Action classes
# ============================================================================

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


# ============================================================================
# Observation classes
# ============================================================================

class StoreSessionReflectionObservation(Observation):
    pass


# ============================================================================
# Executor classes
# ============================================================================

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


# ============================================================================
# ToolDefinition classes
# ============================================================================

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


# ============================================================================
# Registration
# ============================================================================

register_tool("StoreSessionReflectionTool", StoreSessionReflectionTool)


def get_session_reflection_tools() -> List[Tool]:
    """Return Tool specs for session reflection tools."""
    return [
        Tool(name="StoreSessionReflectionTool"),
    ]
