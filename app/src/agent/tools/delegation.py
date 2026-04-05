"""Delegation tools for the main agent's operational protocol.

These 4 tools implement the categorize → directives → condense → spawn pipeline
described in main_system_prompt.txt. The main agent calls them on every message
to route work to specialist subagents instead of handling everything itself.

Tools:
- categorize_conversation: Classify the message domain and reasoning pattern
- get_directives: Retrieve filtered directives for the detected domain
- condense_intent: Rewrite the user message as a focused specialist task
- spawn_subagent: Route to the appropriate specialist subagent
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx
from pydantic import Field
from rich.text import Text

from openhands.sdk.tool.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
)
from openhands.sdk import Tool, register_tool
from agent.tools.base import TextObservation

from config import CATEGORIZATION_MODEL
from orchestrator.executor import call_openrouter
from agent.prompts.loader import render_template
from agent.prompts.yaml_loader import load_yaml
from agent.tools.subagents import _resolve_directives, _run_subagent
from agent.tools.subagent_sdk import run_subagent_sdk

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState

logger = logging.getLogger(__name__)

_DELEGATION_CONFIG_PATH = Path(__file__).parent.parent / "prompts" / "specialists" / "delegation.yaml"


def _load_delegation_config() -> Dict[str, Any]:
    """Load delegation routing maps from YAML."""
    try:
        return load_yaml(_DELEGATION_CONFIG_PATH)
    except FileNotFoundError:
        logger.error(f"Delegation config not found: {_DELEGATION_CONFIG_PATH}")
        return {}


_delegation_config = _load_delegation_config()

CATEGORY_DIRECTIVE_MAP: Dict[str, List[str]] = _delegation_config.get("category_directive_map", {
    "general": ["core"],
})

CATEGORY_SPECIALIST_MAP: Dict[str, Optional[str]] = _delegation_config.get("category_specialist_map", {
    "general": None,
    "social": None,
})

PATTERN_SPECIALIST_OVERRIDES: Dict[str, str] = _delegation_config.get("pattern_specialist_overrides", {})


# =============================================================================
# Tool 1: categorize_conversation
# =============================================================================

CATEGORIZE_DESCRIPTION = """Classify the user's message to determine routing.

Returns: category, reasoning_pattern, condensed_intent, applicable_directives.
Call this FIRST on every message before deciding how to respond."""


class CategorizeConversationAction(Action):
    messages_text: str = Field(
        description="The user's message text to classify"
    )


class CategorizeConversationObservation(TextObservation):
    category: str = Field(default="general", description="Classified category")
    reasoning_pattern: str = Field(default="simple", description="Detected reasoning pattern")
    condensed_intent: str = Field(default="", description="1-2 sentence summary of intent")
    applicable_directives: str = Field(default="", description="Comma-separated directive IDs")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Categorization Result:\n", style="bold blue")
        content.append(f"  Category: {self.category}\n", style="green")
        content.append(f"  Pattern: {self.reasoning_pattern}\n", style="green")
        content.append(f"  Intent: {self.condensed_intent}\n", style="dim")
        content.append(f"  Directives: {self.applicable_directives}\n", style="dim")
        return content


class CategorizeConversationExecutor(ToolExecutor):
    def __call__(
        self,
        action: CategorizeConversationAction,
        conversation: Any = None,
    ) -> CategorizeConversationObservation:
        async def _run():
            prompt = render_template(
                "categorize.j2",
                messages_text=action.messages_text,
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    response = await call_openrouter(
                        model=CATEGORIZATION_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        tools=None,
                        http_client=http_client,
                    )
                text = response.content.strip()
                # Strip markdown fences if present
                if text.startswith("```"):
                    text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                    if text.startswith("json"):
                        text = text[4:].strip()
                data = json.loads(text)
                return CategorizeConversationObservation(
                    category=data.get("category", "general"),
                    reasoning_pattern=data.get("reasoning_pattern", "analytical"),
                    condensed_intent=data.get("condensed_intent", ""),
                    applicable_directives=data.get("applicable_directives", ""),
                )
            except Exception as e:
                logger.warning(f"[Delegation] Categorization failed: {e}, defaulting to general")
                return CategorizeConversationObservation(
                    category="general",
                    reasoning_pattern="analytical",
                    condensed_intent=action.messages_text[:200],
                    applicable_directives="",
                )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, _run()).result()
        return asyncio.run(_run())


class CategorizeConversationTool(ToolDefinition[CategorizeConversationAction, CategorizeConversationObservation]):
    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence["CategorizeConversationTool"]:
        return [
            cls(
                action_type=CategorizeConversationAction,
                observation_type=CategorizeConversationObservation,
                description=CATEGORIZE_DESCRIPTION,
                executor=CategorizeConversationExecutor(),
                annotations=ToolAnnotations(
                    title="categorize_conversation",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


register_tool("categorize_conversation", CategorizeConversationTool)


# =============================================================================
# Tool 2: get_directives
# =============================================================================

GET_DIRECTIVES_DESCRIPTION = """Retrieve filtered directives for a given category.

