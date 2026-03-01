"""Channel system for platform integrations.

This module provides the channel system core for integrating
Discord and OpenWebUI platforms with the agent API.

Components:
- manager: Listener lifecycle management
- listeners: Platform-specific message listeners
- translators: Message format translation
- dispatcher: Bridge to existing agent pipeline
- debounce: Message batching system
- chunker: Response chunking for platform limits
- delivery: Platform-specific response delivery
"""

from channels.manager import (
    start_listener,
    stop_listener,
    start_all_active,
    stop_all,
)
from channels.debounce import (
    init_debounce,
    push_message,
)

__all__ = [
    # Listener management
    "start_listener",
    "stop_listener",
    "start_all_active",
    "stop_all",
    # Debounce system
    "init_debounce",
    "push_message",
]
