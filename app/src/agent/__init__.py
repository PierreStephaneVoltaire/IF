"""Agent module for OpenHands integration."""
from .session import (
    AgentSession,
    AgentResponse,
    get_or_create_session,
    execute_agent,
    clear_session_cache,
    resolve_mcp_servers,
    assemble_system_prompt,
)
from .memory_tools import (
    memory_search,
    memory_add,
    memory_remove,
    memory_list,
    get_memory_tools,
    execute_memory_tool,
)
from .condenser import (
    condense_conversation,
    should_condense,
    estimate_token_count,
)

__all__ = [
    # Session management
    "AgentSession",
    "AgentResponse",
    "get_or_create_session",
    "execute_agent",
    "clear_session_cache",
    "resolve_mcp_servers",
    "assemble_system_prompt",
    # Memory tools
    "memory_search",
    "memory_add",
    "memory_remove",
    "memory_list",
    "get_memory_tools",
    "execute_memory_tool",
    # Context condensation
    "condense_conversation",
    "should_condense",
    "estimate_token_count",
]