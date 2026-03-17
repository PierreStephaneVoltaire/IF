"""Channel registration and management endpoints.

Provides endpoints to:
- Register a Discord channel for listening
- Unregister a channel
- List registered channels
- Manually trigger a response (for testing)
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import (
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_MODEL,
    MAX_HISTORY_LIMIT,
    OPENROUTER_HEADERS,
    LLM_BASE_URL,
    MAX_CHUNK_CHARS,
    INTER_CHUNK_DELAY,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/channels", tags=["channels"])


# SSE format constants (from main app completions.py)
SSE_PREFIX = "data: "
SSE_DONE = "data: [DONE]\n\n"


class ChannelRegistration(BaseModel):
    """Request to register a Discord channel."""
    channel_id: str = Field(..., description="Discord channel ID")
    history_limit: int = Field(DEFAULT_HISTORY_LIMIT, description="Number of messages to fetch for context")
    model: str = Field(DEFAULT_MODEL, description="LLM model to use")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt")


class ChannelInfo(BaseModel):
    """Information about a registered channel."""
    channel_id: str
    history_limit: int
    model: str
    system_prompt: Optional[str]
    status: str = "registered"


class ChannelListResponse(BaseModel):
    """Response for listing channels."""
    channels: List[ChannelInfo]
    total: int


def convert_messages_to_openai(
    messages: List[Any],
    system_prompt: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Convert Discord messages to OpenAI format.

    Reuses patterns from src/channels/translators/discord_translator.py
    """
    openai_messages = []

    if system_prompt:
        openai_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        content_parts = []

        # Add text with author attribution
        if msg.content:
            content_parts.append({
                "type": "text",
                "text": f"[{msg.author}]: {msg.content}"
            })

        # Handle attachments
        for att in msg.attachments:
            ct = att.get("content_type", "")
            url = att.get("url", "")
            filename = att.get("filename", "attachment")

            if ct.startswith("image/") and url:
                # Image attachments become image_url content
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": url}
                })
            else:
                # Non-image attachments become text references
                content_parts.append({
                    "type": "text",
                    "text": f"[Attachment: {filename} ({ct}) — {url}]"
                })

        if content_parts:
            # Discord messages are always "user" role from AI perspective
            openai_messages.append({
                "role": "user",
                "content": content_parts if len(content_parts) > 1 else content_parts[0].get("text", "")
            })

    return openai_messages


