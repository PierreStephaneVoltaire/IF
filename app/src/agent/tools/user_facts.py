
from __future__ import annotations
from typing import List, Optional, Dict, Any, Sequence

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


# Session context - set by the agent session before tool execution
_current_username: str = ""
_current_cache_key: str = ""
_current_context_id: str = ""


def set_session_context(username: str, cache_key: str, context_id: str = "") -> None:
    """Set the session context for user facts tools.

    Args:
        username: The current user's name
        cache_key: The cache/conversation key
        context_id: The context ID for LanceDB storage (format: openwebui_{id} or discord_{id})
    """
    global _current_username, _current_cache_key, _current_context_id
    _current_username = username or "operator"
    _current_cache_key = cache_key or ""
    _current_context_id = context_id or cache_key  # Fallback to cache_key if no context_id


def get_current_context_id() -> str:
    """Get the current context ID."""
    return _current_context_id


def _user_facts_search(
    query: str,
    category: Optional[str] = None,
    limit: int = 5
) -> str:
    """Search for facts in the current context."""
    if not _current_context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()

        cat = FactCategory(category) if category else None
        results = store.search(
            context_id=_current_context_id,
            query=query,
            category=cat,
            limit=limit
        )

        if not results:
            return "No facts found matching that query."

        output = [f"Found {len(results)} relevant facts:", ""]
        for i, fact in enumerate(results, 1):
            source_tag = "observed" if fact.source in (
                FactSource.MODEL_OBSERVED, FactSource.MODEL_ASSESSED
            ) else "stated"
            output.append(f"{i}. [{fact.category.value}] [{source_tag}] {fact.content}")
            output.append(f"   Updated: {fact.updated_at[:10]}")

        return "\n".join(output)
    except Exception as e:
        return f"Error searching facts: {str(e)}"


def _user_facts_add(
    content: str,
    category: str,
    source: str = "user_stated",
    confidence: float = 0.8
) -> str:
    """Add a fact in the current context."""
    from datetime import datetime, timezone

    if not _current_context_id:
        return "Error: No context ID set for this session."

    valid_categories = [c.value for c in FactCategory]
    if category not in valid_categories:
        return f"Invalid category '{category}'. Valid categories: {', '.join(valid_categories)}"

    valid_sources = [s.value for s in FactSource]
    if source not in valid_sources:
        return f"Invalid source '{source}'. Valid sources: {', '.join(valid_sources)}"

    try:
        store = get_user_fact_store()

        fact_id = store.add(
            context_id=_current_context_id,
            content=content,
            category=FactCategory(category),
            source=FactSource(source),
            username=_current_username,
            confidence=confidence,
            cache_key=_current_cache_key,
        )

        return f"Fact stored successfully (ID: {fact_id})"
    except Exception as e:
        return f"Error storing fact: {str(e)}"


def _user_facts_update(
    fact_id: str,
    new_content: str,
    reason: str
) -> str:
    """Update a fact by superseding it."""
    if not _current_context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()
        new_fact = store.supersede(
            context_id=_current_context_id,
            old_fact_id=fact_id,
            new_content=new_content,
            reason=reason,
            cache_key=_current_cache_key
        )
        return f"Fact updated. New ID: {new_fact.id}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error updating fact: {str(e)}"


def _user_facts_list(
    category: Optional[str] = None,
    include_history: bool = False
) -> str:
    """List facts in the current context."""
    if not _current_context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()

        cat = FactCategory(category) if category else None
        facts = store.list_facts(
            context_id=_current_context_id,
            category=cat,
            include_history=include_history
        )

        if not facts:
            return "No facts stored in this context."

        output = [f"Stored facts ({len(facts)} total):", ""]
        for i, fact in enumerate(facts, 1):
            status = "" if fact.active else "[INACTIVE] "
            output.append(f"{i}. {status}[{fact.category.value}] {fact.content}")
            output.append(f"   Source: {fact.source.value}, Updated: {fact.updated_at[:10]}")

        return "\n".join(output)
    except Exception as e:
        return f"Error listing facts: {str(e)}"


def _user_facts_remove(fact_id: str) -> str:
    """Request removal of a fact (requires confirmation)."""
    if not _current_context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()
        fact = store.get(_current_context_id, fact_id)

        if not fact:
            return f"Fact not found: {fact_id}"

        return (
            "PER DIRECTIVE 0-1: Fact deletion requires explicit operator confirmation.\n"
            f"Fact ID: {fact_id}\n"
            f"Content: [{fact.category.value}] {fact.content}\n"
            "Please confirm deletion by responding with 'yes' or 'confirm'."
        )
    except Exception as e:
        return f"Error: {str(e)}"


def _user_facts_remove_confirmed(fact_id: str) -> str:
    """Remove a fact after confirmation."""
    if not _current_context_id:
        return "Error: No context ID set for this session."

    try:
        store = get_user_fact_store()
        fact = store.get(_current_context_id, fact_id)

        if not fact:
            return f"Fact not found: {fact_id}"

        success = store.remove(_current_context_id, fact_id)
        if success:
            return f"Fact removed.\nDeleted: [{fact.category.value}] {fact.content}"
        return f"Failed to remove fact: {fact_id}"
    except Exception as e:
        return f"Error removing fact: {str(e)}"



class UserFactsSearchAction(Action):
    query: str = Field(description="The search query describing what you're looking for")
    category: Optional[str] = Field(
        default=None,
        description="Optional category filter"
    )
    limit: int = Field(default=5, description="Maximum number of results to return")