Maps the category from categorize_conversation to directive types and returns
a formatted directive block. Pure local logic — no LLM call."""


class GetDirectivesAction(Action):
    category: str = Field(description="Category from categorize_conversation")
    reasoning_pattern: str = Field(description="Reasoning pattern from categorize_conversation")


class GetDirectivesObservation(TextObservation):
    directives_block: str = Field(default="", description="Formatted directive text")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Directives Retrieved:\n", style="bold blue")
        content.append(self.directives_block[:500], style="dim")
        return content


class GetDirectivesExecutor(ToolExecutor):
    def __call__(
        self,
        action: GetDirectivesAction,
        conversation: Any = None,
    ) -> GetDirectivesObservation:
        directive_types = CATEGORY_DIRECTIVE_MAP.get(action.category, ["core"])
        directives_block = _resolve_directives(directive_types)
        return GetDirectivesObservation(directives_block=directives_block)


class GetDirectivesTool(ToolDefinition[GetDirectivesAction, GetDirectivesObservation]):
    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence["GetDirectivesTool"]:
        return [
            cls(
                action_type=GetDirectivesAction,
                observation_type=GetDirectivesObservation,
                description=GET_DIRECTIVES_DESCRIPTION,
                executor=GetDirectivesExecutor(),
                annotations=ToolAnnotations(
                    title="get_directives",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


register_tool("get_directives", GetDirectivesTool)


# =============================================================================
# Tool 3: condense_intent
# =============================================================================

CONDENSE_INTENT_DESCRIPTION = """Rewrite the user's message as a focused task for a specialist.

Strips social elements and produces a concise, actionable prompt. Uses a fast
LLM call. The output should be passed directly to spawn_subagent."""


class CondenseIntentAction(Action):
    last_message: str = Field(description="The user's last message")
    category: str = Field(description="Category from categorize_conversation")
    context_summary: str = Field(default="", description="Relevant context from conversation history")


class CondenseIntentObservation(TextObservation):
    condensed_prompt: str = Field(default="", description="Focused task description for specialist")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append("Condensed Intent:\n", style="bold blue")
        content.append(self.condensed_prompt, style="green")
        return content


class CondenseIntentExecutor(ToolExecutor):
    def __call__(
        self,
        action: CondenseIntentAction,
        conversation: Any = None,
    ) -> CondenseIntentObservation:
        async def _run():
            prompt = render_template(
                "condense_intent.j2",
                last_message=action.last_message,
                category=action.category,
                context_summary=action.context_summary,
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    response = await call_openrouter(
                        model=CATEGORIZATION_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        tools=None,
                        http_client=http_client,
                    )
                return CondenseIntentObservation(
                    condensed_prompt=response.content.strip()
                )
            except Exception as e:
                logger.warning(f"[Delegation] Intent condensation failed: {e}, using raw message")
                return CondenseIntentObservation(
                    condensed_prompt=action.last_message[:500]
                )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            with ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, _run()).result()
        return asyncio.run(_run())


class CondenseIntentTool(ToolDefinition[CondenseIntentAction, CondenseIntentObservation]):
    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence["CondenseIntentTool"]:
        return [
            cls(
                action_type=CondenseIntentAction,
                observation_type=CondenseIntentObservation,
                description=CONDENSE_INTENT_DESCRIPTION,
                executor=CondenseIntentExecutor(),
                annotations=ToolAnnotations(
                    title="condense_intent",
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=False,
                ),
            )
        ]


register_tool("condense_intent", CondenseIntentTool)


# =============================================================================
# Tool 4: spawn_subagent
# =============================================================================

SPAWN_SUBAGENT_DESCRIPTION = """Route a task to the appropriate specialist subagent.

