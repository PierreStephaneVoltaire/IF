"""Per-channel debounce system for message batching.

Accumulates messages within CHANNEL_DEBOUNCE_SECONDS of inactivity,
then flushes the batch to the dispatcher.

Threading Model:
- Listener threads call push_message() from their own event loops.
- push_message() is thread-safe: uses threading.Lock to append to a plain list,
  then schedules the debounce timer on the main loop.
- The debounce timer and dispatch run on the main asyncio event loop.
"""
from __future__ import annotations
import asyncio
import threading
import logging
from typing import Dict, List, Any, Optional

from config import CHANNEL_DEBOUNCE_SECONDS

logger = logging.getLogger(__name__)

# Thread-safe lock for buffer access
_lock = threading.Lock()

# Message buffers keyed by conversation_id
_buffers: Dict[str, List[Dict[str, Any]]] = {}

# Pending timers keyed by conversation_id
_timers: Dict[str, asyncio.TimerHandle] = {}

# Reference to main event loop (set at startup)
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def init_debounce(loop: asyncio.AbstractEventLoop) -> None:
    """Initialize the debounce system with the main event loop.
    
    Must be called at startup before any messages are pushed.
    
    Args:
        loop: The main asyncio event loop
    """
    global _main_loop
    _main_loop = loop
    logger.info(
        f"Debounce system initialized "
        f"(window={CHANNEL_DEBOUNCE_SECONDS}s)"
    )


def push_message(conversation_id: str, message: Dict[str, Any]) -> None:
    """Push a message to the debounce buffer.
    
    Called from listener threads. Thread-safe. Appends the message to
    the buffer and resets the debounce timer.
    
    Args:
        conversation_id: Conversation ID to buffer the message for
        message: Message dict from the platform listener
    """
    if _main_loop is None:
        logger.error("Debounce not initialized. Call init_debounce() first.")
        return

    with _lock:
        if conversation_id not in _buffers:
            _buffers[conversation_id] = []
        _buffers[conversation_id].append(message)
        buffer_size = len(_buffers[conversation_id])

    logger.debug(
        f"Message buffered for {conversation_id} "
        f"(buffer size: {buffer_size})"
    )

    # Schedule/reschedule the flush timer on the main loop
    _main_loop.call_soon_threadsafe(
        _schedule_flush, conversation_id
    )


def _schedule_flush(conversation_id: str) -> None:
    """Reschedule the debounce timer for a conversation.
    
    Runs on the main event loop. Cancels any existing timer and
    schedules a new flush after the debounce window.
    
    Args:
        conversation_id: Conversation ID to schedule flush for
    """
    if _main_loop is None:
        return

    # Cancel existing timer if any
    existing = _timers.get(conversation_id)
    if existing is not None:
        existing.cancel()

    # Schedule new flush after debounce window
    handle = _main_loop.call_later(
        CHANNEL_DEBOUNCE_SECONDS,
        lambda: asyncio.ensure_future(_flush(conversation_id), loop=_main_loop),
    )
    _timers[conversation_id] = handle


async def _flush(conversation_id: str) -> None:
    """Flush the buffered messages for a conversation.
    
    Runs on main loop. Removes messages from buffer, cancels timer,
    and dispatches to the channel dispatcher.
    
    Args:
        conversation_id: Conversation ID to flush
    """
    with _lock:
        messages = _buffers.pop(conversation_id, [])
        _timers.pop(conversation_id, None)

    if not messages:
        return

    platform = messages[0].get("platform", "unknown")
    channel_ref = messages[-1].get("channel_ref")  # Latest ref

    logger.info(
        f"Flushing {len(messages)} messages for {conversation_id} ({platform})"
    )

    # Import here to avoid circular dependency
    from channels.dispatcher import dispatch_channel_batch

    try:
        await dispatch_channel_batch(
            messages=messages,
            conversation_id=conversation_id,
            platform=platform,
            channel_ref=channel_ref,
        )
    except Exception as e:
        logger.error(f"Dispatch failed for {conversation_id}: {e}")


def get_buffer_size(conversation_id: str) -> int:
    """Get the current buffer size for a conversation.
    
    Args:
        conversation_id: Conversation ID to check
        
    Returns:
        Number of messages currently buffered
    """
    with _lock:
        return len(_buffers.get(conversation_id, []))


def clear_buffer(conversation_id: str) -> int:
    """Clear the buffer for a conversation.
    
    Args:
        conversation_id: Conversation ID to clear
        
    Returns:
        Number of messages that were cleared
    """
    with _lock:
        messages = _buffers.pop(conversation_id, [])
        timer = _timers.pop(conversation_id, None)
        if timer is not None:
            timer.cancel()
    return len(messages)


def get_all_buffer_sizes() -> Dict[str, int]:
    """Get buffer sizes for all conversations.
    
    Returns:
        Dict mapping conversation_id to buffer size
    """
    with _lock:
        return {cid: len(msgs) for cid, msgs in _buffers.items()}
