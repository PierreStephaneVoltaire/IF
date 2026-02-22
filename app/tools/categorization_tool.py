"""Categorization Tool for the main orchestrator agent.

This module provides a tool that the main agent can call to:
1. Categorize the conversation (coding, architecture, social, etc.)
2. Determine the reasoning pattern (simple, opposing, multi_perspective, research)
3. Condense the user's intent into a focused prompt
4. Identify applicable directives for the subagent

The main agent calls this tool via function calling, making categorization
an explicit step in the orchestration rather than a hidden pre-processing step.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from models import CategorizationResult


# Tool definition for function calling
CATEGORIZATION_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "categorize_conversation",
        "description": """Analyze the conversation to determine:
1. The domain category (coding, architecture, social, financial, health, general, shell)
2. The reasoning pattern to use (simple, opposing_perspective, multi_perspective, research, sequential_refinement)
3. A condensed summary of the user's intent
4. Which directives from IF Prototype A1's ruleset apply

Call this tool to understand how to route and handle the conversation.""",
        "parameters": {
            "type": "object",
            "properties": {
                "analyze": {
                    "type": "boolean",
                    "description": "Set to true to analyze the current conversation",
                },
            },
            "required": ["analyze"],
        },
    },
}


@dataclass
class CategorizationToolResult:
    """Result from categorization tool execution."""
    category: str
    reasoning_pattern: str
    condensed_intent: str
    category_scores: Dict[str, float] = field(default_factory=dict)
    reasoning_scores: Dict[str, float] = field(default_factory=dict)
    applicable_directives: List[str] = field(default_factory=list)
    suggested_agent: str = ""
    debug_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_model(self) -> CategorizationResult:
        """Convert to pydantic model."""
        return CategorizationResult(
            category=self.category,
            reasoning_pattern=self.reasoning_pattern,
            condensed_intent=self.condensed_intent,
            category_scores=self.category_scores,
            reasoning_scores=self.reasoning_scores,
            applicable_directives=self.applicable_directives,
            debug_info=self.debug_info,
        )


class CategorizationTool:
    """Tool for categorizing conversations and determining routing.
    
    This tool is called by the main orchestrator agent to analyze
    incoming messages and determine how to handle them.
    """
    
    def __init__(self):
        self.name = "categorize_conversation"
        self.description = CATEGORIZATION_TOOL_DEFINITION["function"]["description"]
    
    async def run(
        self,
        messages: List[Dict[str, Any]],
    ) -> CategorizationToolResult:
        """Execute the categorization tool.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            CategorizationToolResult with full analysis
        """
        # Import here to avoid circular imports
        from categorization import categorize_combined, condense_intent
        from directive_injector import get_directive_injector

        # Run combined categorization — 3 API calls instead of 6
        category_scores, reasoning_scores, combined_debug = await categorize_combined(messages)
        category_debug = combined_debug
        reasoning_debug = combined_debug
        
        # Determine winners
        category = max(category_scores, key=category_scores.get)
        reasoning_pattern = max(reasoning_scores, key=reasoning_scores.get)
        
        # Get condensed intent
        condensed_intent = await condense_intent(messages)
        
        # Get applicable directives via directive_injector (canonical source)
        injector = get_directive_injector()
        directives = injector.get_directives_for_context(category, reasoning_pattern)
        applicable_directives = [
            f"Directive {d.id} - {d.title}: {d.content}" for d in directives
        ]
        
        # Map category to suggested agent
        agent_map = {
            "coding": "coding",
            "architecture": "architecture",
            "social": "social",
            "financial": "financial",
            "health": "health",
            "general": "general",
            "shell": "shell",
        }
        suggested_agent = agent_map.get(category, "general")
        
        return CategorizationToolResult(
            category=category,
            reasoning_pattern=reasoning_pattern,
            condensed_intent=condensed_intent,
            category_scores=category_scores,
            reasoning_scores=reasoning_scores,
            applicable_directives=applicable_directives,
            suggested_agent=suggested_agent,
            debug_info={
                "category_debug": category_debug,
                "reasoning_debug": reasoning_debug,
            },
        )
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """Get the OpenAI-compatible tool definition."""
        return CATEGORIZATION_TOOL_DEFINITION


# Singleton instance
categorization_tool = CategorizationTool()


async def execute_categorization_tool(
    messages: List[Dict[str, Any]],
) -> CategorizationToolResult:
    """Convenience function to execute categorization.
    
    Args:
        messages: List of conversation messages
        
    Returns:
        CategorizationToolResult
    """
    return await categorization_tool.run(messages)
