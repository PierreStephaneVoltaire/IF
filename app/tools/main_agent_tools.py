"""Main agent tool definitions for IF Prototype A1.

This module defines the OpenAI-compatible tool schemas that the main agent
can call to orchestrate categorization, directive lookup, intent condensation,
and subagent spawning.

These are the tool *definitions* (schemas). The actual execution logic lives
in tool_executor.py.
"""
from __future__ import annotations
from typing import Any, Dict, List


# ============================================================================
# Tool: categorize_conversation
# ============================================================================

CATEGORIZE_CONVERSATION_TOOL = {
    "type": "function",
    "function": {
        "name": "categorize_conversation",
        "description": (
            "Analyze the conversation to determine:\n"
            "1. The domain category (coding, architecture, social, financial, health, general, shell)\n"
            "2. The reasoning pattern to use (simple, opposing_perspective, multi_perspective, "
            "research, sequential_refinement)\n"
            "3. A condensed summary of the user's intent\n"
            "4. Which directives from IF Prototype A1's ruleset apply\n\n"
            "Call this tool first before deciding how to respond."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "analyze": {
                    "type": "boolean",
                    "description": "Set to true to analyze the current conversation.",
                },
            },
            "required": ["analyze"],
        },
    },
}


# ============================================================================
# Tool: get_directives
# ============================================================================

GET_DIRECTIVES_TOOL = {
    "type": "function",
    "function": {
        "name": "get_directives",
        "description": (
            "Look up the applicable IF Prototype A1 directives for a given category and "
            "reasoning pattern. Returns a formatted list of directive strings that must be "
            "followed when generating or rewriting the response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The domain category (e.g. coding, architecture, social).",
                },
                "reasoning_pattern": {
                    "type": "string",
                    "description": "The reasoning pattern (e.g. simple, sequential_refinement).",
                },
            },
            "required": ["category", "reasoning_pattern"],
        },
    },
}


# ============================================================================
# Tool: condense_intent
# ============================================================================

CONDENSE_INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "condense_intent",
        "description": (
            "Summarize the conversation into a clear, actionable prompt suitable for passing "
            "to a specialist subagent. Removes pleasantries and filler while preserving "
            "technical details and context. Call this before spawning a subagent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "condense": {
                    "type": "boolean",
                    "description": "Set to true to condense the current conversation.",
                },
            },
            "required": ["condense"],
        },
    },
}


# ============================================================================
# Tool: spawn_subagent
# ============================================================================

SPAWN_SUBAGENT_TOOL = {
    "type": "function",
    "function": {
        "name": "spawn_subagent",
        "description": (
            "Spawn a specialist subagent to handle the task. The subagent will use the "
            "appropriate workflow (simple, sequential_refinement, opposing_perspective, "
            "multi_perspective, or research) based on the reasoning pattern. "
            "Returns the raw specialist output which you should then rewrite in your voice."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "The domain category for the specialist (e.g. coding, architecture).",
                },
                "reasoning_pattern": {
                    "type": "string",
                    "description": "The reasoning pattern to use (e.g. simple, sequential_refinement).",
                },
                "condensed_intent": {
                    "type": "string",
                    "description": "The condensed intent prompt for the specialist.",
                },
                "applicable_directives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of directive strings to inject into the specialist context.",
                },
            },
            "required": ["category", "reasoning_pattern", "condensed_intent", "applicable_directives"],
        },
    },
}


# All tool definitions as a list for easy registration
ALL_MAIN_AGENT_TOOLS: List[Dict[str, Any]] = [
    CATEGORIZE_CONVERSATION_TOOL,
    GET_DIRECTIVES_TOOL,
    CONDENSE_INTENT_TOOL,
    SPAWN_SUBAGENT_TOOL,
]
