"""Discord client with history fetching capability.

Reuses patterns from src/channels/listeners/discord_listener.py but adds
channel history fetching for context building.
"""
from __future__ import annotations
import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import discord

if TYPE_CHECKING:
    from config import ChannelConfig

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Configuration for a registered channel."""
    channel_id: int
    history_limit: int = 50
    system_prompt: Optional[str] = None
    handler: Optional[Callable] = None


@dataclass
class DiscordMessage:
    """Simplified message representation."""
    author: str
    author_id: int
    content: str
    attachments: List[Dict[str, Any]]
    timestamp: datetime
    is_bot: bool = False


class DiscordClient:
    """Singleton Discord client with history fetching capability.

    This is the main new code needed - adds history fetching on top of
    the patterns from discord_listener.py.
    """

    _instance: Optional['DiscordClient'] = None

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.client: Optional[discord.Client] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.registered_channels: Dict[int, ChannelConfig] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ready_event = threading.Event()
        # Shared HTTP client injected by main.py lifespan for agent API calls
        self.http_client: Optional[Any] = None

    @classmethod
    def get_instance(cls, bot_token: Optional[str] = None) -> 'DiscordClient':
        """Get or create singleton instance."""
        if cls._instance is None:
            if bot_token is None:
                raise ValueError("bot_token required for first initialization")
            cls._instance = cls(bot_token)
        return cls._instance

    def start(self) -> None:
        """Start the Discord client in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Discord client already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_client, daemon=True)
        self._thread.start()

        # Wait for client to be ready (with timeout)
        if self._ready_event.wait(timeout=30):
            logger.info("Discord client started successfully")
        else:
            logger.warning("Discord client startup timed out")

    def stop(self) -> None:
        """Stop the Discord client."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        logger.info("Discord client stopped")

    def _run_client(self) -> None:
        """Run the Discord client in its own event loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            logger.info(f"Discord client connected as {self.client.user}")
            self._ready_event.set()

        @self.client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

        async def runner():
            try:
                await self.client.start(self.bot_token)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Discord client error: {e}")
            finally:
                await self.client.close()

        async def main():
            task = asyncio.create_task(runner())
            while not self._stop_event.is_set():
                await asyncio.sleep(1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        try:
            self.loop.run_until_complete(main())
        except Exception as e:
            logger.error(f"Discord client thread error: {e}")
        finally:
            self.loop.close()
            logger.info("Discord client thread finished")

    async def _handle_message(self, message: discord.Message) -> None:
        """Handle incoming Discord message."""
        # Ignore own messages and other bots
        if message.author == self.client.user or message.author.bot:
            return

        channel_id = message.channel.id
        if channel_id not in self.registered_channels:
            return

        config = self.registered_channels[channel_id]
        if config.handler:
            try:
                await config.handler(message, config)
            except Exception as e:
                logger.error(f"Error in channel handler for {channel_id}: {e}")

    def register_channel(
        self,
        channel_id: int,
        history_limit: int = 50,
        system_prompt: Optional[str] = None,
        handler: Optional[Callable] = None,
    ) -> ChannelConfig:
        """Register a channel for listening."""
        config = ChannelConfig(
            channel_id=channel_id,
            history_limit=history_limit,
            system_prompt=system_prompt,
            handler=handler,
        )
        self.registered_channels[channel_id] = config
        logger.info(f"Registered channel {channel_id} (history_limit={history_limit})")
        return config

    def unregister_channel(self, channel_id: int) -> bool:
        """Unregister a channel."""
        if channel_id in self.registered_channels:
            del self.registered_channels[channel_id]
            logger.info(f"Unregistered channel {channel_id}")
            return True
        return False

    async def fetch_history(
        self,
        channel_id: int,
        limit: int = 50,
        before: Optional[datetime] = None
    ) -> List[DiscordMessage]:
        """Fetch last N messages from channel history.

        This is the key addition - fetches historical messages for context.

        Args:
            channel_id: Discord channel ID
            limit: Maximum number of messages to fetch
            before: Fetch messages before this timestamp

        Returns:
            List of DiscordMessage objects, oldest first
        """
        if not self.client:
            logger.error("Discord client not initialized")
            return []

        channel = self.client.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.error(f"Channel {channel_id} is not a text channel")
            return []

        messages = []
        try:
            async for msg in channel.history(limit=limit, before=before):
                # Include bot messages — they represent the agent's previous replies
                # and are needed for the agent to maintain coherent conversation context.
                # Mark them with is_bot=True so the translator maps them to role="assistant".

                # Convert attachments
                attachments = []
                for att in msg.attachments:
                    attachments.append({
                        "filename": att.filename,
                        "url": att.url,
                        "content_type": att.content_type or "application/octet-stream",
                    })

                messages.append(DiscordMessage(
                    author=msg.author.display_name,
                    author_id=msg.author.id,
                    content=msg.clean_content,
                    attachments=attachments,
                    timestamp=msg.created_at,
                    is_bot=msg.author.bot,
                ))
        except Exception as e:
            logger.error(f"Error fetching history for channel {channel_id}: {e}")
            return []

        # Return oldest first (history returns newest first)
        return list(reversed(messages))

    def get_channel(self, channel_id: int) -> Optional[discord.TextChannel]:
        """Get a Discord channel by ID."""
        if not self.client:
            return None
        channel = self.client.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    def is_ready(self) -> bool:
        """Check if the client is ready."""
        return self._ready_event.is_set() and self.client is not None


# Global client instance
_client: Optional[DiscordClient] = None


def get_client(bot_token: Optional[str] = None) -> DiscordClient:
    """Get the global Discord client instance."""
    global _client
    if _client is None:
        if bot_token is None:
            raise ValueError("bot_token required for first initialization")
        _client = DiscordClient(bot_token)
    return _client


def start_client(bot_token: str) -> DiscordClient:
    """Start the global Discord client."""
    client = get_client(bot_token)
    client.start()
    return client


def stop_client() -> None:
    """Stop the global Discord client."""
    global _client
    if _client is not None:
        _client.stop()
