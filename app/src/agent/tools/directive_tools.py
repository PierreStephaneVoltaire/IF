
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

from config import (
    OPENROUTER_BASE_URL,
    OPENROUTER_API_KEY,
    DIRECTIVE_REWRITE_MODEL,
)
from storage.factory import get_directive_store
from agent.prompts.loader import render_template


def _rewrite_content_via_llm(raw_content: str) -> str:
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
    
    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    prompt = render_template("directive_rewrite.j2", raw_content=raw_content)
    payload = {
        "model": DIRECTIVE_REWRITE_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.3,
    }
    
    response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
    response.raise_for_status()
    
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def _add_directive(alpha: int, label: str, raw_content: str, types: List[str]) -> str:
    """Add a new directive.

    Alpha 0-1 are blocked. Content is rewritten through configured LLM before storage.
    Beta is auto-assigned.

    Args:
        alpha: Alpha tier (2-5 only)
        label: Directive label (UPPER_SNAKE_CASE)
        raw_content: Raw operator intent to be rewritten
        types: Domain types for this directive (e.g., ["code", "security"])

    Returns:
        Confirmation message with assigned directive ID
    """
    # Block alpha 0-1
    if alpha in (0, 1):
        return f"Error: Cannot add directives to alpha tier {alpha}. Tiers 0-1 are protected."

    # Validate types
    valid_types = {"core", "code", "architecture", "security", "health", "competition", "finance", "communication", "personality", "metacognition", "memory", "tool"}
    for t in types:
        if t not in valid_types:
            return f"Error: Invalid type '{t}'. Valid types: {sorted(valid_types)}"

    try:
        # Rewrite content through LLM
        rewritten_content = _rewrite_content_via_llm(raw_content)

        # Store the directive
        store = get_directive_store()
        directive = store.add(
            alpha=alpha,
            label=label,
            content=rewritten_content,
            types=types,
            created_by="operator"
        )

        return f"Directive {directive.alpha}-{directive.beta} added: {label}\nTypes: {', '.join(types)}\n\nContent: {rewritten_content}"

    except Exception as e:
        return f"Error adding directive: {str(e)}"


