
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



REWRITE_PROMPT = """You are rewriting a directive for an AI agent's behavioral system.

The directive system uses terse, imperative prose. No filler. No corporate warmth.
Each directive reads like a standing order — clear conditions, clear behavior, 
clear exceptions.

Reference style (do not copy, match the voice):
---
When the operator submits a message for review before sending,
treat it as a critical verification task. Verify all factual
claims against available knowledge and tools. Flag statements
that are incorrect, misleading, or unsupported — even if the
operator appears confident.
---

Rewrite the following into a single directive in that voice. 
Output the directive text only, no preamble, no explanation.

Operator intent:
{raw_content}
Call configured LLM via OpenRouter to rewrite raw content into directive voice.
    
    The model is configurable via DIRECTIVE_REWRITE_MODEL env var.
    
    Args:
        raw_content: Raw operator intent
        
    Returns:
        Rewritten directive text
        
    Raises:
        httpx.HTTPStatusError: If the API call fails
Add a new directive.
    
    Alpha 0-1 are blocked. Content is rewritten through configured LLM before storage.
    Beta is auto-assigned.
    
    Args:
        alpha: Alpha tier (2-5 only)
        label: Directive label (UPPER_SNAKE_CASE)
        raw_content: Raw operator intent to be rewritten
        
    Returns:
        Confirmation message with assigned directive ID
Revise an existing directive (creates new version).
    
    Alpha 0-1 content changes are blocked. Content is rewritten through 
    configured LLM before storing. Old version is marked inactive.
    
    Args:
        alpha: Alpha tier
        beta: Beta number
        raw_content: New raw content (rewritten through LLM)
        label: New label (optional, defaults to existing)
        reason: Reason for revision (required)
        
    Returns:
        Confirmation message
Deactivate a directive.
    
    Alpha 0-1 are blocked.
    
    Args:
        alpha: Alpha tier
        beta: Beta number
        
    Returns:
        Confirmation message
List all directives.
    
    Args:
        alpha: Optional alpha tier filter
        
    Returns:
        Formatted list of directives
Return Tool specs for all directive tools, for use in Agent construction."""
    return [
        Tool(name="DirectiveAddTool"),
        Tool(name="DirectiveReviseTool"),
        Tool(name="DirectiveDeactivateTool"),
        Tool(name="DirectiveListTool"),
    ]