def chunk_response(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split response into chunks for Discord.

    Reuses patterns from src/channels/chunker.py
    """
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks = []
    paragraphs = text.split("\n\n")

    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chars:
            current_chunk += ("\n\n" if current_chunk else "") + para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # Handle paragraphs longer than max_chars
            if len(para) > max_chars:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chars:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


async def stream_llm_response(
    messages: List[Dict[str, Any]],
    model: str,
    http_client: Any,
    timeout: float = 120.0
) -> AsyncGenerator[str, None]:
    """Stream response from OpenRouter directly.

    Reuses patterns from src/routing/interceptor.py
    """
    url = f"{LLM_BASE_URL}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    full_content = ""

    async with http_client.stream(
        "POST",
        url,
        headers=OPENROUTER_HEADERS,
        json=payload,
        timeout=timeout
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith(SSE_PREFIX):
                data = line[len(SSE_PREFIX):].strip()
                if data == "[DONE]":
                    break

                try:
                    parsed = json.loads(data)
                    choices = parsed.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                except json.JSONDecodeError:
                    continue

    return full_content


async def handle_discord_message(message: Any, config: Any) -> None:
    """Handle incoming Discord message with LLM response.

    This is the main handler that:
    1. Fetches channel history
    2. Converts to OpenAI format
    3. Streams LLM response
    4. Sends response back to Discord
    """
    from discord_client import get_client

    client = get_client()

    # Fetch history including the new message
    history = await client.fetch_history(
        config.channel_id,
        limit=config.history_limit
    )

    logger.info(f"Fetched {len(history)} messages for channel {config.channel_id}")

    # Convert to OpenAI format
    openai_messages = convert_messages_to_openai(
        history,
        system_prompt=config.system_prompt
    )

    if not openai_messages:
        logger.warning("No messages to send to LLM")
        return

    # Get HTTP client from app state
    http_client = message.client.http_client if hasattr(message.client, 'http_client') else None
    if not http_client:
        logger.error("HTTP client not available")
        return

    # Stream LLM response
    try:
        response_text = await stream_llm_response(
            messages=openai_messages,
            model=config.model,
            http_client=http_client
        )
    except Exception as e:
        logger.error(f"LLM streaming failed: {e}")
        return

    if not response_text:
        logger.info("Empty response from LLM")
        return

    # Chunk and send to Discord
    chunks = chunk_response(response_text)
    channel = client.get_channel(config.channel_id)

    if not channel:
        logger.error(f"Could not get channel {config.channel_id}")
        return

    for chunk in chunks:
        try:
            await channel.send(chunk)
            if len(chunks) > 1:
                await asyncio.sleep(INTER_CHUNK_DELAY)
        except Exception as e:
            logger.error(f"Failed to send chunk to Discord: {e}")
            break

    logger.info(f"Sent {len(chunks)} chunks to channel {config.channel_id}")


@router.post("/register", response_model=ChannelInfo)
async def register_channel(req: ChannelRegistration, request: Request):
    """Register a Discord channel for listening."""
    from discord_client import get_client

    try:
        channel_id = int(req.channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id - must be numeric")

    if req.history_limit > MAX_HISTORY_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"history_limit exceeds maximum of {MAX_HISTORY_LIMIT}"
        )

    client = get_client()

    if not client.is_ready():
        raise HTTPException(status_code=503, detail="Discord client not ready")

    # Verify channel exists and is accessible
    channel = client.get_channel(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found or not accessible")

    # Register with handler
    config = client.register_channel(
        channel_id=channel_id,
        history_limit=req.history_limit,
        model=req.model,
        system_prompt=req.system_prompt,
        handler=handle_discord_message
    )

    return ChannelInfo(
        channel_id=str(channel_id),
        history_limit=config.history_limit,
        model=config.model,
        system_prompt=config.system_prompt,
        status="registered"
    )


@router.delete("/{channel_id}")
async def unregister_channel(channel_id: str):
    """Unregister a Discord channel."""
    from discord_client import get_client

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id - must be numeric")

    client = get_client()

    if client.unregister_channel(channel_id_int):
        return {"status": "unregistered", "channel_id": channel_id}
    else:
        raise HTTPException(status_code=404, detail="Channel not registered")


@router.get("/", response_model=ChannelListResponse)
async def list_channels():
    """List all registered channels."""
    from discord_client import get_client

    client = get_client()

    channels = []
    for channel_id, config in client.registered_channels.items():
        channels.append(ChannelInfo(
            channel_id=str(channel_id),
            history_limit=config.history_limit,
            model=config.model,
            system_prompt=config.system_prompt,
            status="registered"
        ))

    return ChannelListResponse(channels=channels, total=len(channels))


@router.post("/{channel_id}/trigger")
async def trigger_response(channel_id: str, request: Request):
    """Manually trigger a response for testing.

    Fetches history and sends to LLM without waiting for a new message.
    """
    from discord_client import get_client

    try:
        channel_id_int = int(channel_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid channel_id - must be numeric")

    client = get_client()

    if channel_id_int not in client.registered_channels:
        raise HTTPException(status_code=404, detail="Channel not registered")

    config = client.registered_channels[channel_id_int]

    # Fetch history
    history = await client.fetch_history(
        channel_id_int,
        limit=config.history_limit
    )

    if not history:
        return {"status": "no_messages", "message": "No messages found in channel history"}

    # Convert to OpenAI format
    openai_messages = convert_messages_to_openai(
        history,
        system_prompt=config.system_prompt
    )

    # Get HTTP client
    http_client = request.app.state.http_client

    # Stream LLM response
    try:
        response_text = await stream_llm_response(
            messages=openai_messages,
            model=config.model,
            http_client=http_client
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM streaming failed: {e}")

    # Send to Discord
    chunks = chunk_response(response_text)
    channel = client.get_channel(channel_id_int)

    if channel:
        for chunk in chunks:
            try:
                await channel.send(chunk)
                if len(chunks) > 1:
                    await asyncio.sleep(INTER_CHUNK_DELAY)
            except Exception as e:
                logger.error(f"Failed to send chunk: {e}")
                break

    return {
        "status": "success",
        "messages_processed": len(history),
        "response_length": len(response_text),
        "chunks_sent": len(chunks) if channel else 0
    }
