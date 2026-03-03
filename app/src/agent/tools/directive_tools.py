"""Directive management tools for agent access.

These tools allow the agent to manage behavioral directives.
All content is rewritten through a configurable LLM before storage
to match the directive voice/style.

Tools:
- directive_add: Add a new directive (alpha 2-5 only)
- directive_revise: Create a new version of an existing directive
- directive_deactivate: Deactivate a directive
- directive_list: List all directives

Constraints:
- Alpha 0-1 directives are protected (Directive Zero-Five)
- Content is rewritten through LLM before storage
- All changes create new versions (immutable history)
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


# ============================================================================
# LLM Rewrite Integration (configurable model)
# ============================================================================

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
"""


def rewrite_directive_content(raw_content: str) -> str:
    """Call configured LLM via OpenRouter to rewrite raw content into directive voice.
    
    The model is configurable via DIRECTIVE_REWRITE_MODEL env var.
    
    Args:
        raw_content: Raw operator intent
        
    Returns:
        Rewritten directive text
        
    Raises:
        httpx.HTTPStatusError: If the API call fails
    """
    import httpx
    from config import (
        OPENROUTER_API_KEY,
        OPENROUTER_BASE_URL,
        OPENROUTER_HEADERS,
        DIRECTIVE_REWRITE_MODEL,
    )
    
    prompt = REWRITE_PROMPT.format(raw_content=raw_content)
    
    response = httpx.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers=OPENROUTER_HEADERS,
        json={
            "model": DIRECTIVE_REWRITE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
        },
        timeout=60.0,
    )
    
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


# ============================================================================
# Plain Python implementations (called by executors)
# ============================================================================

def _directive_add(alpha: int, label: str, raw_content: str) -> str:
    """Add a new directive.
    
    Alpha 0-1 are blocked. Content is rewritten through configured LLM before storage.
    Beta is auto-assigned.
    
    Args:
        alpha: Alpha tier (2-5 only)
        label: Directive label (UPPER_SNAKE_CASE)
        raw_content: Raw operator intent to be rewritten
        
    Returns:
        Confirmation message with assigned directive ID
    """
    # Block alpha 0-1
    if alpha in (0, 1):
        return "ERROR: Directive Zero-Five prohibits agent creation of alpha 0-1 directives."
    
    # Validate alpha range
    if alpha < 2 or alpha > 5:
        return f"ERROR: Alpha must be 2-5 for agent-created directives. Got: {alpha}"
    
    try:
        # Rewrite through configured LLM
        rewritten_content = rewrite_directive_content(raw_content)
        
        # Store
        from storage.factory import get_directive_store
        store = get_directive_store()
        directive = store.add(
            alpha=alpha,
            label=label,
            content=rewritten_content,
            created_by="agent"
        )
        
        return (
            f"Directive added: {directive.display_id} v{directive.version} {label}\n"
            f"Content: {rewritten_content[:200]}..."
        )
    except Exception as e:
        return f"Error adding directive: {str(e)}"


def _directive_revise(
    alpha: int, 
    beta: int, 
    raw_content: str,
    label: Optional[str] = None, 
    reason: str = ""
) -> str:
    """Revise an existing directive (creates new version).
    
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
    """
    # Block alpha 0-1 content changes
    if alpha in (0, 1):
        return "ERROR: Directive Zero-Five prohibits agent modification of alpha 0-1 directives."
    
    if not reason:
        return "ERROR: Reason is required for directive revisions."
    
    try:
        from storage.factory import get_directive_store
        store = get_directive_store()
        
        # Check if directive exists
        existing = store.get(alpha, beta)
        if not existing:
            return f"ERROR: Directive {alpha}-{beta} not found."
        
        # Rewrite content through configured LLM
        rewritten_content = rewrite_directive_content(raw_content)
        
        # Create new version
        new_version = store.revise(
            alpha=alpha,
            beta=beta,
            content=rewritten_content,
            label=label,
            created_by="agent"
        )
        
        if not new_version:
            return f"ERROR: Could not revise directive {alpha}-{beta}."
        
        return (
            f"Directive revised: {new_version.display_id} v{new_version.version}\n"
            f"Reason: {reason}"
        )
    except Exception as e:
        return f"Error revising directive: {str(e)}"


