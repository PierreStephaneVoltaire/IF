"""Activity tracker for the heartbeat system.

Tracks message activity per channel/chat to determine idle state.
Persists to SQLite for survival across restarts.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Session, select

from storage.models import ActivityLogEntry

if TYPE_CHECKING:
    from storage.models import WebhookRecord
    from storage.sqlite_backend import SQLiteBackend

logger = logging.getLogger(__name__)


class ActivityTracker:
    """Tracks activity per cache_key for heartbeat idle detection.
    
    Activity is recorded on every incoming message and outgoing response.
    The heartbeat runner queries this to find idle channels.
    
    Example:
        >>> tracker = ActivityTracker(backend)
        >>> tracker.record_activity("channel_123", webhook_id="wh_abc")
        >>> idle = tracker.get_idle_webhooks(active_webhooks, 6.0, 6.0)
    """
    
    def __init__(self, backend: "SQLiteBackend"):
        """Initialize the activity tracker.
        
        Args:
            backend: SQLite backend for persistence
        """
        self.backend = backend
    
    def record_activity(
        self,
        cache_key: str,
        webhook_id: str | None = None
    ) -> None:
        """Record activity for a cache_key.
        
        Called on every message — inbound or outbound.
        Updates last_message_at timestamp.
        
        Args:
            cache_key: The channel_id or chat_id
            webhook_id: Optional webhook ID (only for webhook channels)
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with Session(self.backend.engine) as session:
            entry = session.get(ActivityLogEntry, cache_key)
            if entry:
                entry.last_message_at = now
                if webhook_id:
                    entry.webhook_id = webhook_id
            else:
                entry = ActivityLogEntry(
                    cache_key=cache_key,
                    webhook_id=webhook_id,
                    last_message_at=now
                )
                session.add(entry)
            session.commit()
        
        logger.debug(f"[Activity] Recorded for {cache_key}")
    
    def record_heartbeat(self, cache_key: str) -> None:
        """Mark that a heartbeat was sent to this channel.
        
        Args:
            cache_key: The channel_id that received the heartbeat
        """
        now = datetime.now(timezone.utc).isoformat()
        
        with Session(self.backend.engine) as session:
            entry = session.get(ActivityLogEntry, cache_key)
            if entry:
                entry.last_heartbeat_at = now
            else:
                # Shouldn't happen, but handle gracefully
                entry = ActivityLogEntry(
                    cache_key=cache_key,
                    last_message_at=now,
                    last_heartbeat_at=now
                )
                session.add(entry)
            session.commit()
        
        logger.debug(f"[Heartbeat] Recorded for {cache_key}")
    
    def get_idle_webhooks(
        self,
        active_webhooks: List["WebhookRecord"],
        idle_threshold_hours: float,
        cooldown_hours: float,
    ) -> List["WebhookRecord"]:
        """Returns webhooks whose channels have been idle beyond threshold.
        
        Filters out channels that:
        - Have had recent activity (within idle_threshold_hours)
        - Are on heartbeat cooldown (within cooldown_hours of last heartbeat)
        
        Args:
            active_webhooks: List of active webhook records
            idle_threshold_hours: Hours of inactivity before heartbeat eligible
            cooldown_hours: Hours to wait between heartbeats
            
        Returns:
            List of webhooks eligible for heartbeat
        """
        idle_threshold = timedelta(hours=idle_threshold_hours)
        cooldown_threshold = timedelta(hours=cooldown_hours)
        now = datetime.now(timezone.utc)
        
        idle_webhooks = []
        
        for webhook in active_webhooks:
            config = webhook.get_config()
            channel_id = config.get("channel_id")
            if not channel_id:
                continue
            
            with Session(self.backend.engine) as session:
                entry = session.get(ActivityLogEntry, channel_id)
                
                if not entry:
                    # No record = never had activity, include it
                    idle_webhooks.append(webhook)
                    logger.debug(
                        f"[Heartbeat] Channel {channel_id} has no activity record, "
                        "eligible for heartbeat"
                    )
                    continue
                
                # Parse last message time
                try:
                    last_msg = datetime.fromisoformat(
                        entry.last_message_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    # Invalid timestamp, include it
                    idle_webhooks.append(webhook)
                    continue
                
                # Check if idle long enough
                idle_duration = now - last_msg.replace(tzinfo=timezone.utc)
                if idle_duration < idle_threshold:
                    logger.debug(
                        f"[Heartbeat] Channel {channel_id} active "
                        f"{idle_duration.total_seconds() / 3600:.1f}h ago, skipping"
                    )
                    continue
                
                # Check cooldown
                if entry.last_heartbeat_at:
                    try:
                        last_heartbeat = datetime.fromisoformat(
                            entry.last_heartbeat_at.replace("Z", "+00:00")
                        )
                        cooldown_duration = now - last_heartbeat.replace(tzinfo=timezone.utc)
                        if cooldown_duration < cooldown_threshold:
                            logger.debug(
                                f"[Heartbeat] Channel {channel_id} on cooldown, "
                                f"{cooldown_duration.total_seconds() / 3600:.1f}h since last"
                            )
                            continue
                    except (ValueError, TypeError):
                        pass  # Invalid timestamp, proceed
                
                idle_webhooks.append(webhook)
        
        return idle_webhooks
