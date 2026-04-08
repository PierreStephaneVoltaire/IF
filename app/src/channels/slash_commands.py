"""Discord slash command registration and interaction handling.

Registers guild-level slash commands and handles interactions.
Uses a thread-safe dedup set so the same guild is never synced
twice across listeners sharing a bot token.
"""
from __future__ import annotations

import logging
import threading

import discord
from discord import app_commands

logger = logging.getLogger(__name__)

# Thread-safe dedup: (bot_user_id, guild_id) pairs already synced
_synced_guilds: set[tuple[int, int]] = set()
_sync_lock = threading.Lock()


def should_sync(bot_user_id: int, guild_id: int) -> bool:
    """Check-and-mark whether this guild needs command sync.

    Returns True (and marks as synced) if not yet synced, False otherwise.
    Thread-safe across multiple listener threads.
    """
    with _sync_lock:
        key = (bot_user_id, guild_id)
        if key in _synced_guilds:
            return False
        _synced_guilds.add(key)
        return True


def setup_command_tree(
    tree: app_commands.CommandTree,
    channel_id: int,
    conversation_id: str,
    webhook_id: str,
) -> None:
    """Register all slash commands on the given CommandTree.

    Each command handler routes through the existing command logic
    (routing cache, CommandHandler) rather than the full dispatcher pipeline.

    Args:
        tree: The CommandTree to register commands on
        channel_id: Discord channel ID (used as cache_key)
        conversation_id: Conversation ID for this webhook
        webhook_id: Webhook ID for logging
    """
    cache_key = str(channel_id)
    context_id = f"discord_{channel_id}"

    # --- /end_convo ---
    @tree.command(
        name="end_convo",
        description="Clear conversation state and force reclassification",
    )
    async def end_convo_cmd(interaction: discord.Interaction):
        try:
            from routing.cache import get_cache

            cache = get_cache()
            cache.evict(cache_key)

            try:
                from storage.factory import get_webhook_store

                store = get_webhook_store()
                if store:
                    await cache.persist_eviction(cache_key, store._backend)
            except Exception as e:
                logger.warning(f"[SlashCmd] Failed to persist eviction: {e}")

            await interaction.response.send_message(
                "Acknowledged. Categorisation state cleared. "
                "Next message will be re-evaluated."
            )
        except Exception as e:
            logger.error(f"[SlashCmd] /end_convo error: {e}")
            await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

    # --- /pondering ---
    @tree.command(
        name="pondering",
        description="Enter reflective conversation mode (heavy tier)",
    )
    async def pondering_cmd(interaction: discord.Interaction):
        try:
            from routing.cache import get_cache

            cache = get_cache()
            cache.pin(cache_key, 2)  # Heavy tier

            try:
                from storage.factory import get_webhook_store

                store = get_webhook_store()
                if store:
                    await cache.persist_entry(cache_key, store._backend)
            except Exception as e:
                logger.warning(f"[SlashCmd] Failed to persist pin: {e}")

            await interaction.response.send_message(
                "Acknowledged. Routing pinned to preset: pondering. "
                "Send /end_convo to release."
            )
        except Exception as e:
            logger.error(f"[SlashCmd] /pondering error: {e}")
            await interaction.response.send_message(
                f"Error: {e}", ephemeral=True
            )

    # --- /clear ---
    @tree.command(
        name="clear",
        description="Delete recent messages from this channel",
    )
    @app_commands.describe(amount="Number of messages to delete (default 100)")
    async def clear_cmd(interaction: discord.Interaction, amount: int = 100):
        if not interaction.channel:
            await interaction.response.send_message(
                "Cannot determine channel.", ephemeral=True
            )
            return

        perms = interaction.channel.permissions_for(interaction.guild.me)
        if not perms.manage_messages:
            await interaction.response.send_message(
                "I need the **Manage Messages** permission to clear chat.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "You need the **Manage Messages** permission to use this.",
                ephemeral=True,
            )
            return

        amount = max(1, min(amount, 1000))
        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(
                f"Deleted {len(deleted)} message(s).", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "Missing permissions to delete messages.", ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"Failed to delete messages: {e}", ephemeral=True
            )

    # --- Reflection commands ---
    def _make_reflection_handler(
        command_name: str, description: str, args_hint: str = "",
    ):
        """Factory for reflection command handlers."""

        @tree.command(name=command_name, description=description)
        @app_commands.describe(
            args=args_hint or "Optional arguments for the command"
        )
        async def handler(interaction: discord.Interaction, args: str = ""):
            await interaction.response.defer()
            try:
                from memory.user_facts import get_user_fact_store
                from agent.commands import get_command_handler
                from agent.reflection import get_reflection_engine

                store = get_user_fact_store()
                reflection_engine = get_reflection_engine()
                cmd_handler = get_command_handler(
                    store, reflection_engine, context_id
                )

                result = cmd_handler.handle(f"/{command_name}", args)

                # Discord followup limit is 2000 chars
                if len(result) <= 2000:
                    await interaction.followup.send(result)
                else:
                    # Chunk the response
                    chunks = [
                        result[i : i + 2000]
                        for i in range(0, len(result), 2000)
                    ]
                    for chunk in chunks:
                        await interaction.followup.send(chunk)
            except ImportError as e:
                await interaction.followup.send(
                    f"Command not available: {e}"
                )
            except Exception as e:
                logger.error(
                    f"[SlashCmd] /{command_name} error: {e}"
                )
                await interaction.followup.send(
                    f"Error executing /{command_name}: {e}"
                )

        return handler

    _make_reflection_handler("reflect", "Trigger a manual reflection cycle")
    _make_reflection_handler(
        "gaps",
        "List capability gaps ranked by priority",
        args_hint="Minimum trigger count (default 1)",
    )
    _make_reflection_handler("patterns", "Show detected behavioral patterns")
    _make_reflection_handler(
        "opinions", "Show opinion pairs (operator vs agent positions)"
    )
    _make_reflection_handler(
        "growth",
        "Show operator growth report",
        args_hint="Number of days to look back (default 30)",
    )
    _make_reflection_handler(
        "meta", "Show store health metrics and category suggestions"
    )
    _make_reflection_handler(
        "tools", "Show tool suggestions from capability gaps"
    )
