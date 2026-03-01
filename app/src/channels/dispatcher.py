"""Channel dispatcher - bridge between channel system and existing pipeline.

Translates platform messages → calls core pipeline → delivers response back.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List

from channels.translators.discord_translator import translate_discord_batch
from channels.translators.openwebui_translator import translate_openwebui_batch
from channels.chunker import chunk_response
from channels.delivery import deliver_to_channel

logger = logging.getLogger(__name__)


async def dispatch_channel_batch(
    messages: List[Dict[str, Any]],
    conversation_id: str,
    platform: str,
    channel_ref: Any,
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
    
    # Step 1: Translate messages to request format
    if platform == "discord":
        request_data = translate_discord_batch(messages, conversation_id)
    elif platform == "openwebui":
        request_data = translate_openwebui_batch(messages, conversation_id)
    else:
        logger.error(f"Unknown platform: {platform}")
        return
    
    # Step 2: Process through the existing pipeline
    # Import here to avoid circular dependency
    from api.completions import process_chat_completion_internal
    from main import app
    
    # Get HTTP client from app state
    http_client = app.state.http_client
    
    try:
        # Discord: show typing indicator while processing
        if platform == "discord" and hasattr(channel_ref, "typing"):
            async with channel_ref.typing():
                response_text, attachments = await process_chat_completion_internal(
                    request_data=request_data,
                    http_client=http_client,
                    conversation_id=conversation_id,
                )
        else:
            response_text, attachments = await process_chat_completion_internal(
                request_data=request_data,
                http_client=http_client,
                conversation_id=conversation_id,
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
    )
    
    logger.info(f"Delivery completed for {conversation_id}")


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
