"""Agent session management for OpenHands integration.

This module implements Step 5 of the routing pipeline:
- System prompt assembly (base + memory + preset-specific)
- MCP server resolution
- Agent session creation/reuse
- Message passing to agent via OpenHands SDK
- Response handling and attachment scanning
- Operator context auto-retrieval from user facts
"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from pydantic import SecretStr

from openhands.sdk import LLM, Agent, Conversation , MessageEvent, TextContent

from config import (
    PRESET_MCP_MAP,
    SANDBOX_PATH,
    MEMORY_DB_PATH,
    PERSISTENCE_DIR,
    LLM_API_KEY,
    LLM_BASE_URL,
)
from presets.loader import PresetManager
from mcp_servers.config import resolve_mcp_config
from agent.memory_tools import get_memory_tools
from agent.tools.user_facts import get_user_facts_tools, set_session_context


logger = logging.getLogger(__name__)


# Path to pondering addendum file
PONDERING_ADDENDUM_PATH = Path(__file__).parent / "prompts" / "pondering_addendum.md"


def load_pondering_addendum() -> str:
    """Load the pondering mode addendum.
    
    Returns:
        Content of pondering_addendum.md or empty string if not found
    """
    try:
        if PONDERING_ADDENDUM_PATH.exists():
            return PONDERING_ADDENDUM_PATH.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to load pondering addendum: {e}")
    return ""


@dataclass
class AgentSession:
    """Represents an active agent session."""
    session_id: str
    preset_slug: str
    model: str  # OpenRouter model ID
    system_prompt: str
    mcp_servers: List[str]
    created_at: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "session_id": self.session_id,
            "preset_slug": self.preset_slug,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "mcp_servers": self.mcp_servers,
            "created_at": self.created_at.isoformat(),
            "message_count": self.message_count,
        }


@dataclass
class AgentResponse:
    """Response from agent execution."""
    content: str
    attachments: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize response to dictionary."""
        return {
            "content": self.content,
            "attachments": self.attachments,
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
        }


def resolve_mcp_servers(preset_slug: str) -> List[str]:
    """Resolve MCP servers for a preset.
    
    Merges __all__ servers with preset-specific servers.
    
    Args:
        preset_slug: Preset identifier
        
    Returns:
        List of MCP server keys
    """
    # Get global servers
    global_servers = PRESET_MCP_MAP.get("__all__", [])
    
    # Get preset-specific servers
    preset_servers = PRESET_MCP_MAP.get(preset_slug, [])
    
    # Merge and deduplicate
    all_servers = list(set(global_servers + preset_servers))
    
    return all_servers


def get_operator_context(messages: List[Dict[str, Any]]) -> str:
    """Retrieve relevant operator context for system prompt.
    
    Searches user facts based on the last user message.
    This runs synchronously - ChromaDB is local and fast.
    
    Args:
        messages: Conversation messages
        
    Returns:
        Formatted operator context block, or empty string if no matches
    """
    from memory.user_facts import (
        FactCategory,
        FactSource,
        get_user_fact_store
    )
    
    # Extract last user message
    last_user_msg = None
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                last_user_msg = " ".join(text_parts)
            else:
                last_user_msg = content
            break
    
    if not last_user_msg:
        return ""
    
    try:
        store = get_user_fact_store()
        
        # Search for relevant facts
        facts = store.search(last_user_msg, limit=5)
        
        # Search for model assessments separately
        assessments = store.search(
            last_user_msg,
            category=FactCategory.MODEL_ASSESSMENT,
            limit=3
        )
        
        # Deduplicate by ID
        all_facts = {f.id: f for f in facts + assessments}.values()
        
        if not all_facts:
            return ""
        
        # Format context block
        lines = ["═══ OPERATOR CONTEXT ═══"]
        for f in all_facts:
            source_tag = "observed" if f.source in (
                FactSource.MODEL_OBSERVED, FactSource.MODEL_ASSESSED
            ) else "stated"
            lines.append(f"- [{f.category.value}] [{source_tag}] {f.content} ({f.updated_at[:10]})")
        lines.append("══════════════════════")
        return "\n".join(lines)
        
    except Exception as e:
        logger.warning(f"Failed to get operator context: {e}")
        return ""


