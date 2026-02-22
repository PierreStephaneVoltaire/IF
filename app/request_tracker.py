"""Request tracking for handling HTTP interrupts and resumption.

This module provides:
- Request ID tracking for idempotency
- In-flight request management
- Checkpoint-aware request handling
- Automatic resume from last checkpoint on reconnection
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4


class RequestStatus(str, Enum):
    """Status of a request."""
    PENDING = "pending"           # Request received, not yet processing
    PROCESSING = "processing"     # Currently being processed
    INTERRUPTED = "interrupted"   # HTTP connection dropped during processing
    WAITING_INPUT = "waiting_input"  # Waiting for user input (checkpoint)
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Failed with error


@dataclass
class TrackedRequest:
    """A tracked request with metadata and status."""
    request_id: str
    chat_id: str
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
    checkpoint_id: Optional[str] = None
    last_node: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "chat_id": self.chat_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "checkpoint_id": self.checkpoint_id,
            "last_node": self.last_node,
            "error": self.error,
            "metadata": self.metadata,
        }


class RequestTracker:
    """Tracks in-flight requests and their status.
    
    This enables:
    - Idempotent request handling
    - Resume from last checkpoint on reconnection
    - Detection of duplicate requests
    - Monitoring of request lifecycle
    """
    
    def __init__(self, max_age_seconds: int = 3600):
        """Initialize the request tracker.
        
        Args:
            max_age_seconds: Maximum age of tracked requests before cleanup
        """
        self._requests: Dict[str, TrackedRequest] = {}
        self._chat_to_request: Dict[str, str] = {}  # chat_id -> request_id
        self._max_age_seconds = max_age_seconds
        self._lock = asyncio.Lock()
    
    async def create_request(
        self,
        chat_id: str,
        request_id: Optional[str] = None,
    ) -> TrackedRequest:
        """Create a new tracked request.
        
        Args:
            chat_id: The conversation/chat ID
            request_id: Optional specific request ID (for idempotency)
            
        Returns:
            TrackedRequest instance
        """
        async with self._lock:
            # Check if there's an existing request for this chat
            if chat_id in self._chat_to_request:
                existing_id = self._chat_to_request[chat_id]
                existing = self._requests.get(existing_id)
                
                # If request is still processing or waiting, return it
                if existing and existing.status in (
                    RequestStatus.PROCESSING,
                    RequestStatus.WAITING_INPUT,
                    RequestStatus.PENDING,
                ):
                    return existing
            
            # Create new request
            now = datetime.utcnow()
            tracked = TrackedRequest(
                request_id=request_id or str(uuid4()),
                chat_id=chat_id,
                status=RequestStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            
            self._requests[tracked.request_id] = tracked
            self._chat_to_request[chat_id] = tracked.request_id
            
            return tracked
    
    async def get_request(self, request_id: str) -> Optional[TrackedRequest]:
        """Get a tracked request by ID."""
        return self._requests.get(request_id)
    
    async def get_request_for_chat(self, chat_id: str) -> Optional[TrackedRequest]:
        """Get the current tracked request for a chat."""
        request_id = self._chat_to_request.get(chat_id)
        if request_id:
            return self._requests.get(request_id)
        return None
    
    async def update_request(
        self,
        request_id: str,
        status: Optional[RequestStatus] = None,
        checkpoint_id: Optional[str] = None,
        last_node: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[TrackedRequest]:
        """Update a tracked request.
        
        Args:
            request_id: The request ID to update
            status: New status (optional)
            checkpoint_id: Current checkpoint ID (optional)
            last_node: Last executed node (optional)
            error: Error message if failed (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            Updated TrackedRequest or None if not found
        """
        async with self._lock:
            tracked = self._requests.get(request_id)
            if not tracked:
                return None
            
            if status:
                tracked.status = status
            if checkpoint_id:
                tracked.checkpoint_id = checkpoint_id
            if last_node:
                tracked.last_node = last_node
            if error:
                tracked.error = error
            if metadata:
                tracked.metadata.update(metadata)
            
            tracked.updated_at = datetime.utcnow()
            
            # If completed or failed, remove from chat mapping
            if status in (RequestStatus.COMPLETED, RequestStatus.FAILED):
                if tracked.chat_id in self._chat_to_request:
                    if self._chat_to_request[tracked.chat_id] == request_id:
                        del self._chat_to_request[tracked.chat_id]
            
            return tracked
    
    async def mark_interrupted(self, request_id: str) -> Optional[TrackedRequest]:
        """Mark a request as interrupted (HTTP connection dropped)."""
        return await self.update_request(
            request_id,
            status=RequestStatus.INTERRUPTED,
        )
    
    async def mark_processing(self, request_id: str) -> Optional[TrackedRequest]:
        """Mark a request as processing."""
        return await self.update_request(
            request_id,
            status=RequestStatus.PROCESSING,
        )
    
    async def mark_waiting_input(
        self,
        request_id: str,
        checkpoint_id: Optional[str] = None,
    ) -> Optional[TrackedRequest]:
        """Mark a request as waiting for user input."""
        return await self.update_request(
            request_id,
            status=RequestStatus.WAITING_INPUT,
            checkpoint_id=checkpoint_id,
        )
    
    async def mark_completed(self, request_id: str) -> Optional[TrackedRequest]:
        """Mark a request as completed."""
        return await self.update_request(
            request_id,
            status=RequestStatus.COMPLETED,
        )
    
    async def mark_failed(
        self,
        request_id: str,
        error: str,
    ) -> Optional[TrackedRequest]:
        """Mark a request as failed."""
        return await self.update_request(
            request_id,
            status=RequestStatus.FAILED,
            error=error,
        )
    
    async def can_resume(self, chat_id: str) -> bool:
        """Check if a conversation can be resumed.
        
        Args:
            chat_id: The conversation ID
            
        Returns:
            True if there's an interruptable or waiting request
        """
        tracked = await self.get_request_for_chat(chat_id)
        if not tracked:
            return False
        
        return tracked.status in (
            RequestStatus.INTERRUPTED,
            RequestStatus.WAITING_INPUT,
        )
    
    async def cleanup_old_requests(self) -> int:
        """Remove old completed/failed requests.
        
        Returns:
            Number of requests removed
        """
        async with self._lock:
            now = datetime.utcnow()
            to_remove = []
            
            for request_id, tracked in self._requests.items():
                age = (now - tracked.updated_at).total_seconds()
                if age > self._max_age_seconds and tracked.status in (
                    RequestStatus.COMPLETED,
                    RequestStatus.FAILED,
                    RequestStatus.INTERRUPTED,
                ):
                    to_remove.append(request_id)
            
            for request_id in to_remove:
                del self._requests[request_id]
                # Remove from chat mapping if present
                for chat_id, rid in list(self._chat_to_request.items()):
                    if rid == request_id:
                        del self._chat_to_request[chat_id]
            
            return len(to_remove)
    
    async def list_active_requests(self) -> List[TrackedRequest]:
        """List all active (non-completed/failed) requests."""
        return [
            req for req in self._requests.values()
            if req.status not in (RequestStatus.COMPLETED, RequestStatus.FAILED)
        ]


# Global request tracker instance
_request_tracker: Optional[RequestTracker] = None


def get_request_tracker() -> RequestTracker:
    """Get the global request tracker instance."""
    global _request_tracker
    if _request_tracker is None:
        _request_tracker = RequestTracker()
    return _request_tracker
