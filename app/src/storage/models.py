"""Shared data model for webhook records.

Used by both SQLite and future DynamoDB backends.

For SQLite: this IS the table definition (SQLModel, table=True).
For DynamoDB: this is used for serialization/deserialization only.
"""
from __future__ import annotations
from typing import Dict, Any
from datetime import datetime, timezone
import uuid
import json

from sqlmodel import SQLModel, Field


class WebhookRecord(SQLModel, table=True):
    """Webhook record for channel integrations.
    
    Stores webhook configuration for platforms like Discord and OpenWebUI.
    """
    __tablename__ = "webhooks"

    webhook_id: str = Field(
        default_factory=lambda: f"wh_{uuid.uuid4().hex[:12]}",
        primary_key=True,
    )
    conversation_id: str = Field(
        default_factory=lambda: f"conv_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    platform: str  # "discord" | "openwebui"
    label: str  # Human-readable name
    status: str = "active"  # "active" | "inactive"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    config_json: str = ""  # JSON-serialized platform config

    # --- Convenience methods for config serialization ---

    def set_config(self, config: Dict[str, Any]) -> None:
        """Serialize config dict to JSON string.
        
        Args:
            config: Configuration dictionary to store
        """
        self.config_json = json.dumps(config)

    def get_config(self) -> Dict[str, Any]:
        """Deserialize config from JSON string.
        
        Returns:
            Configuration dictionary, empty dict if not set
        """
        return json.loads(self.config_json) if self.config_json else {}
