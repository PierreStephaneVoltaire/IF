"""User facts tools for agent access.

These tools allow the agent to store and retrieve facts about the operator.
The agent uses these to build persistent knowledge about the operator's
preferences, skills, goals, and patterns.

Tools:
- user_facts_search: Semantic search across stored facts
- user_facts_add: Store a new fact about the operator
- user_facts_update: Update/supersede an existing fact
- user_facts_list: List all stored facts
- user_facts_remove: Request removal of a fact (requires confirmation)
"""
from __future__ import annotations
from typing import List, Optional

from openhands.sdk import Tool, ToolExecutor

from memory.user_facts import (
    UserFact,
    FactCategory,
    FactSource,
    get_user_fact_store
)


# Session context injection (set by session.py)
_current_username: str = ""
_current_cache_key: str = ""


def set_session_context(username: str, cache_key: str) -> None:
    """Set the current session context for tool handlers.
    
    This is called by the session manager to inject the current
    username and cache_key so tools can use them without the agent
    needing to provide them.
    
    Args:
        username: The operator's username
        cache_key: The current conversation cache key
    """
    global _current_username, _current_cache_key
    _current_username = username or "operator"
    _current_cache_key = cache_key or ""


def user_facts_search(
    query: str,
    category: Optional[str] = None,
    limit: int = 5
) -> str:
    """Search user facts semantically.
    
    Finds facts that are semantically relevant to the query.
    Use this to retrieve context about the operator's preferences,
    skills, history, or any other stored information.
    
    Args:
        query: The search query describing what you're looking for
        category: Optional category filter (personal, preference, opinion,
                  skill, life_event, future_direction, project_direction,
                  mental_state, conversation_summary, topic_log, model_assessment)
        limit: Maximum number of results to return (default 5)
        
    Returns:
        Formatted list of matching facts
    """
    try:
        store = get_user_fact_store()
        
        cat = FactCategory(category) if category else None
        results = store.search(query, category=cat, limit=limit)
        
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


def user_facts_add(
    content: str,
    category: str,
    source: str = "user_stated",
    confidence: float = 0.8
) -> str:
    """Store a new fact about the operator.
    
    Use this to capture information about the operator that should
    persist across conversations: preferences, skills, goals, patterns.
    
    Args:
        content: The fact content (be specific and clear)
        category: One of: personal, preference, opinion, skill, life_event,
                  future_direction, project_direction, mental_state,
                  conversation_summary, topic_log, model_assessment
        source: Source of the fact (user_stated, model_observed, model_assessed,
                conversation_derived). Default: user_stated
        confidence: Confidence level 0.0-1.0 (default 0.8)
        
    Returns:
        Confirmation message with the new fact ID
    """
    from datetime import datetime
    
    # Validate category
    valid_categories = [c.value for c in FactCategory]
    if category not in valid_categories:
        return f"Invalid category '{category}'. Valid categories: {', '.join(valid_categories)}"
    
    # Validate source
    valid_sources = [s.value for s in FactSource]
    if source not in valid_sources:
        return f"Invalid source '{source}'. Valid sources: {', '.join(valid_sources)}"
    
    try:
        store = get_user_fact_store()
        
        fact = UserFact(
            username=_current_username,
            content=content,
            category=FactCategory(category),
            source=FactSource(source),
            confidence=confidence,
            cache_key=_current_cache_key,
            created_at=datetime.utcnow().isoformat() + "Z",
            updated_at=datetime.utcnow().isoformat() + "Z",
        )
        
        store.add(fact)
        return f"Fact stored successfully (ID: {fact.id})"
    except Exception as e:
        return f"Error storing fact: {str(e)}"


