"""Platform-specific response delivery.

Delivers chunked responses back to platform channels.
Handles platform-specific formatting and rate limits.
"""
from __future__ import annotations
import asyncio
import logging
from typing import Dict, List, Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    import discord

logger = logging.getLogger(__name__)

# Delay between chunks (seconds)
INTER_CHUNK_DELAY = 0.5


async def deliver_to_channel(
    platform: str,
    channel_ref: Any,
    chunks: List[str],
    attachments: List[Dict[str, Any]],
    discord_loop: Any = None,
) -> None:
    """Deliver response chunks to a platform channel.

    Routes to the appropriate platform-specific delivery function.

    Args:
        platform: Platform name ("discord" or "openwebui")
        channel_ref: Platform-specific channel reference
        chunks: List of text chunks to send
        attachments: List of attachment dicts with filename, url, local_path
        discord_loop: Discord event loop (required for Discord platform)
    """
    if platform == "discord":
        await _deliver_discord(channel_ref, chunks, attachments, discord_loop)
    elif platform == "openwebui":
        await _deliver_openwebui(channel_ref, chunks, attachments)
    else:
        logger.error(f"Unknown platform for delivery: {platform}")


async def _deliver_discord(
    channel: "discord.TextChannel",
    chunks: List[str],
    attachments: List[Dict[str, Any]],
    discord_loop: Any = None,
) -> None:
    """Send chunks to Discord channel.

    Sends chunks sequentially with files attached to the last chunk.
    Falls back to URL references if file download fails.

    When discord_loop is provided, sends are scheduled on the Discord
    event loop via run_coroutine_threadsafe (the channel object is bound
    to that loop, not the main/FastAPI loop).

    Args:
        channel: Discord TextChannel object
        chunks: List of text chunks to send
        attachments: List of attachment dicts
        discord_loop: The Discord client's event loop (required for cross-thread delivery)
    """
    import discord

    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        files: List[discord.File] = []

        if is_last and attachments:
            # Attach files to the last chunk
            for att in attachments:
                local_path = att.get("local_path")
                filename = att.get("filename", "attachment")
                url = att.get("url", "")

                if local_path:
                    try:
                        files.append(
                            discord.File(local_path, filename=filename)
                        )
                    except Exception as e:
                        logger.warning(
                            f"Cannot attach {filename}: {e}, "
                            f"falling back to URL"
                        )
                        chunk += f"\n📎 {filename}: {url}"
                else:
                    # No local path, use URL reference
                    chunk += f"\n📎 {filename}: {url}"

        try:
            send_coro = channel.send(
                content=chunk,
                files=files if files else None,
            )
            if discord_loop:
                # Schedule on Discord's event loop and await the result
                future = asyncio.run_coroutine_threadsafe(send_coro, discord_loop)
                await asyncio.wrap_future(future)
            else:
                await send_coro
            logger.debug(f"Sent Discord chunk {i+1}/{len(chunks)}")
        except discord.HTTPException as e:
            logger.error(f"Discord send failed: {e}")
            break
        except Exception as e:
            logger.error(f"Unexpected Discord error: {e}")
            break

        # Delay between chunks (not after last)
        if not is_last:
            await asyncio.sleep(INTER_CHUNK_DELAY)


async def _deliver_openwebui(
    channel_ref: Dict[str, str],
    chunks: List[str],
    attachments: List[Dict[str, Any]],
) -> None:
    """Post response to OpenWebUI channel.
    
    Sends as a single combined message (OpenWebUI doesn't have
    Discord's character limit).
    
    Args:
        channel_ref: Dict with base_url, channel_id, api_key
        chunks: List of text chunks (will be combined)
        attachments: List of attachment dicts
    """
    base_url = channel_ref["base_url"].rstrip("/")
    channel_id = channel_ref["channel_id"]
    api_key = channel_ref["api_key"]

    # Combine chunks into single message
    full_response = "\n\n".join(chunks)

    # Add attachment links if any
    if attachments:
        full_response += "\n\n**Attachments:**\n"
        for att in attachments:
            filename = att.get("filename", "attachment")
            url = att.get("url", "")
            full_response += f"- [{filename}]({url})\n"

    async with httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30.0,
    ) as client:
        try:
            resp = await client.post(
                f"/api/v1/channels/{channel_id}/messages",
                json={
                    "role": "assistant",
                    "content": full_response,
                },
            )
            
            if resp.status_code in (200, 201):
                logger.info(f"OpenWebUI delivery successful")
            else:
                logger.error(
                    f"OpenWebUI delivery failed: {resp.status_code} - "
                    f"{resp.text[:200]}"
                )
        except httpx.TimeoutException:
            logger.error("OpenWebUI delivery timeout")
        except httpx.RequestError as e:
            logger.error(f"OpenWebUI connection error: {e}")
        except Exception as e:
            logger.error(f"OpenWebUI delivery error: {e}")


async def send_typing_indicator(platform: str, channel_ref: Any) -> None:
    """Send typing indicator for supported platforms.
    
    Args:
        platform: Platform name
        channel_ref: Platform-specific channel reference
    """
    if platform == "discord":
        # Discord typing is handled via async context manager in dispatcher
        pass
    # OpenWebUI doesn't have typing indicators


async def send_error_message(
    platform: str,
    channel_ref: Any,
    error_message: str,
) -> None:
    """Send an error message to a channel.
    
    Args:
        platform: Platform name
        channel_ref: Platform-specific channel reference
        error_message: Error message to send
    """
    await deliver_to_channel(
        platform=platform,
        channel_ref=channel_ref,
        chunks=[f"❌ Error: {error_message}"],
        attachments=[],
    )


async def deliver_to_openwebui(
    api_url: str,
    channel_id: str,
    chunks: List[str],
    attachments: List[Dict[str, Any]],
) -> None:
    """Deliver response to OpenWebUI channel directly.
    
    Used by heartbeat system for proactive messaging.
    
    Args:
        api_url: OpenWebUI API base URL
        channel_id: Target channel ID
        chunks: List of text chunks (will be combined)
        attachments: List of attachment dicts
    """
    if not api_url:
        logger.error("OpenWebUI API URL not configured")
        return
    
    base_url = api_url.rstrip("/")
    
    # Combine chunks into single message
    full_response = "\n\n".join(chunks)
    
    # Add attachment links if any
    if attachments:
        full_response += "\n\n**Attachments:**\n"
        for att in attachments:
            filename = att.get("filename", "attachment")
            url = att.get("url", "")
            full_response += f"- [{filename}]({url})\n"
    
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=30.0,
    ) as client:
        try:
            resp = await client.post(
                f"/api/v1/channels/{channel_id}/messages",
                json={
                    "role": "assistant",
                    "content": full_response,
                },
            )
            
            if resp.status_code in (200, 201):
                logger.info(f"OpenWebUI heartbeat delivery successful")
            else:
                logger.error(
                    f"OpenWebUI heartbeat delivery failed: {resp.status_code} - "
                    f"{resp.text[:200]}"
                )
        except httpx.TimeoutException:
            logger.error("OpenWebUI heartbeat delivery timeout")
        except httpx.RequestError as e:
            logger.error(f"OpenWebUI heartbeat connection error: {e}")
        except Exception as e:
            logger.error(f"OpenWebUI heartbeat delivery error: {e}")