class UserFactsAddAction(Action):
    content: str = Field(description="The fact content (be specific and clear)")
    category: str = Field(
        description="Category of the fact: personal, preference, opinion, skill, life_event, "
                    "future_direction, project_direction, mental_state, conversation_summary, "
                    "topic_log, model_assessment, agent_identity, agent_opinion, agent_principle, "
                    "capability_gap, tool_suggestion, opinion_pair, misconception, interest_area, "
                    "session_reflection"
    )
    source: str = Field(default="user_stated", description="Source of the fact")
    confidence: float = Field(default=0.8, description="Confidence level 0.0-1.0")


class UserFactsUpdateAction(Action):
    fact_id: str = Field(description="ID of the fact to update")
    new_content: str = Field(description="The new/updated content")
    reason: str = Field(description="Reason for the update")


class UserFactsListAction(Action):
    category: Optional[str] = Field(default=None, description="Optional category filter")
    include_history: bool = Field(default=False, description="Include superseded/inactive facts")


class UserFactsRemoveAction(Action):
    fact_id: str = Field(description="ID of the fact to remove")



class UserFactsSearchObservation(TextObservation):
    pass


class UserFactsAddObservation(TextObservation):
    pass


class UserFactsUpdateObservation(TextObservation):
    pass


class UserFactsListObservation(TextObservation):
    pass


class UserFactsRemoveObservation(TextObservation):
    pass



class UserFactsSearchExecutor(ToolExecutor[UserFactsSearchAction, UserFactsSearchObservation]):
    def __call__(self, action: UserFactsSearchAction, conversation=None) -> UserFactsSearchObservation:
        result = _user_facts_search(action.query, action.category, action.limit)
        return UserFactsSearchObservation.from_text(result)


class UserFactsAddExecutor(ToolExecutor[UserFactsAddAction, UserFactsAddObservation]):
    def __call__(self, action: UserFactsAddAction, conversation=None) -> UserFactsAddObservation:
        result = _user_facts_add(action.content, action.category, action.source, action.confidence)
        return UserFactsAddObservation.from_text(result)


class UserFactsUpdateExecutor(ToolExecutor[UserFactsUpdateAction, UserFactsUpdateObservation]):
    def __call__(self, action: UserFactsUpdateAction, conversation=None) -> UserFactsUpdateObservation:
        result = _user_facts_update(action.fact_id, action.new_content, action.reason)
        return UserFactsUpdateObservation.from_text(result)


class UserFactsListExecutor(ToolExecutor[UserFactsListAction, UserFactsListObservation]):
    def __call__(self, action: UserFactsListAction, conversation=None) -> UserFactsListObservation:
        result = _user_facts_list(action.category, action.include_history)
        return UserFactsListObservation.from_text(result)


class UserFactsRemoveExecutor(ToolExecutor[UserFactsRemoveAction, UserFactsRemoveObservation]):
    def __call__(self, action: UserFactsRemoveAction, conversation=None) -> UserFactsRemoveObservation:
        result = _user_facts_remove(action.fact_id)
        return UserFactsRemoveObservation.from_text(result)



class UserFactsSearchTool(ToolDefinition[UserFactsSearchAction, UserFactsSearchObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UserFactsSearchTool"]:
        return [cls(
            description=(
                "Search stored facts about the operator semantically. "
                "Use to retrieve context about preferences, skills, history, or any stored information."
            ),
            action_type=UserFactsSearchAction,
            observation_type=UserFactsSearchObservation,
            executor=UserFactsSearchExecutor(),
        )]


class UserFactsAddTool(ToolDefinition[UserFactsAddAction, UserFactsAddObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UserFactsAddTool"]:
        return [cls(
            description=(
                "Store a new fact about the operator. "
                "Use to capture preferences, skills, goals, patterns, or observations that should persist."
            ),
            action_type=UserFactsAddAction,
            observation_type=UserFactsAddObservation,
            executor=UserFactsAddExecutor(),
        )]


class UserFactsUpdateTool(ToolDefinition[UserFactsUpdateAction, UserFactsUpdateObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UserFactsUpdateTool"]:
        return [cls(
            description=(
                "Update an existing fact by superseding it. "
                "The old fact is preserved for history."
            ),
            action_type=UserFactsUpdateAction,
            observation_type=UserFactsUpdateObservation,
            executor=UserFactsUpdateExecutor(),
        )]


class UserFactsListTool(ToolDefinition[UserFactsListAction, UserFactsListObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UserFactsListTool"]:
        return [cls(
            description=(
                "List all stored facts. "
                "Use to review what is known about the operator."
            ),
            action_type=UserFactsListAction,
            observation_type=UserFactsListObservation,
            executor=UserFactsListExecutor(),
        )]


class UserFactsRemoveTool(ToolDefinition[UserFactsRemoveAction, UserFactsRemoveObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["UserFactsRemoveTool"]:
        return [cls(
            description=(
                "Request removal of a fact. "
                "Requires operator confirmation per Directive 0-1."
            ),
            action_type=UserFactsRemoveAction,
            observation_type=UserFactsRemoveObservation,
            executor=UserFactsRemoveExecutor(),
        )]



register_tool("UserFactsSearchTool", UserFactsSearchTool)
register_tool("UserFactsAddTool", UserFactsAddTool)
register_tool("UserFactsUpdateTool", UserFactsUpdateTool)
register_tool("UserFactsListTool", UserFactsListTool)
register_tool("UserFactsRemoveTool", UserFactsRemoveTool)


def get_user_facts_tools() -> List[Tool]:

    return [
        Tool(name="UserFactsSearchTool"),
        Tool(name="UserFactsAddTool"),
        Tool(name="UserFactsUpdateTool"),
        Tool(name="UserFactsListTool"),
        Tool(name="UserFactsRemoveTool"),
    ]