def _directive_deactivate(alpha: int, beta: int) -> str:
    """Deactivate a directive.
    
    Alpha 0-1 are blocked.
    
    Args:
        alpha: Alpha tier
        beta: Beta number
        
    Returns:
        Confirmation message
    """
    # Block alpha 0-1
    if alpha == 0 and beta == 1:
        return "ERROR: Directive 0-1 (Memory Preservation) cannot be deactivated."
    if alpha in (0, 1):
        return "ERROR: Directive Zero-Five prohibits agent deactivation of alpha 0-1 directives."
    
    try:
        from storage.factory import get_directive_store
        store = get_directive_store()
        success = store.deactivate(alpha=alpha, beta=beta)
        
        if not success:
            return f"ERROR: Could not deactivate directive {alpha}-{beta}. Not found or blocked."
        
        return f"Directive deactivated: {alpha}-{beta}"
    except Exception as e:
        return f"Error deactivating directive: {str(e)}"


def _directive_list(alpha: Optional[int] = None) -> str:
    """List all directives.
    
    Args:
        alpha: Optional alpha tier filter
        
    Returns:
        Formatted list of directives
    """
    try:
        from storage.factory import get_directive_store
        store = get_directive_store()
        directives = store.get_all(alpha=alpha)
        
        if not directives:
            if alpha is not None:
                return f"No directives found for alpha={alpha}."
            return "No directives found."
        
        output = [f"Directives ({len(directives)} total):", ""]
        for d in directives:
            output.append(f"{d.display_id} v{d.version}  {d.label}")
            output.append(f"  Created by: {d.created_by}")
            output.append(f"  Created: {d.created_at[:10]}")
            output.append("")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error listing directives: {str(e)}"


# ============================================================================
# Action classes
# ============================================================================

class DirectiveAddAction(Action):
    alpha: int = Field(
        description="Alpha tier (2-5 only for agent creation)"
    )
    label: str = Field(
        description="Directive label in UPPER_SNAKE_CASE"
    )
    raw_content: str = Field(
        description="Raw operator intent to be rewritten into directive voice"
    )


class DirectiveReviseAction(Action):
    alpha: int = Field(description="Alpha tier")
    beta: int = Field(description="Beta number")
    raw_content: str = Field(
        description="New raw content (rewritten through LLM)"
    )
    label: Optional[str] = Field(
        default=None, 
        description="New label (optional)"
    )
    reason: str = Field(
        description="Reason for revision (required)"
    )


class DirectiveDeactivateAction(Action):
    alpha: int = Field(description="Alpha tier")
    beta: int = Field(description="Beta number")


class DirectiveListAction(Action):
    alpha: Optional[int] = Field(
        default=None, 
        description="Optional alpha tier filter"
    )


# ============================================================================
# Observation classes
# ============================================================================

class DirectiveAddObservation(Observation):
    pass


class DirectiveReviseObservation(Observation):
    pass


class DirectiveDeactivateObservation(Observation):
    pass


class DirectiveListObservation(Observation):
    pass


# ============================================================================
# Executor classes
# ============================================================================

class DirectiveAddExecutor(
    ToolExecutor[DirectiveAddAction, DirectiveAddObservation]
):
    def __call__(
        self, 
        action: DirectiveAddAction, 
        conversation=None
    ) -> DirectiveAddObservation:
        result = _directive_add(action.alpha, action.label, action.raw_content)
        return DirectiveAddObservation.from_text(result)


class DirectiveReviseExecutor(
    ToolExecutor[DirectiveReviseAction, DirectiveReviseObservation]
):
    def __call__(
        self, 
        action: DirectiveReviseAction, 
        conversation=None
    ) -> DirectiveReviseObservation:
        result = _directive_revise(
            action.alpha, 
            action.beta, 
            action.raw_content, 
            action.label, 
            action.reason
        )
        return DirectiveReviseObservation.from_text(result)