def _revise_directive(
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
    # Block alpha 0-1
    if alpha in (0, 1):
        return f"Error: Cannot revise directives in alpha tier {alpha}. Tiers 0-1 are protected."
    
    if not reason:
        return "Error: Reason for revision is required."
    
    try:
        # Rewrite content through LLM
        rewritten_content = _rewrite_content_via_llm(raw_content)
        
        # Revise the directive
        store = get_directive_store()
        new_directive = store.revise(
            alpha=alpha,
            beta=beta,
            content=rewritten_content,
            label=label,
            created_by="operator"
        )
        
        if not new_directive:
            return f"Error: Directive {alpha}-{beta} not found."
        
        return (
            f"Directive {alpha}-{beta} revised to version {new_directive.version}: "
            f"{new_directive.label}\n"
            f"Reason: {reason}\n\n"
            f"New content: {rewritten_content}"
        )
        
    except Exception as e:
        return f"Error revising directive: {str(e)}"


def _deactivate_directive(alpha: int, beta: int) -> str:
    """Deactivate a directive.
    
    Alpha 0-1 are blocked.
    
    Args:
        alpha: Alpha tier
        beta: Beta number
        
    Returns:
        Confirmation message
    """
    # Block alpha 0-1
    if alpha in (0, 1):
        return f"Error: Cannot deactivate directives in alpha tier {alpha}. Tiers 0-1 are protected."
    
    try:
        store = get_directive_store()
        success = store.deactivate(alpha, beta)
        
        if success:
            return f"Directive {alpha}-{beta} deactivated."
        else:
            return f"Error: Directive {alpha}-{beta} not found or could not be deactivated."
            
    except Exception as e:
        return f"Error deactivating directive: {str(e)}"


def _list_directives(alpha: Optional[int] = None) -> str:
    """List all directives.
    
    Args:
        alpha: Optional alpha tier filter
        
    Returns:
        Formatted list of directives
    """
    try:
        store = get_directive_store()
        directives = store.get_all(alpha=alpha)
        
        if not directives:
            if alpha is not None:
                return f"No directives found for alpha tier {alpha}."
            return "No directives found."
        
        lines = []
        for d in directives:
            lines.append(f"**{d.alpha}-{d.beta}** {d.label} (v{d.version})")
            lines.append(f"  {d.content[:100]}..." if len(d.content) > 100 else f"  {d.content}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error listing directives: {str(e)}"


# =============================================================================
# Action, Observation, Executor, and Tool Definitions
# =============================================================================

# --- DirectiveAddTool ---

class DirectiveAddAction(Action):
    alpha: int = Field(description="Alpha tier (2-5 only, 0-1 are protected)")
    label: str = Field(description="Directive label in UPPER_SNAKE_CASE")
    raw_content: str = Field(description="Raw operator intent to be rewritten into directive voice")
    types: List[str] = Field(description="Domain types (e.g., ['code', 'security']). Valid: core, code, architecture, security, health, competition, finance, communication, personality, metacognition, memory, tool")


class DirectiveAddObservation(TextObservation):
    pass


class DirectiveAddExecutor(ToolExecutor[DirectiveAddAction, DirectiveAddObservation]):
    def __call__(self, action: DirectiveAddAction, conversation=None) -> DirectiveAddObservation:
        result = _add_directive(
            alpha=action.alpha,
            label=action.label,
            raw_content=action.raw_content,
            types=action.types
        )
        return DirectiveAddObservation.from_text(result)


class DirectiveAddTool(ToolDefinition[DirectiveAddAction, DirectiveAddObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DirectiveAddTool"]:
        return [cls(
            description=(
                "Add a new behavioral directive. Alpha tiers 0-1 are protected. "
                "Content is automatically rewritten into directive voice via LLM. "
                "Beta number is auto-assigned. "
                "Types: Domain types for directive applies to (e.g., code, security, health). "
                "At least one type required."
            ),
            action_type=DirectiveAddAction,
            observation_type=DirectiveAddObservation,
            executor=DirectiveAddExecutor(),
        )]


register_tool("DirectiveAddTool", DirectiveAddTool)


# --- DirectiveReviseTool ---

class DirectiveReviseAction(Action):
    alpha: int = Field(description="Alpha tier")
    beta: int = Field(description="Beta number")
    raw_content: str = Field(description="New raw content to be rewritten into directive voice")
    label: Optional[str] = Field(default=None, description="New label (optional, defaults to existing)")
    reason: str = Field(description="Reason for revision (required)")


class DirectiveReviseObservation(TextObservation):
    pass


class DirectiveReviseExecutor(ToolExecutor[DirectiveReviseAction, DirectiveReviseObservation]):
    def __call__(self, action: DirectiveReviseAction, conversation=None) -> DirectiveReviseObservation:
        result = _revise_directive(
            alpha=action.alpha,
            beta=action.beta,
            raw_content=action.raw_content,
            label=action.label,
            reason=action.reason
        )
        return DirectiveReviseObservation.from_text(result)


class DirectiveReviseTool(ToolDefinition[DirectiveReviseAction, DirectiveReviseObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DirectiveReviseTool"]:
        return [cls(
            description=(
                "Revise an existing directive. Creates a new version; old version is "
                "marked inactive. Alpha tiers 0-1 are protected. Content is rewritten "
                "via LLM. Reason is required."
            ),
            action_type=DirectiveReviseAction,
            observation_type=DirectiveReviseObservation,
            executor=DirectiveReviseExecutor(),
        )]


register_tool("DirectiveReviseTool", DirectiveReviseTool)


# --- DirectiveDeactivateTool ---

class DirectiveDeactivateAction(Action):
    alpha: int = Field(description="Alpha tier")
    beta: int = Field(description="Beta number")


class DirectiveDeactivateObservation(TextObservation):
    pass


class DirectiveDeactivateExecutor(ToolExecutor[DirectiveDeactivateAction, DirectiveDeactivateObservation]):
    def __call__(self, action: DirectiveDeactivateAction, conversation=None) -> DirectiveDeactivateObservation:
        result = _deactivate_directive(
            alpha=action.alpha,
            beta=action.beta
        )
        return DirectiveDeactivateObservation.from_text(result)


class DirectiveDeactivateTool(ToolDefinition[DirectiveDeactivateAction, DirectiveDeactivateObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DirectiveDeactivateTool"]:
        return [cls(
            description=(
                "Deactivate a directive. Alpha tiers 0-1 are protected and cannot be deactivated."
            ),
            action_type=DirectiveDeactivateAction,
            observation_type=DirectiveDeactivateObservation,
            executor=DirectiveDeactivateExecutor(),
        )]


register_tool("DirectiveDeactivateTool", DirectiveDeactivateTool)


# --- DirectiveListTool ---

class DirectiveListAction(Action):
    alpha: Optional[int] = Field(default=None, description="Optional alpha tier filter (0-5)")


class DirectiveListObservation(TextObservation):
    pass


class DirectiveListExecutor(ToolExecutor[DirectiveListAction, DirectiveListObservation]):
    def __call__(self, action: DirectiveListAction, conversation=None) -> DirectiveListObservation:
        result = _list_directives(alpha=action.alpha)
        return DirectiveListObservation.from_text(result)


class DirectiveListTool(ToolDefinition[DirectiveListAction, DirectiveListObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["DirectiveListTool"]:
        return [cls(
            description=(
                "List all active directives, optionally filtered by alpha tier."
            ),
            action_type=DirectiveListAction,
            observation_type=DirectiveListObservation,
            executor=DirectiveListExecutor(),
        )]


register_tool("DirectiveListTool", DirectiveListTool)


# =============================================================================
# Tool Registration Function
# =============================================================================

def get_directive_tools() -> List[Tool]:
    """Return Tool specs for all directive tools, for use in Agent construction."""
    return [
        Tool(name="DirectiveAddTool"),
        Tool(name="DirectiveReviseTool"),
        Tool(name="DirectiveDeactivateTool"),
        Tool(name="DirectiveListTool"),
    ]
