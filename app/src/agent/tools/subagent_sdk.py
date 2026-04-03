"""SDK-based agentic loop for specialist subagents.

Uses the OpenHands SDK Conversation.run() pattern to give agentic specialists
proper tool dispatch, stuck detection, and iterative execution.

Specialists with `agentic: true` in their YAML config are routed here instead
of the raw OpenRouter call loop in _run_subagent().
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import List

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation, MessageEvent, TextContent, Tool
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.event.conversation_error import ConversationErrorEvent

from config import LLM_API_KEY, LLM_BASE_URL, SPECIALIST_REASONING_EFFORT
from terminal.files import strip_files_line, log_file_refs, accumulate_file_refs
from agent.tools.terminal_tools import get_terminal_system_prompt

logger = logging.getLogger(__name__)

# Path to the pass-through system prompt template (contains just {{ system_prompt }})
_SYSTEM_PROMPT_TEMPLATE = Path(__file__).parent.parent / "prompts" / "system_prompt.j2"


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
        llm = LLM(
            usage_id=f"specialist-{chat_id}",
            model=sdk_model,
            base_url=LLM_BASE_URL,
            api_key=SecretStr(LLM_API_KEY),
            reasoning_effort=SPECIALIST_REASONING_EFFORT,
        )

        # Create Agent — reuses existing system_prompt.j2 pass-through template
        agent = Agent(
            llm=llm,
            tools=tools,
            mcp_config={},
            system_prompt_filename=str(_SYSTEM_PROMPT_TEMPLATE),
            system_prompt_kwargs={"system_prompt": full_prompt},
        )

        # Create ephemeral Conversation (no persistence)
        conversation = Conversation(
            agent=agent,
            workspace=os.getcwd(),
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

    except ConversationRunError as e:
        logger.error(f"[SDK Subagent] ConversationRunError: {e}")
        return f"Specialist encountered an error: {e}"

    except Exception as e:
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
