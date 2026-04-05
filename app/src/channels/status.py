"""Discord status embed system.

Sends lightweight, color-coded embeds to Discord channels for operational
visibility. Only sends for Discord platform — no-ops for API/OpenWebUI.

Embeds are sent as separate small messages per event (not edited in-place).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class StatusType(Enum):
    MESSAGE_RECEIVED = "message_received"
    MODEL_SELECTED = "model_selected"
    SUBAGENT_SPAWNING = "subagent_spawning"
    SUBAGENT_COMPLETED = "subagent_completed"
    SUBAGENT_FAILED = "subagent_failed"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"


_STATUS_COLORS = {
    StatusType.MESSAGE_RECEIVED: 0x3498DB,   # blue
    StatusType.MODEL_SELECTED: 0x2ECC71,     # green
    StatusType.SUBAGENT_SPAWNING: 0xF39C12,   # yellow
    StatusType.SUBAGENT_COMPLETED: 0x2ECC71,  # green
    StatusType.SUBAGENT_FAILED: 0xE74C3C,     # red
    StatusType.TOOL_STARTED: 0x9B59B6,        # purple
    StatusType.TOOL_COMPLETED: 0x2ECC71,      # green
    StatusType.TOOL_FAILED: 0xE74C3C,         # red
}


async def send_status(
    status_type: StatusType,
    title: str,
    description: str = "",
    fields: Optional[Dict[str, str]] = None,
) -> None:
    """Send a status embed to the Discord channel (if platform context is Discord).

    Silently no-ops for non-Discord platforms or when no platform context is set.
    Never blocks the pipeline — all errors are caught and logged.

    Args:
        status_type: Type of status event (determines embed color)
        title: Short status label
        description: Brief details
        fields: Optional key-value pairs to display as embed fields
    """
    from channels.context import get_platform_context

    ctx = get_platform_context()
    if not ctx or ctx.get("platform") != "discord":
        return

    channel = ctx.get("channel_ref")
    discord_loop = ctx.get("discord_loop")

    if not channel or not discord_loop:
        return

    try:
        import discord

        color = _STATUS_COLORS.get(status_type, 0x95A5A6)
        embed = discord.Embed(
            title=title,
            description=description or None,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        if fields:
            for name, value in fields.items():
                embed.add_field(name=name, value=value, inline=True)

        embed.set_footer(text="IF Status")

        coro = channel.send(embed=embed)

        if discord_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, discord_loop)
            # Don't await — fire and forget to avoid blocking the pipeline
            future.add_done_callback(lambda f: None)
        else:
            await coro

    except Exception as e:
        logger.debug(f"[Status] Failed to send embed: {e}")