def user_facts_update(
    fact_id: str,
    new_content: str,
    reason: str
) -> str:
    """Update an existing fact by superseding it.
    
    Creates a new fact with the updated content and marks the old one
    as superseded. The old fact is preserved for history.
    
    Args:
        fact_id: ID of the fact to update
        new_content: The new/updated content
        reason: Reason for the update (required)
        
    Returns:
        Confirmation message with the new fact ID
    """
    try:
        store = get_user_fact_store()
        new_fact = store.supersede(
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


def user_facts_list(
    category: Optional[str] = None,
    include_history: bool = False
) -> str:
    """List all stored facts.
    
    Shows facts organized by category. Use this to review what
    is known about the operator.
    
    Args:
        category: Optional category filter
        include_history: Include superseded/inactive facts (default False)
        
    Returns:
        Formatted list of all facts
    """
    try:
        store = get_user_fact_store()
        
        cat = FactCategory(category) if category else None
        facts = store.list_facts(category=cat, include_history=include_history)
        
        if not facts:
            return "No facts stored."
        
        output = [f"Stored facts ({len(facts)} total):", ""]
        for i, fact in enumerate(facts, 1):
            status = "" if fact.active else "[INACTIVE] "
            output.append(f"{i}. {status}[{fact.category.value}] {fact.content}")
            output.append(f"   Source: {fact.source.value}, Updated: {fact.updated_at[:10]}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error listing facts: {str(e)}"


def user_facts_remove(fact_id: str) -> str:
    """Request removal of a fact.
    
    Per Directive 0-1, fact deletion requires explicit operator
    confirmation. This tool initiates the request.
    
    Args:
        fact_id: ID of the fact to remove
        
    Returns:
        Instructions for confirming deletion
    """
    try:
        store = get_user_fact_store()
        fact = store.get(fact_id)
        
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


def user_facts_remove_confirmed(fact_id: str) -> str:
    """Actually remove a fact after confirmation.
    
    This should only be called after the operator has explicitly
    confirmed the deletion.
    
    Args:
        fact_id: ID of the fact to remove
        
    Returns:
        Confirmation of deletion
    """
    try:
        store = get_user_fact_store()
        fact = store.get(fact_id)
        
        if not fact:
            return f"Fact not found: {fact_id}"
        
        success = store.remove(fact_id)
        if success:
            return f"Fact removed.\nDeleted: [{fact.category.value}] {fact.content}"
        return f"Failed to remove fact: {fact_id}"
    except Exception as e:
        return f"Error removing fact: {str(e)}"


def get_user_facts_tools() -> List[Tool]:
    """Get user facts tool definitions for OpenHands agent.
    
    Returns:
        List of Tool objects for registration with the agent
    """
    return [
        Tool(
            name="user_facts_search",
            description="Search stored facts about the operator semantically. Use to retrieve context about preferences, skills, history, or any stored information.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query describing what you're looking for"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                        "enum": [c.value for c in FactCategory]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 5)"
                    }
                },
                "required": ["query"]
            },
            executor=ToolExecutor(user_facts_search)
        ),
        Tool(
            name="user_facts_add",
            description="Store a new fact about the operator. Use to capture preferences, skills, goals, patterns, or observations that should persist.",
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The fact content (be specific and clear)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category of the fact",
                        "enum": [c.value for c in FactCategory]
                    },
                    "source": {
                        "type": "string",
                        "description": "Source of the fact",
                        "enum": [s.value for s in FactSource],
                        "default": "user_stated"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence level 0.0-1.0",
                        "default": 0.8
                    }
                },
                "required": ["content", "category"]
            },
            executor=ToolExecutor(user_facts_add)
        ),
        Tool(
            name="user_facts_update",
            description="Update an existing fact by superseding it. The old fact is preserved for history.",
            parameters={
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "string",
                        "description": "ID of the fact to update"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The new/updated content"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the update"
                    }
                },
                "required": ["fact_id", "new_content", "reason"]
            },
            executor=ToolExecutor(user_facts_update)
        ),
        Tool(
            name="user_facts_list",
            description="List all stored facts. Use to review what is known about the operator.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional category filter",
                        "enum": [c.value for c in FactCategory]
                    },
                    "include_history": {
                        "type": "boolean",
                        "description": "Include superseded/inactive facts",
                        "default": False
                    }
                },
                "required": []
            },
            executor=ToolExecutor(user_facts_list)
        ),
        Tool(
            name="user_facts_remove",
            description="Request removal of a fact. Requires operator confirmation per Directive 0-1.",
            parameters={
                "type": "object",
                "properties": {
                    "fact_id": {
                        "type": "string",
                        "description": "ID of the fact to remove"
                    }
                },
                "required": ["fact_id"]
            },
            executor=ToolExecutor(user_facts_remove)
        ),
    ]