def assemble_system_prompt(
    preset_slug: str,
    preset_manager: PresetManager,
    memory_context: Optional[str] = None,
    operator_context: Optional[str] = None
) -> str:
    """Assemble the complete system prompt for a preset.
    
    Combines:
    1. Base system prompt from preset
    2. Operator context block (auto-retrieved from user facts)
    3. Memory context block (if provided)
    4. Preset-specific instructions (sandbox rules, etc.)
    
    Args:
        preset_slug: Preset identifier
        preset_manager: Manager with preset data
        memory_context: Optional memory context to inject
        operator_context: Optional operator context from user facts
        
    Returns:
        Complete system prompt string
    """
    # Get preset data
    preset = preset_manager.get_preset(preset_slug)
    if not preset:
        logger.warning(f"Preset not found: {preset_slug}, using default")
        base_prompt = "You are a helpful AI assistant."
    else:
        base_prompt = preset.description
    
    # Start with base prompt
    prompt_parts = [base_prompt]
    
    # Add operator context if provided (from user facts)
    if operator_context:
        prompt_parts.append(f"\n{operator_context}\n")
    
    # Add memory protocol
    memory_protocol = """
MEMORY PROTOCOL:
You have access to a persistent memory store containing facts
about the operator — preferences, life events, profession,
skill levels, opinions, mental state, and similar context.

USE memory_search WHEN:
  - The conversation would benefit from knowing the operator's
    background, preferences, or history.
  - The operator references something previously discussed
    across sessions.
  - You need to tailor tone, depth, or framing to the operator's
    known level of understanding.

DO NOT USE memory_search WHEN:
  - The task is purely technical with no personalization benefit
    (code generation, architecture review, shell commands).
  - The operator's background is irrelevant to the task.

USE memory_add WHEN:
  - The operator shares personal information with cross-session
    value (preferences, life events, opinions).
  - The operator explicitly asks you to remember something.
  - A pattern emerges across multiple interactions that would
    benefit future sessions.

DO NOT USE memory_add FOR:
  - Task-specific details (code snippets, debugging context).
  - Transient conversation artifacts.
  - Information the operator might want to forget.
"""
    prompt_parts.append(memory_protocol)
    
    # Add memory context if provided
    if memory_context:
        prompt_parts.append(f"\nRELEVANT MEMORIES:\n{memory_context}\n")
    
    # Add preset-specific instructions
    mcp_servers = resolve_mcp_servers(preset_slug)
    
    # Load pondering addendum if active preset is pondering
    if preset_slug == "pondering":
        pondering_addendum = load_pondering_addendum()
        if pondering_addendum:
            logger.info(f"[Session] Loaded pondering addendum ({len(pondering_addendum)} chars)")
            prompt_parts.append(f"\n{pondering_addendum}\n")
    
    # Sandbox instructions for presets with sandbox access
    if "sandbox" in mcp_servers:
        sandbox_instruction = f"""
SANDBOX FILE PROTOCOL:
If your response includes code exceeding 5 lines, do not embed
it in the message body. Write it to a file in the sandbox directory
({SANDBOX_PATH}) and reference the file path. The file will be
delivered as an attachment.

File naming: Use descriptive names with timestamps if needed.
Example: solution.py, config.json, architecture_diagram.md
"""
        prompt_parts.append(sandbox_instruction)
    
    return "\n".join(prompt_parts)


def get_model_for_preset(preset_slug: str, preset_manager: PresetManager) -> str:
    """Get the OpenRouter model ID for a preset.
    
    Args:
        preset_slug: Preset identifier
        preset_manager: Manager with preset data
        
    Returns:
        OpenRouter model ID
    """
    preset = preset_manager.get_preset(preset_slug)
    if not preset:
        # Fallback to a capable general model
        return "anthropic/claude-3.5-sonnet"
    
    # Get model from preset
    model = preset.model
    if model:
        return model
    
    # Fallback
    return "anthropic/claude-3.5-sonnet"


async def execute_agent(
    session: AgentSession,
    messages: List[Dict[str, str]],
    http_client: Any,
    stream: bool = False
) -> AgentResponse:
    """Execute agent with messages using OpenHands SDK.
    
    This implementation uses the OpenHands Agent and Conversation classes
    for full MCP server access, tool use, and conversation persistence.
    
    Args:
        session: Agent session configuration
        messages: Conversation messages
        http_client: HTTP client (unused, kept for API compatibility)
        stream: Whether to stream response (not implemented yet)
        
    Returns:
        AgentResponse with content and attachments
    """
    try:
        # Convert the preset model to OpenRouter format
        # The preset.model is like "@preset/architecture", we need "openrouter/@preset/architecture"
        model = session.model
        if not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        
        # Create OpenHands LLM instance
        llm = LLM(
            usage_id="agent",
            model=model,
            base_url=LLM_BASE_URL,
            api_key=SecretStr(LLM_API_KEY),
        )
        print(f"[Agent] Using model: {model}")
        # Get MCP config for this preset
        mcp_config = resolve_mcp_config(session.preset_slug)
        print(f"[Agent] Resolved MCP servers: {list(mcp_config.keys())}")
        # Get memory tools
        tools = get_memory_tools()
        # Get user facts tools
        tools.extend(get_user_facts_tools())
        print(f"[Agent] Loaded memory tools and user facts tools")
        # Create OpenHands Agent
        agent = Agent(
            llm=llm,
            tools=tools,
            mcp_config=mcp_config,
        )
        print("[Agent] Agent created with system prompt:")
        # Create or restore Conversation for persistence
        # OpenHands Conversation expects a UUID object, not a string
        conversation_id_uuid = uuid.uuid4()
        conversation = Conversation(
            agent=agent,
            workspace=os.getcwd(),
            persistence_dir=PERSISTENCE_DIR,
            conversation_id=conversation_id_uuid,
        )
        print(f"[Agent] Conversation initialized with ID: {session.session_id}")
        # Format messages for the agent
        # OpenHands expects messages in a specific format
        # The system prompt is already included in session.system_prompt
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            conversation.send_message(content)
        
        conversation.run()
        events = conversation.state.events
        last_agent_message:MessageEvent = None
        for event in events:
          if isinstance(event, MessageEvent) and event.source == "agent":
            last_agent_message = event
       
        content = ""
        if last_agent_message:
            content = " ".join(
                    c.text
                    for c in last_agent_message.llm_message.content
                    if isinstance(c, TextContent)
                )
        # Scan sandbox for attachments
        attachments = scan_sandbox_for_attachments()
        print(f"[Agent] Found attachments: {attachments}")
        return AgentResponse(
            content=content,
            attachments=attachments,
            finish_reason="stop"
        )
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return AgentResponse(
            content=f"Error executing agent: {str(e)}",
            finish_reason="error"
        )


