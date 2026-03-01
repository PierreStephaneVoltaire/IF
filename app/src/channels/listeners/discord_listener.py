"""Discord listener using discord.py.

Runs a bot client in its own thread with its own event loop.
Captures messages from the registered channel and pushes to debounce queue.
"""
from __future__ import annotations
import asyncio
import threading
import logging
from typing import TYPE_CHECKING, Callable

import discord

if TYPE_CHECKING:
    from storage.models import WebhookRecord

logger = logging.getLogger(__name__)


def create_discord_listener(
    record: "WebhookRecord",
    stop_event: threading.Event,
) -> Callable[[], None]:
    """Create a Discord listener function for threading.
    
    Returns a callable to be used as a Thread target. Runs a discord.py
    client that listens to a single channel.
    
    Args:
        record: WebhookRecord containing Discord configuration
        stop_event: Threading event to signal listener shutdown
        
    Returns:
        Callable that runs the Discord bot listener
    """
    config = record.get_config()
    bot_token = config["bot_token"]
    channel_id = int(config["channel_id"])
    conversation_id = record.conversation_id
    webhook_id = record.webhook_id

    def run() -> None:
        """Run the Discord bot in its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            logger.info(
                f"Discord listener {webhook_id} connected as {client.user}"
            )

        @client.event
        async def on_message(message: discord.Message):
            # Ignore own messages and other bots
            if message.author == client.user or message.author.bot:
                return
            # Only listen to the registered channel
            if message.channel.id != channel_id:
                return

            # Import here to avoid circular dependency
            from channels.debounce import push_message

            push_message(
                conversation_id=conversation_id,
                message={
                    "platform": "discord",
                    "webhook_id": webhook_id,
                    "conversation_id": conversation_id,
                    "author": message.author.display_name,
                    "content": message.clean_content,
                    "attachments": [
                        {
                            "filename": att.filename,
                            "url": att.url,
                            "content_type": (
                                att.content_type
                                or "application/octet-stream"
                            ),
                        }
                        for att in message.attachments
                    ],
                    "channel_ref": message.channel,
                    "timestamp": message.created_at.isoformat(),
                },
            )
            logger.debug(
                f"Discord message from {message.author.display_name} "
                f"in {webhook_id}: {message.clean_content[:50]}..."
            )

        async def runner():
            """Run the Discord client."""
            try:
                await client.start(bot_token)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Discord client error for {webhook_id}: {e}")
            finally:
                await client.close()

        async def main():
            """Main async function that watches for stop signal."""
            task = asyncio.create_task(runner())
            # Watch for stop signal from the manager
            while not stop_event.is_set():
                await asyncio.sleep(1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        try:
            loop.run_until_complete(main())
        except Exception as e:
            logger.error(f"Discord listener error for {webhook_id}: {e}")
        finally:
            loop.close()
            logger.info(f"Discord listener stopped for {webhook_id}")

    return run
