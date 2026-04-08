"""Channel dispatcher - bridge between channel system and existing pipeline.

Translates platform messages → calls core pipeline → delivers response back.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

import httpx

from channels.translators.discord_translator import translate_discord_batch
from channels.translators.openwebui_translator import translate_openwebui_batch
from channels.chunker import chunk_response
from channels.delivery import deliver_to_channel

logger = logging.getLogger(__name__)

# Number of historical messages to fetch from Discord channel
DISCORD_HISTORY_LIMIT = 100


async def _upload_attachments(
    request_data: Dict[str, Any],
    conversation_id: str,
    http_client: httpx.AsyncClient,
) -> None:
    """Download attachment URLs and upload to terminal filesystem.

    Pops _pending_uploads from request_data and processes each one.
    Failures are logged as warnings and never block the pipeline.
    """
    pending = request_data.pop("_pending_uploads", [])
    if not pending:
        return

    try:
        from pathlib import Path
        from app_sandbox import get_local_sandbox
        from config import MEDIA_UPLOAD_DIR
    except ImportError as e:
        logger.warning(f"[Upload] Import error, skipping attachment upload: {e}")
        return

    try:
        workdir = Path(get_local_sandbox().get_working_dir(conversation_id))
        upload_dir = workdir / MEDIA_UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"[Upload] Sandbox setup failed, skipping attachment upload: {e}")
        return

    for att in pending:
        filename = att["filename"]
        url = att["url"]
        try:
            resp = await http_client.get(url, timeout=30.0)
            resp.raise_for_status()
            dest = upload_dir / filename
            dest.write_bytes(resp.content)
            logger.info(f"[Upload] Uploaded {filename} ({len(resp.content)} bytes) to {dest}")
        except Exception as e:
            logger.warning(f"[Upload] Failed to upload {filename}: {e}")


async def _fetch_discord_history(
    channel_ref: Any,
    discord_loop: Any,
) -> List[Any]:
    """Fetch recent messages from Discord channel history.

    Args:
        channel_ref: Discord TextChannel object
        discord_loop: The Discord client's event loop

    Returns:
        List of discord.Message objects (newest first)
    """
    if channel_ref is None:
        return []

    try:
        import asyncio
        import discord

        async def fetch():
            messages = []
            async for msg in channel_ref.history(limit=DISCORD_HISTORY_LIMIT):
                messages.append(msg)
            return messages

        # Run the fetch in the Discord event loop
        if discord_loop and discord_loop.is_running():
            # Schedule the coroutine in the Discord loop
            future = asyncio.run_coroutine_threadsafe(fetch(), discord_loop)
            # Wait for result with timeout
            messages = future.result(timeout=10.0)
            logger.info(f"[Discord] Fetched {len(messages)} history messages")
            return messages
        else:
            logger.warning("[Discord] Discord loop not running, skipping history fetch")
            return []

    except Exception as e:
        logger.warning(f"[Discord] Failed to fetch channel history: {e}")
        return []


async def dispatch_channel_batch(
    messages: List[Dict[str, Any]],
    conversation_id: str,
    platform: str,
    channel_ref: Any,
    discord_loop: Any = None,
) -> None:
    """Process a batch of channel messages and deliver response.

    This is the main entry point for the channel system:
    1. Translate platform messages to ChatCompletionRequest format
    2. Call the same core pipeline as /v1/chat/completions
    3. Chunk and deliver the response back to the channel

    Args:
        messages: List of message dicts from debounce queue
        conversation_id: Conversation ID for this batch
        platform: Platform name ("discord" or "openwebui")
        channel_ref: Platform-specific channel reference
    """
    logger.info(
        f"Dispatching batch for {conversation_id}: "
        f"{len(messages)} messages from {platform}"
    )

    # Set platform context for status embed threading
    from channels.context import set_platform_context
    set_platform_context(platform, channel_ref, discord_loop)

    # Emit message received status embed
    from channels.status import send_status, StatusType
    await send_status(
        StatusType.MESSAGE_RECEIVED,
        "Message Received",
        f"{len(messages)} message(s)",
    )

    # Step 1: Translate messages to request format
    if platform == "discord":
        # Fetch channel history for context
        history_messages = await _fetch_discord_history(channel_ref, discord_loop)
        request_data = translate_discord_batch(
            messages,
            conversation_id,
            history_messages=history_messages,
        )
    elif platform == "openwebui":
        request_data = translate_openwebui_batch(messages, conversation_id)
    else:
        logger.error(f"Unknown platform: {platform}")
        return

    # Step 2: Process through the existing pipeline
    # Import here to avoid circular dependency
    from api.completions import process_chat_completion_internal
    from main import app
    from storage.factory import get_webhook_store

    # Get HTTP client from app state
    http_client = app.state.http_client

    # Step 1.5: Upload attachments to terminal filesystem
    await _upload_attachments(request_data, conversation_id, http_client)

    # Get webhook record for this conversation
    webhook = None
    try:
        store = get_webhook_store()
        records = store.list_active()
        for r in records:
            if r.conversation_id == conversation_id:
                webhook = r
                break
    except Exception as e:
        logger.warning(f"Could not fetch webhook record: {e}")

    try:
        response_text, attachments = await process_chat_completion_internal(
            request_data=request_data,
            http_client=http_client,
            webhook=webhook,
        )
    except Exception as e:
        logger.error(f"Pipeline error for {conversation_id}: {e}")
        # Send error message to channel
        from channels.delivery import send_error_message
        await send_error_message(
            platform=platform,
            channel_ref=channel_ref,
            error_message=str(e),
        )
        return
    
    logger.info(
        f"Pipeline completed for {conversation_id}: "
        f"{len(response_text)} chars, {len(attachments)} attachments"
    )
    
    # Step 3: Chunk and deliver
    chunks = chunk_response(response_text)
    logger.info(f"Response split into {len(chunks)} chunks")
    
    await deliver_to_channel(
        platform=platform,
        channel_ref=channel_ref,
        chunks=chunks,
        attachments=attachments,
        discord_loop=discord_loop,
    )
    
    logger.info(f"Delivery completed for {conversation_id}")

    # Clear platform context
    from channels.context import clear_platform_context
    clear_platform_context()
    
    # Record activity for heartbeat system (outbound message)
    try:
        from heartbeat.activity import ActivityTracker
        from storage.factory import get_webhook_store
        store = get_webhook_store()
        if store and hasattr(store, '_backend'):
            tracker = ActivityTracker(store._backend)
            # Get webhook_id from channel_ref if available
            webhook_id = getattr(channel_ref, 'webhook_id', None)
            tracker.record_activity(conversation_id, webhook_id=webhook_id)
    except Exception as e:
        logger.debug(f"[Activity] Failed to record outbound: {e}")


async def dispatch_single_message(
    message: Dict[str, Any],
    conversation_id: str,
    platform: str,
    channel_ref: Any,
) -> None:
    """Dispatch a single message (wrapper around batch dispatch).
    
    Convenience function for cases where debounce is not needed.
    
    Args:
        message: Single message dict
        conversation_id: Conversation ID
        platform: Platform name
        channel_ref: Platform-specific channel reference
    """
    await dispatch_channel_batch(
        messages=[message],
        conversation_id=conversation_id,
        platform=platform,
        channel_ref=channel_ref,
    )
