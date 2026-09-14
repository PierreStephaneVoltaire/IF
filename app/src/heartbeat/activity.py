




from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from storage.models import WebhookRecord
    from storage.models import ActivityLogEntry

logger = logging.getLogger(__name__)

class ActivityTracker:










    
    def __init__(self, backend):





        self.backend = backend
    
    def record_activity(
        self,
        cache_key: str,
        webhook_id: str | None = None
    ) -> None:









        self.backend.record_activity(cache_key, webhook_id)
        
        logger.debug(f"[Activity] Recorded for {cache_key}")
    
    def record_heartbeat(self, cache_key: str) -> None:





        self.backend.record_heartbeat(cache_key)
        
        logger.debug(f"[Heartbeat] Recorded for {cache_key}")
    
    def get_idle_webhooks(
        self,
        active_webhooks: List["WebhookRecord"],
        idle_threshold_hours: float,
        cooldown_hours: float,
    ) -> List["WebhookRecord"]:














        idle_threshold = timedelta(hours=idle_threshold_hours)
        cooldown_threshold = timedelta(hours=cooldown_hours)
        now = datetime.now(timezone.utc)
        
        idle_webhooks = []
        
        for webhook in active_webhooks:
            config = webhook.get_config()
            channel_id = config.get("channel_id")
            if not channel_id:
                continue
            
            entry = self.backend.get_activity(channel_id)
            if not entry:
                idle_webhooks.append(webhook)
                logger.debug(
                    f"[Heartbeat] Channel {channel_id} has no activity record, "
                    "eligible for heartbeat"
                )
                continue

            last_message_at = entry.last_message_at if hasattr(entry, "last_message_at") else entry.get("last_message_at")
            last_heartbeat_at = entry.last_heartbeat_at if hasattr(entry, "last_heartbeat_at") else entry.get("last_heartbeat_at")

            try:
                last_msg = datetime.fromisoformat(last_message_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                idle_webhooks.append(webhook)
                continue

            idle_duration = now - last_msg.replace(tzinfo=timezone.utc)
            if idle_duration < idle_threshold:
                logger.debug(
                    f"[Heartbeat] Channel {channel_id} active "
                    f"{idle_duration.total_seconds() / 3600:.1f}h ago, skipping"
                )
                continue

            if last_heartbeat_at:
                try:
                    last_heartbeat = datetime.fromisoformat(last_heartbeat_at.replace("Z", "+00:00"))
                    cooldown_duration = now - last_heartbeat.replace(tzinfo=timezone.utc)
                    if cooldown_duration < cooldown_threshold:
                        logger.debug(
                            f"[Heartbeat] Channel {channel_id} on cooldown, "
                            f"{cooldown_duration.total_seconds() / 3600:.1f}h since last"
                        )
                        continue
                except (ValueError, TypeError):
                    pass

            idle_webhooks.append(webhook)
        
        return idle_webhooks
