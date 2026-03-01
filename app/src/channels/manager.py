"""Listener lifecycle management for channel integrations.

This module manages the lifecycle of platform listeners (Discord, OpenWebUI).
Each active webhook gets one listener running in a background daemon thread.
"""
from __future__ import annotations
import threading
import logging
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from storage.models import WebhookRecord

logger = logging.getLogger(__name__)

# Active listeners keyed by webhook_id
_listeners: Dict[str, Dict[str, Any]] = {}


def start_listener(record: "WebhookRecord") -> None:
    """Start a background listener for a webhook record.
    
    Creates and starts a daemon thread that runs the platform-specific
    listener function.
    
    Args:
        record: WebhookRecord containing platform and configuration
    """
    wid = record.webhook_id

    if wid in _listeners:
        logger.warning(f"Listener {wid} already running. Skipping.")
        return

    stop_event = threading.Event()
    platform = record.platform

    if platform == "discord":
        from channels.listeners.discord_listener import create_discord_listener
        target = create_discord_listener(record, stop_event)

    elif platform == "openwebui":
        from channels.listeners.openwebui_listener import create_openwebui_listener
        target = create_openwebui_listener(record, stop_event)

    else:
        logger.error(f"Unknown platform: {platform}")
        return

    thread = threading.Thread(
        target=target,
        name=f"listener-{wid}",
        daemon=True,
    )
    thread.start()

    _listeners[wid] = {
        "thread": thread,
        "stop_event": stop_event,
    }
    logger.info(
        f"Started {platform} listener for {wid} ({record.label})"
    )


def stop_listener(webhook_id: str) -> None:
    """Signal a listener to stop and wait for cleanup.
    
    Args:
        webhook_id: ID of the webhook whose listener should stop
    """
    entry = _listeners.pop(webhook_id, None)
    if entry is None:
        return
    
    entry["stop_event"].set()
    entry["thread"].join(timeout=10)
    logger.info(f"Stopped listener for {webhook_id}")


def start_all_active(records: list["WebhookRecord"]) -> None:
    """Start listeners for all active webhook records.
    
    Called at startup to resume listeners from persisted state.
    
    Args:
        records: List of WebhookRecord objects to start
    """
    started = 0
    for record in records:
        if record.status == "active":
            start_listener(record)
            started += 1
    
    logger.info(f"Started {started} active listeners from persisted state")


def stop_all() -> None:
    """Stop all active listeners.
    
    Called at shutdown to gracefully terminate all listener threads.
    """
    for wid in list(_listeners.keys()):
        stop_listener(wid)
    
    logger.info("All listeners stopped")


def get_active_listener_count() -> int:
    """Get the number of currently active listeners.
    
    Returns:
        Number of active listeners
    """
    return len(_listeners)


def is_listener_active(webhook_id: str) -> bool:
    """Check if a listener is currently active.
    
    Args:
        webhook_id: Webhook ID to check
        
    Returns:
        True if listener is active, False otherwise
    """
    return webhook_id in _listeners
