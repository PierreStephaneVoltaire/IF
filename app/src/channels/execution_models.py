from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

def floats_to_decimals(obj: Any) -> Any:


    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: floats_to_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [floats_to_decimals(v) for v in obj]
    return obj

def get_instance_identity() -> str:


    import socket
    return f"{socket.gethostname()}/{uuid.uuid4()}"


@dataclass
class DiscordOutboundMessage:

    outbound_id: str
    channel_id: str
    conversation_id: str
    task_id: str | None = None
    intent_id: str | None = None
    batch_id: str | None = None
    type: Literal[
        "social_response",
        "clarifying_question",
        "task_started",
        "task_update",
        "task_completed",
        "task_failed",
        "await_instruction",
        "cancel_confirmation",
    ] = "social_response"
    priority: int = 5
    content: str = ""
    attachments: list[dict[str, Any]] = field(default_factory=list)
    reply_to_message_id: str | None = None
    allowed_mentions: dict[str, Any] | None = None
    status: Literal["queued", "sending", "sent", "failed"] = "queued"
    send_after: str | None = None
    created_at: str = ""
    updated_at: str = ""
    discord_message_id: str | None = None
    idempotency_key: str = ""
    ttl: int | None = None
    registry_sk: str | None = None