Wraps the specialist spawning pipeline with automatic specialist selection
based on category. Pass the condensed_intent from condense_intent, NOT from
categorize_conversation."""


class SpawnSubagentAction(Action):
    category: str = Field(description="Category from categorize_conversation")
    reasoning_pattern: str = Field(description="Reasoning pattern from categorize_conversation")
    condensed_intent: str = Field(description="Focused task from condense_intent tool call")
    applicable_directives: str = Field(default="", description="Directive IDs from categorize_conversation")
    context: str = Field(default="", description="Background context for the specialist")


class SpawnSubagentObservation(TextObservation):
    result: str = Field(default="", description="The specialist's output")
    specialist_type: str = Field(default="", description="Which specialist was used")

    @property
    def visualize(self) -> Text:
        content = Text()
        content.append(f"Subagent Result ({self.specialist_type}):\n", style="bold blue")
        content.append(self.result[:500])
        return content


class SpawnSubagentExecutor(ToolExecutor):
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(
        self,
        action: SpawnSubagentAction,
        conversation: Any = None,
    ) -> SpawnSubagentObservation:
        specialist_slug = PATTERN_SPECIALIST_OVERRIDES.get(
            action.reasoning_pattern,
            CATEGORY_SPECIALIST_MAP.get(action.category),
        )

        if specialist_slug is None:
            return SpawnSubagentObservation(
                result="No specialist needed for this category. Respond directly.",
                specialist_type="none",
            )

        async def _run():
            from agent.specialists import get_specialist, render_specialist_prompt
            from models.router import select_model_for_specialist

            specialist = get_specialist(specialist_slug)
            if not specialist:
                return f"Unknown specialist: {specialist_slug}", specialist_slug

            directives = _resolve_directives(
                specialist.directive_types,
                action.applicable_directives,
            )

            system_prompt = render_specialist_prompt(
                specialist=specialist,
                task=action.condensed_intent,
                context=action.context,
                directives=directives,
            )

            # Route to concrete model via router
            model = await select_model_for_specialist(
                specialist.preset, action.condensed_intent,
            )

            from channels.status import send_status, StatusType
            await send_status(
                StatusType.SUBAGENT_SPAWNING,
                f"Spawning: {specialist_slug}",
                action.condensed_intent[:100],
                {"Model": model},
            )
            await send_status(
                StatusType.MODEL_SELECTED,
                f"Router: {model}",
                specialist.preset,
            )

            if specialist.agentic:
                result = await run_subagent_sdk(
                    system_prompt=system_prompt,
                    user_message=action.condensed_intent,
                    model=model,
                    max_turns=specialist.max_iterations,
                    chat_id=self.chat_id,
                    tool_names=specialist.tools,
                )
            else:
                async with httpx.AsyncClient(timeout=120.0) as http_client:
                    result = await _run_subagent(
                        system_prompt=system_prompt,
                        user_message=action.condensed_intent,
                        model=model,
                        max_turns=specialist.max_turns,
                        chat_id=self.chat_id,
                        http_client=http_client,
                    )

            logger.info(
                f"[Delegation] spawn_subagent: category={action.category} "
                f"specialist={specialist_slug} result_len={len(result)}"
            )

            from channels.status import send_status, StatusType
            await send_status(StatusType.SUBAGENT_COMPLETED, f"Completed: {specialist_slug}")

            return result, specialist_slug

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        # Propagate contextvars (platform context for status embeds) into the thread
        import contextvars
        ctx = contextvars.copy_context()

        if loop and loop.is_running():
            with ThreadPoolExecutor() as pool:
                result, slug = pool.submit(ctx.run, asyncio.run, _run()).result()
        else:
            result, slug = asyncio.run(_run())

        return SpawnSubagentObservation(result=result, specialist_type=slug)


class SpawnSubagentTool(ToolDefinition[SpawnSubagentAction, SpawnSubagentObservation]):
    @classmethod
    def create(
        cls,
        conv_state: "ConversationState | None" = None,
        chat_id: str = "",
        **params,
    ) -> Sequence["SpawnSubagentTool"]:
        return [
            cls(
                action_type=SpawnSubagentAction,
                observation_type=SpawnSubagentObservation,
                description=SPAWN_SUBAGENT_DESCRIPTION,
                executor=SpawnSubagentExecutor(chat_id=chat_id),
                annotations=ToolAnnotations(
                    title="spawn_subagent",
                    readOnlyHint=False,
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=True,
                ),
            )
        ]


register_tool("spawn_subagent", SpawnSubagentTool)


# =============================================================================
# Registration Helper
# =============================================================================

def get_delegation_tools(chat_id: str) -> List[Tool]:
    """Return the 4 delegation tool definitions."""
    return [
        Tool(name="categorize_conversation", params={}),
        Tool(name="get_directives", params={}),
        Tool(name="condense_intent", params={}),
        Tool(name="spawn_subagent", params={"chat_id": chat_id}),
    ]