def scan_sandbox_for_attachments() -> List[str]:
    """Scan sandbox directory for new/modified files.
    
    In a full implementation, this would:
    1. Track request start time
    2. Find files modified after request start
    3. Return list of attachment paths
    
    For now, returns empty list (attachments not implemented).
    
    Returns:
        List of file paths (relative to sandbox)
    """
    # TODO: Implement attachment scanning
    # This requires tracking request timestamps and file modification times
    
    if not os.path.exists(SANDBOX_PATH):
        return []
    
    attachments = []
    
    # Walk sandbox directory
    for root, dirs, files in os.walk(SANDBOX_PATH):
        for file in files:
            # Get relative path
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, SANDBOX_PATH)
            attachments.append(rel_path)
    
    return attachments


def create_session_id(conversation_id: str, preset_slug: str) -> str:
    """Create a unique session ID.
    
    Args:
        conversation_id: Conversation identifier
        preset_slug: Preset identifier
        
    Returns:
        Unique session ID
    """
    return f"{conversation_id}-{preset_slug}-{uuid.uuid4().hex[:8]}"


# Session cache (in-memory, no persistence)
_session_cache: Dict[str, AgentSession] = {}


def get_or_create_session(
    conversation_id: str,
    preset_slug: str,
    preset_manager: PresetManager,
    memory_context: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None
) -> AgentSession:
    """Get existing session or create new one.
    
    Sessions are cached in-memory and keyed by conversation+preset.
    If preset changes, a new session is created.
    
    Args:
        conversation_id: Conversation identifier
        preset_slug: Preset identifier
        preset_manager: Manager with preset data
        memory_context: Optional memory context
        messages: Optional messages for operator context retrieval
        
    Returns:
        AgentSession instance
    """
    # Create session key
    session_key = f"{conversation_id}-{preset_slug}"
    
    # Check cache
    if session_key in _session_cache:
        return _session_cache[session_key]
    
    # Get operator context from user facts if messages provided
    operator_context = None
    if messages:
        operator_context = get_operator_context(messages)
    
    # Create new session
    session_id = create_session_id(conversation_id, preset_slug)
    model = get_model_for_preset(preset_slug, preset_manager)
    system_prompt = assemble_system_prompt(
        preset_slug, 
        preset_manager, 
        memory_context,
        operator_context
    )
    mcp_servers = resolve_mcp_servers(preset_slug)
    
    # Set session context for user facts tools
    set_session_context("operator", conversation_id)
    
    session = AgentSession(
        session_id=session_id,
        preset_slug=preset_slug,
        model=model,
        system_prompt=system_prompt,
        mcp_servers=mcp_servers
    )
    
    # Cache session
    _session_cache[session_key] = session
    
    logger.info(
        f"Created new agent session: {session_id} "
        f"(preset={preset_slug}, model={model}, mcps={mcp_servers})"
    )
    
    return session


def clear_session_cache(conversation_id: Optional[str] = None):
    """Clear session cache.
    
    Args:
        conversation_id: If provided, clear only sessions for this conversation.
                        If None, clear entire cache.
    """
    global _session_cache
    
    if conversation_id:
        # Clear only sessions for this conversation
        keys_to_remove = [
            k for k in _session_cache.keys()
            if k.startswith(f"{conversation_id}-")
        ]
        for key in keys_to_remove:
            del _session_cache[key]
    else:
        # Clear all
        _session_cache.clear()
