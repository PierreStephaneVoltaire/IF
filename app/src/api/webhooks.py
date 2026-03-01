"""Webhook registration, listing, and deletion endpoints.

New routes for managing channel webhooks (Discord, OpenWebUI).
"""
from __future__ import annotations
import logging
from typing import Literal, Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from storage.factory import get_webhook_store
from storage.models import WebhookRecord
from channels.manager import start_listener, stop_listener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


# ============================================================================
# Request Schemas
# ============================================================================

class DiscordConfig(BaseModel):
    """Discord webhook configuration."""
    bot_token: str = Field(..., description="Discord bot token")
    channel_id: str = Field(..., description="Discord channel ID to listen to")


class OpenWebUIConfig(BaseModel):
    """OpenWebUI webhook configuration."""
    base_url: str = Field(..., description="OpenWebUI server base URL")
    channel_id: str = Field(..., description="OpenWebUI channel ID")
    api_key: str = Field(..., description="OpenWebUI API key")


class RegisterWebhookRequest(BaseModel):
    """Request body for webhook registration."""
    platform: Literal["discord", "openwebui"] = Field(
        ..., description="Platform type"
    )
    label: str = Field(
        ..., description="Human-readable label for this channel"
    )
    discord: Optional[DiscordConfig] = Field(
        None, description="Discord configuration (required if platform is discord)"
    )
    openwebui: Optional[OpenWebUIConfig] = Field(
        None, description="OpenWebUI configuration (required if platform is openwebui)"
    )


# ============================================================================
# Response Schemas
# ============================================================================

class WebhookResponse(BaseModel):
    """Response for webhook operations."""
    webhook_id: str
    conversation_id: str
    platform: str
    label: str
    status: str


class WebhookListResponse(BaseModel):
    """Response for listing webhooks."""
    webhooks: List[WebhookResponse]
    total: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/register", response_model=WebhookResponse)
async def register_webhook(req: RegisterWebhookRequest):
    """Register a new channel webhook.
    
    Creates a webhook record in storage and starts the listener immediately.
    
    Args:
        req: Registration request with platform and configuration
        
    Returns:
        WebhookResponse with created webhook details
        
    Raises:
        HTTPException: If validation fails or registration fails
    """
    # Validate platform-specific config
    if req.platform == "discord" and req.discord is None:
        raise HTTPException(
            status_code=400,
            detail="discord config required when platform is 'discord'"
        )
    if req.platform == "openwebui" and req.openwebui is None:
        raise HTTPException(
            status_code=400,
            detail="openwebui config required when platform is 'openwebui'"
        )
    
    # Extract config
    config = (req.discord or req.openwebui).model_dump()
    
    # Create webhook record
    record = WebhookRecord(
        platform=req.platform,
        label=req.label,
    )
    record.set_config(config)
    
    # Persist to storage
    store = get_webhook_store()
    record = store.create(record)
    
    logger.info(
        f"Registered webhook {record.webhook_id} "
        f"({req.platform}, {req.label})"
    )
    
    # Start listener
    try:
        start_listener(record)
    except Exception as e:
        logger.error(f"Failed to start listener for {record.webhook_id}: {e}")
        # Don't fail the request - webhook is registered, listener can be retried
    
    return WebhookResponse(
        webhook_id=record.webhook_id,
        conversation_id=record.conversation_id,
        platform=record.platform,
        label=record.label,
        status="listening" if record.status == "active" else record.status,
    )


@router.get("/", response_model=WebhookListResponse)
async def list_all_webhooks():
    """List all registered webhooks.
    
    Returns both active and inactive webhooks.
    
    Returns:
        WebhookListResponse with all webhook records
    """
    store = get_webhook_store()
    records = store.list_all()
    
    webhooks = [
        WebhookResponse(
            webhook_id=r.webhook_id,
            conversation_id=r.conversation_id,
            platform=r.platform,
            label=r.label,
            status=r.status,
        )
        for r in records
    ]
    
    return WebhookListResponse(
        webhooks=webhooks,
        total=len(webhooks),
    )


@router.get("/active", response_model=WebhookListResponse)
async def list_active_webhooks():
    """List only active webhooks.
    
    Returns:
        WebhookListResponse with active webhook records
    """
    store = get_webhook_store()
    records = store.list_active()
    
    webhooks = [
        WebhookResponse(
            webhook_id=r.webhook_id,
            conversation_id=r.conversation_id,
            platform=r.platform,
            label=r.label,
            status=r.status,
        )
        for r in records
    ]
    
    return WebhookListResponse(
        webhooks=webhooks,
        total=len(webhooks),
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(webhook_id: str):
    """Get a specific webhook by ID.
    
    Args:
        webhook_id: Webhook ID to retrieve
        
    Returns:
        WebhookResponse for the requested webhook
        
    Raises:
        HTTPException: If webhook not found
    """
    store = get_webhook_store()
    record = store.get(webhook_id)
    
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Webhook not found: {webhook_id}"
        )
    
    return WebhookResponse(
        webhook_id=record.webhook_id,
        conversation_id=record.conversation_id,
        platform=record.platform,
        label=record.label,
        status=record.status,
    )


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """Deactivate a webhook.
    
    Stops the listener and marks the webhook as inactive.
    The webhook record is retained for audit purposes.
    
    Args:
        webhook_id: Webhook ID to deactivate
        
    Returns:
        Dict with status and webhook_id
        
    Raises:
        HTTPException: If webhook not found
    """
    store = get_webhook_store()
    record = store.get(webhook_id)
    
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Webhook not found: {webhook_id}"
        )
    
    # Stop listener
    stop_listener(webhook_id)
    
    # Mark as inactive
    store.deactivate(webhook_id)
    
    logger.info(f"Deactivated webhook {webhook_id}")
    
    return {
        "status": "deactivated",
        "webhook_id": webhook_id,
    }


@router.post("/{webhook_id}/restart")
async def restart_webhook(webhook_id: str):
    """Restart a deactivated webhook.
    
    Starts the listener for an existing webhook record.
    
    Args:
        webhook_id: Webhook ID to restart
        
    Returns:
        Dict with status and webhook_id
        
    Raises:
        HTTPException: If webhook not found or already active
    """
    store = get_webhook_store()
    record = store.get(webhook_id)
    
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Webhook not found: {webhook_id}"
        )
    
    if record.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Webhook is not active: {webhook_id}"
        )
    
    # Start listener
    try:
        start_listener(record)
    except Exception as e:
        logger.error(f"Failed to restart listener for {webhook_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start listener: {e}"
        )
    
    return {
        "status": "restarted",
        "webhook_id": webhook_id,
    }