class DirectiveDeactivateExecutor(
    ToolExecutor[DirectiveDeactivateAction, DirectiveDeactivateObservation]
):
    def __call__(
        self, 
        action: DirectiveDeactivateAction, 
        conversation=None
    ) -> DirectiveDeactivateObservation:
        result = _directive_deactivate(action.alpha, action.beta)
        return DirectiveDeactivateObservation.from_text(result)


class DirectiveListExecutor(
    ToolExecutor[DirectiveListAction, DirectiveListObservation]
):
    def __call__(
        self, 
        action: DirectiveListAction, 
        conversation=None
    ) -> DirectiveListObservation:
        result = _directive_list(action.alpha)
        return DirectiveListObservation.from_text(result)


# ============================================================================
# ToolDefinition classes
# ============================================================================

class DirectiveAddTool(
    ToolDefinition[DirectiveAddAction, DirectiveAddObservation]
):
    @classmethod
    def create(
        cls, 
        conv_state=None, 
        **params
    ) -> Sequence["DirectiveAddTool"]:
        return [cls(
            description=(
                "Add a new directive. Alpha must be 2-5 (alpha 0-1 blocked). "
                "Content is rewritten into directive voice before storage. "
                "Beta is auto-assigned."
            ),
            action_type=DirectiveAddAction,
            observation_type=DirectiveAddObservation,
            executor=DirectiveAddExecutor(),
        )]


class DirectiveReviseTool(
    ToolDefinition[DirectiveReviseAction, DirectiveReviseObservation]
):
    @classmethod
    def create(
        cls, 
        conv_state=None, 
        **params
    ) -> Sequence["DirectiveReviseTool"]:
        return [cls(
            description=(
                "Revise an existing directive (creates new version). Alpha 0-1 blocked. "
                "Content is rewritten through LLM. Old version is preserved for history. "
                "Reason is required."
            ),
            action_type=DirectiveReviseAction,
            observation_type=DirectiveReviseObservation,
            executor=DirectiveReviseExecutor(),
        )]


class DirectiveDeactivateTool(
    ToolDefinition[DirectiveDeactivateAction, DirectiveDeactivateObservation]
):
    @classmethod
    def create(
        cls, 
        conv_state=None, 
        **params
    ) -> Sequence["DirectiveDeactivateTool"]:
        return [cls(
            description=(
                "Deactivate a directive. Alpha 0-1 blocked. "
                "Directive 0-1 (Memory Preservation) can never be deactivated by agent."
            ),
            action_type=DirectiveDeactivateAction,
            observation_type=DirectiveDeactivateObservation,
            executor=DirectiveDeactivateExecutor(),
        )]


class DirectiveListTool(
    ToolDefinition[DirectiveListAction, DirectiveListObservation]
):
    @classmethod
    def create(
        cls, 
        conv_state=None, 
        **params
    ) -> Sequence["DirectiveListTool"]:
        return [cls(
            description=(
                "List all directives. Optionally filter by alpha tier."
            ),
            action_type=DirectiveListAction,
            observation_type=DirectiveListObservation,
            executor=DirectiveListExecutor(),
        )]


# ============================================================================
# Registration
# ============================================================================

register_tool("DirectiveAddTool", DirectiveAddTool)
register_tool("DirectiveReviseTool", DirectiveReviseTool)
register_tool("DirectiveDeactivateTool", DirectiveDeactivateTool)
register_tool("DirectiveListTool", DirectiveListTool)


def get_directive_tools() -> List[Tool]:
    """Return Tool specs for all directive tools, for use in Agent construction."""
    return [
        Tool(name="DirectiveAddTool"),
        Tool(name="DirectiveReviseTool"),
        Tool(name="DirectiveDeactivateTool"),
        Tool(name="DirectiveListTool"),
    ]
