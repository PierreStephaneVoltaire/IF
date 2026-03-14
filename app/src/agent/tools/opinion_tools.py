
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
    OpinionPair,
    Misconception,
    get_user_fact_store
)
from agent.tools.user_facts import _current_cache_key, get_current_context_id


def _log_opinion_pair(
    topic: str,
    user_position: str,
    agent_position: str,
    agent_reasoning: str,
    agreement_level: str = "partial",
    confidence: float = 0.7
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
            query=topic,
            category=FactCategory.OPINION_PAIR,
            limit=1,
        )

        if existing:
            old_fact = existing[0]
            pair_metadata = old_fact.metadata if hasattr(old_fact, 'metadata') else {}
            pair = OpinionPair.from_dict(pair_metadata)

            pair.evolution = pair.evolution or []
            pair.evolution.append({
                "previous_position": pair.agent_position,
                "new_position": agent_position,
                "reason": agent_reasoning,
                "timestamp": now,
            })
            pair.agent_position = agent_position
            pair.agent_reasoning = agent_reasoning
            pair.agent_confidence = confidence
            pair.agreement_level = agreement_level
            pair.updated_at = now

            # Update by superseding
            new_fact = store.supersede(
                context_id=context_id,
                old_fact_id=old_fact.id,
                new_content=f"Opinion: {topic}",
                reason="Opinion evolution update",
                cache_key=_current_cache_key,
            )
            return f"Opinion pair updated (ID: {new_fact.id})"

        pair = OpinionPair(
            topic=topic,
            user_position=user_position,
            agent_position=agent_position,
            agent_reasoning=agent_reasoning,
            agent_confidence=confidence,
            agreement_level=agreement_level,
            created_at=now,
            updated_at=now,
        )

        store.add(
            context_id=context_id,
            content=f"Opinion: {topic}",
            category=FactCategory.OPINION_PAIR,
            source=FactSource.MODEL_OBSERVED,
            confidence=confidence,
            cache_key=_current_cache_key,
            metadata=pair.to_dict(),
        )
        return f"Opinion pair logged"

    except Exception as e:
        return f"Error logging opinion pair: {str(e)}"


def _log_misconception(
    topic: str,
    what_they_said: str,
    what_is_correct: str,
    domain: str,
    severity: str = "minor",
    suggested_resources: Optional[List[str]] = None
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
            query=f"{topic} {what_they_said}",
            category=FactCategory.MISCONCEPTION,
            limit=1,
        )

        if existing:
            old_fact = existing[0]
            misc_metadata = old_fact.metadata if hasattr(old_fact, 'metadata') else {}
            misc = Misconception.from_dict(misc_metadata)
            misc.recurrence_count += 1
            misc.last_seen = now

            # Update by superseding
            store.supersede(
                context_id=context_id,
                old_fact_id=old_fact.id,
                new_content=f"Misconception: {topic} - {what_they_said[:50]}",
                reason="Misconception recurrence",
                cache_key=_current_cache_key,
            )
            return f"Misconception recurrence logged (count: {misc.recurrence_count})"

        misc = Misconception(
            topic=topic,
            what_they_said=what_they_said,
            what_is_correct=what_is_correct,
            domain=domain,
            severity=severity,
            corrected_in_session=True,
            recurrence_count=1,
            suggested_resources=suggested_resources or [],
            created_at=now,
            last_seen=now,
        )

        store.add(
            context_id=context_id,
            content=f"Misconception: {topic} - {what_they_said[:50]}",
            category=FactCategory.MISCONCEPTION,
            source=FactSource.MODEL_OBSERVED,
            confidence=0.9,
            cache_key=_current_cache_key,
            metadata=misc.to_dict(),
        )
        return f"Misconception logged"

    except Exception as e:
        return f"Error logging misconception: {str(e)}"



class LogOpinionPairAction(Action):
    topic: str = Field(description="The subject of the opinion")
    user_position: str = Field(description="What the operator believes/said")
    agent_position: str = Field(description="Your position on this topic")
    agent_reasoning: str = Field(description="Why you hold this position")
    agreement_level: str = Field(default="partial", description="agree, partial, disagree, or insufficient_data")
    confidence: float = Field(default=0.7, description="Your confidence level 0.0-1.0")


class LogMisconceptionAction(Action):
    topic: str = Field(description="The subject area")
    what_they_said: str = Field(description="What the operator incorrectly stated")
    what_is_correct: str = Field(description="The correct information")
    domain: str = Field(description="Domain (networking, programming, AWS, etc.)")
    severity: str = Field(default="minor", description="minor, moderate, or critical")
    suggested_resources: Optional[List[str]] = Field(default=None, description="Reading suggestions")



class LogOpinionPairObservation(Observation):
    pass


class LogMisconceptionObservation(Observation):
    pass



class LogOpinionPairExecutor(ToolExecutor[LogOpinionPairAction, LogOpinionPairObservation]):
    def __call__(self, action: LogOpinionPairAction, conversation=None) -> LogOpinionPairObservation:
        result = _log_opinion_pair(
            action.topic,
            action.user_position,
            action.agent_position,
            action.agent_reasoning,
            action.agreement_level,
            action.confidence
        )
        return LogOpinionPairObservation.from_text(result)


class LogMisconceptionExecutor(ToolExecutor[LogMisconceptionAction, LogMisconceptionObservation]):
    def __call__(self, action: LogMisconceptionAction, conversation=None) -> LogMisconceptionObservation:
        result = _log_misconception(
            action.topic,
            action.what_they_said,
            action.what_is_correct,
            action.domain,
            action.severity,
            action.suggested_resources
        )
        return LogMisconceptionObservation.from_text(result)



class LogOpinionPairTool(ToolDefinition[LogOpinionPairAction, LogOpinionPairObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["LogOpinionPairTool"]:
        return [cls(
            description=(
                "Log an opinion pair when the operator expresses a strong position. "
                "Record both their position and your assessment with reasoning."
            ),
            action_type=LogOpinionPairAction,
            observation_type=LogOpinionPairObservation,
            executor=LogOpinionPairExecutor(),
        )]


class LogMisconceptionTool(ToolDefinition[LogMisconceptionAction, LogMisconceptionObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["LogMisconceptionTool"]:
        return [cls(
            description=(
                "Log a factual misunderstanding demonstrated by the operator. "
                "Use for objectively incorrect beliefs (NOT opinions). "
                "Correct the misconception and suggest resources. Per Directive 2-18."
            ),
            action_type=LogMisconceptionAction,
            observation_type=LogMisconceptionObservation,
            executor=LogMisconceptionExecutor(),
        )]



register_tool("LogOpinionPairTool", LogOpinionPairTool)
register_tool("LogMisconceptionTool", LogMisconceptionTool)


def get_opinion_tools() -> List[Tool]:

    return [
        Tool(name="LogOpinionPairTool"),
        Tool(name="LogMisconceptionTool"),
    ]
