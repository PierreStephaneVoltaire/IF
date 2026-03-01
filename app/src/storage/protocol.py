"""Abstract store protocol.

Any backend (SQLite, DynamoDB, etc.) implements this interface.
The rest of the codebase imports ONLY this protocol.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable, List, Optional


@runtime_checkable
class WebhookStore(Protocol):
    """Protocol for webhook storage backends.
    
    Any storage backend (SQLite, DynamoDB, etc.) must implement
    this interface. The rest of the codebase uses only this protocol.
    """
    
    def create(self, record: "WebhookRecord") -> "WebhookRecord":
        """Persist a new webhook record.
        
        Args:
            record: The webhook record to persist
            
        Returns:
            The record with any generated fields populated
        """
        ...
    
    def get(self, webhook_id: str) -> Optional["WebhookRecord"]:
        """Retrieve a single webhook by its ID.
        
        Args:
            webhook_id: The unique webhook identifier
            
        Returns:
            The webhook record if found, None otherwise
        """
        ...
    
    def list_all(self) -> List["WebhookRecord"]:
        """List all webhook records regardless of status.
        
        Returns:
            List of all webhook records
        """
        ...
    
    def list_active(self) -> List["WebhookRecord"]:
        """List only records with status == 'active'.
        
        Returns:
            List of active webhook records
        """
        ...
    
    def deactivate(self, webhook_id: str) -> bool:
        """Set status to 'inactive'.
        
        Args:
            webhook_id: The unique webhook identifier
            
        Returns:
            True if the record existed and was deactivated, False otherwise
        """
        ...
