"""Platform-specific message listeners.

This submodule contains listener implementations for different platforms:
- discord_listener: Discord bot using discord.py
- openwebui_listener: OpenWebUI polling-based listener
"""

from channels.listeners.discord_listener import create_discord_listener
from channels.listeners.openwebui_listener import create_openwebui_listener

__all__ = [
    "create_discord_listener",
    "create_openwebui_listener",
]
