"""Tool execution handlers for the main agent tools.

This module implements the actual execution logic for each tool that the
main IF Prototype A1 agent can call. Each function wraps existing logic
from categorization.py, directive_injector.py, and the workflows.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


async def execute_categorize(
    messages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Execute the categorize_conversation tool.

    Runs 3-model parallel categorization (category + reasoning) and
    condenses the intent. Wraps existing categorization logic.

    Args:
        messages: List of conversation message dicts

    Returns:
        Dict with category, reasoning_pattern, condensed_intent,
        category_scores, reasoning_scores, applicable_directives,
        suggested_agent.
    """
    from tools.categorization_tool import execute_categorization_tool

    result = await execute_categorization_tool(messages)
    return {
        "category": result.category,
        "reasoning_pattern": result.reasoning_pattern,
        "condensed_intent": result.condensed_intent,
        "category_scores": result.category_scores,
        "reasoning_scores": result.reasoning_scores,
        "applicable_directives": result.applicable_directives,
        "suggested_agent": result.suggested_agent,
    }


def execute_get_directives(
    category: str,
    reasoning_pattern: str,
) -> List[str]:
    """Execute the get_directives tool.

    Looks up applicable directives from the main system prompt using
    the existing DirectiveInjector.

    Args:
        category: The domain category
        reasoning_pattern: The reasoning pattern

    Returns:
        List of formatted directive strings
    """
    from directive_injector import get_directive_injector

    injector = get_directive_injector()
    directives = injector.get_directives_for_context(category, reasoning_pattern)
    return injector.format_for_injection(directives, include_priority=True)


async def execute_condense_intent(
    messages: List[Dict[str, Any]],
) -> str:
    """Execute the condense_intent tool.

    Summarizes the conversation into a focused intent statement.

    Args:
        messages: List of conversation message dicts

    Returns:
        Condensed intent string
    """
    from categorization import condense_intent

    return await condense_intent(messages)


async def execute_spawn_subagent(
    messages: List[Dict[str, Any]],
    category: str,
    reasoning_pattern: str,
    condensed_intent: str,
    applicable_directives: List[str],
    sandbox_dir: Optional[str] = None,
    chat_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute the spawn_subagent tool.

    Creates and runs the appropriate workflow for the given category and
    reasoning pattern. Returns the raw specialist output.

    Args:
        messages: List of conversation message dicts
        category: The domain category
        reasoning_pattern: The reasoning pattern
        condensed_intent: The condensed intent prompt
        applicable_directives: List of directive strings
        sandbox_dir: Optional sandbox directory for file operations
        chat_id: Optional chat identifier
        metadata: Optional additional metadata

    Returns:
        Dict with content, success, agent_name, model, attachments, metadata
    """
    from workflows import get_workflow, WorkflowContext

    workflow = get_workflow(reasoning_pattern)

    context = WorkflowContext(
        messages=messages,
        category=category,
        reasoning_pattern=reasoning_pattern,
        condensed_intent=condensed_intent,
        applicable_directives=applicable_directives,
        sandbox_dir=sandbox_dir,
        chat_id=chat_id or "",
        metadata=metadata or {},
    )

    result = await workflow.execute(context)

    return {
        "content": result.content,
        "success": result.success,
        "agent_name": result.agent_name,
        "model": result.model,
        "attachments": result.attachments,
        "metadata": result.metadata,
    }
