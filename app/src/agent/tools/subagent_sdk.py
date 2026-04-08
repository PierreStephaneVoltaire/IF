"""SDK-based agentic loop for specialist subagents.

Uses the OpenHands SDK Conversation.run() pattern to give agentic specialists
proper tool dispatch, stuck detection, and iterative execution.

Specialists with `agentic: true` in their YAML config are routed here instead
of the raw OpenRouter call loop in _run_subagent().

Skills are loaded per-specialist (not globally) to avoid context bloat.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, AgentContext, Conversation, MessageEvent, TextContent, Tool
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.event.conversation_error import ConversationErrorEvent

from config import LLM_API_KEY, LLM_BASE_URL, SPECIALIST_REASONING_EFFORT
from sandbox import get_local_sandbox
from files import strip_files_line, log_file_refs, accumulate_file_refs
from agent.tools.terminal_tools import get_terminal_system_prompt
from agent.skills import load_skills_for_specialist

logger = logging.getLogger(__name__)

# Path to the pass-through system prompt template (contains just {{ system_prompt }})
_SYSTEM_PROMPT_TEMPLATE = Path(__file__).parent.parent / "prompts" / "system_prompt.j2"


def _get_max_output_tokens(model_id: str) -> int | None:
    """Look up max_output_tokens for a model from the registry.

    Returns None if the model isn't in the registry, letting the SDK decide.
    The model_id should be the clean OpenRouter ID (no 'openrouter/' prefix).
    """
    try:
        from storage.factory import get_model_registry
        registry = get_model_registry()
        info = registry.get(model_id)
        if info and info.max_output_tokens:
            return info.max_output_tokens
    except Exception:
        pass
    return None


def resolve_specialist_tools(chat_id: str, tool_names: List[str]) -> List[Tool]:
    """Resolve specialist YAML tool names to SDK Tool objects.

    Each tool name maps to a registered ToolDefinition via register_tool().
    The SDK resolves the name to the actual tool at agent init time.

    Args:
        chat_id: Chat ID for terminal container scoping
        tool_names: Tool names from specialist YAML config

    Returns:
        List of Tool specs for Agent initialization
    """
    return [Tool(name=name, params={"chat_id": chat_id}) for name in tool_names]


async def run_subagent_sdk(
    system_prompt: str,
    user_message: str,
    model: str,
    max_turns: int,
    chat_id: str,
    tool_names: List[str],
    skill_names: List[str] | None = None,
    original_preset: str | None = None,
) -> str:
    """Run a specialist using the OpenHands SDK agentic loop.

    The specialist's Jinja2 prompt template (agent.j2) is already rendered
    into system_prompt by the caller via render_specialist_prompt(). This
    function wraps it in the SDK's system_prompt.j2 pass-through template.

    Args:
        system_prompt: Pre-rendered specialist prompt (includes directives, context, task)
        user_message: The condensed intent/task from the main agent
        model: OpenRouter model/preset slug
        max_turns: Maximum iterations for the agentic loop
        chat_id: Chat ID for terminal container scoping
        tool_names: Tool names from specialist config (respected exactly)
        skill_names: AgentSkills names to load for this specialist (loaded at spawn time)

    Returns:
        Specialist response text (with FILES: metadata stripped)
    """
    conversation = None
    try:
        # Convert model to OpenRouter format
        sdk_model = model
        if not sdk_model.startswith("openrouter/"):
            sdk_model = f"openrouter/{sdk_model}"

        # Append terminal system prompt for tool usage guidance
        terminal_section = get_terminal_system_prompt()
        full_prompt = f"{system_prompt}\n\n{terminal_section}"

        # Build tools from specialist config
        tools = resolve_specialist_tools(chat_id, tool_names)
        logger.info(f"[SDK Subagent] Starting: model={sdk_model} | tools={tool_names} | max_turns={max_turns}")

        # Create LLM
        max_output_tokens = _get_max_output_tokens(model)
        llm = LLM(
            usage_id=f"specialist-{chat_id}",
            model=sdk_model,
            base_url=LLM_BASE_URL,
            api_key=SecretStr(LLM_API_KEY),
            reasoning_effort=SPECIALIST_REASONING_EFFORT,
            max_output_tokens=max_output_tokens,
        )

        # Load skills for this specialist (per-specialist, not global)
        skills = load_skills_for_specialist(skill_names or [])
        if skills:
            logger.info(f"[SDK Subagent] Loaded {len(skills)} skills: {skill_names}")

        # Create Agent with optional AgentContext for skills
        agent_context = AgentContext(
            skills=skills,
            load_user_skills=False,
            load_public_skills=False,
        ) if skills else None

        agent = Agent(
            llm=llm,
            tools=tools,
            mcp_config={},
            agent_context=agent_context,
            system_prompt_filename=str(_SYSTEM_PROMPT_TEMPLATE),
            system_prompt_kwargs={"system_prompt": full_prompt},
        )

        # Create ephemeral Conversation (no persistence)
        conversation = Conversation(
            agent=agent,
            workspace=get_local_sandbox().get_workspace(chat_id),
            max_iteration_per_run=max_turns,
            stuck_detection=True,
            visualizer=None,
            delete_on_close=False,
        )

        conversation.send_message(user_message)

        # Run in executor — conversation.run() is synchronous
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, conversation.run)

        # Extract response based on execution status
        return _extract_response(conversation, max_turns, chat_id)

    except (ConversationRunError, Exception) as e:
        from models.router import is_context_limit_error, select_model_by_context
        if original_preset and is_context_limit_error(e):
            fallback = select_model_by_context(original_preset)
            if fallback and fallback != model:
                logger.warning(f"[SDK Subagent] Context limit, retrying with {fallback}")
                return await run_subagent_sdk(
                    system_prompt, user_message, fallback, max_turns,
                    chat_id, tool_names, original_preset=None,
                )
        if isinstance(e, ConversationRunError):
            logger.error(f"[SDK Subagent] ConversationRunError: {e}")
            return f"Specialist encountered an error: {e}"
        logger.error(f"[SDK Subagent] Unexpected error: {e}", exc_info=True)
        return f"Specialist error: {type(e).__name__}: {e}"

    finally:
        if conversation:
            try:
                conversation.close()
            except Exception as e:
                logger.debug(f"[SDK Subagent] Cleanup error: {e}")


def _extract_response(conversation, max_turns: int, chat_id: str) -> str:
    """Extract the specialist's response from SDK conversation events.

    Handles FINISHED, STUCK, and ERROR states. Strips FILES: metadata
    from the response text.

    Args:
        conversation: The SDK Conversation object
        max_turns: Max turns configured (for error messages)
        chat_id: Chat ID for logging

    Returns:
        Specialist response text with FILES: metadata stripped
    """
    events = conversation.state.events
    status = conversation.state.execution_status

    # Log tool invocations for observability
    for event in events:
        if hasattr(event, "tool_call") and event.tool_call:
            tc = event.tool_call
            tool_name = getattr(tc, "name", getattr(tc, "function", "unknown"))
            tool_args = str(getattr(tc, "arguments", getattr(tc, "args", {})))[:200]
            logger.debug(f"[SDK Subagent] tool_call: {tool_name} | args={tool_args}")

    # Emit tool execution status embeds (batched after run completes)
    try:
        import asyncio as _aio
        from channels.status import send_status, StatusType
        for event in events:
            if hasattr(event, "tool_call") and event.tool_call:
                tc = event.tool_call
                tool_name = getattr(tc, "name", getattr(tc, "function", "unknown"))
                _aio.get_event_loop().run_until_complete(
                    send_status(StatusType.TOOL_STARTED, f"Tool: {tool_name}")
                )
    except Exception:
        pass

    if status == ConversationExecutionStatus.STUCK:
        logger.warning(f"[SDK Subagent] Specialist got stuck after {max_turns} iterations")
        context = _get_recent_context(events)
        return f"Specialist got stuck in a repetitive loop and was stopped.\n\nLast actions:\n{context}"

    if status == ConversationExecutionStatus.ERROR:
        logger.error(f"[SDK Subagent] Specialist ended with ERROR after {max_turns} iterations")
        error_detail = _get_error_detail(events)
        return f"Specialist encountered an error after {max_turns} iterations.\n\n{error_detail}"

    # Find the last MessageEvent from the agent
    last_agent_message = None
    for event in events:
        if isinstance(event, MessageEvent) and event.source == "agent":
            last_agent_message = event

    if not last_agent_message:
        logger.warning(f"[SDK Subagent] No final MessageEvent after {max_turns} iterations (status={status})")
        context = _get_recent_context(events)
        return f"Specialist did not produce a final response after {max_turns} iterations.\n\nLast actions:\n{context}"

    # Extract text content
    content = " ".join(
        c.text
        for c in last_agent_message.llm_message.content
        if isinstance(c, TextContent)
    )

    # Strip FILES: metadata
    cleaned, refs = strip_files_line(content)
    if refs:
        log_file_refs(chat_id, refs)
        accumulate_file_refs(chat_id, refs)
        logger.info(f"[SDK Subagent] Extracted {len(refs)} file references: {[r.path for r in refs]}")

    return cleaned or ""


def _get_recent_context(events, max_events: int = 6) -> str:
    """Get a summary of recent actions/observations for stuck/error context.

    Args:
        events: List of SDK events
        max_events: Number of recent events to include

    Returns:
        Formatted string of recent events
    """
    recent = events[-max_events:]
    lines = []
    for event in recent:
        if hasattr(event, "tool_name"):
            action_str = getattr(event, "action", "")
            if action_str:
                action_str = str(action_str)[:200]
            lines.append(f"- [{event.tool_name}] {action_str}")
        elif hasattr(event, "observation") and event.observation:
            obs_str = str(event.observation)[:200]
            lines.append(f"  → {obs_str}")
        elif isinstance(event, MessageEvent) and event.source == "agent":
            text = " ".join(
                c.text for c in event.llm_message.content
                if isinstance(c, TextContent)
            )[:200]
            lines.append(f"- [agent] {text}")
    return "\n".join(lines) if lines else "(no recent events)"


def _get_error_detail(events) -> str:
    """Extract error details from ConversationErrorEvent in events.

    Args:
        events: List of SDK events

    Returns:
        Error detail string
    """
    for event in reversed(events):
        if isinstance(event, ConversationErrorEvent):
            return f"{event.detail} (code: {event.code})"
    return "No error details available"
