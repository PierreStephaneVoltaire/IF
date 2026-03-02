"""SQLite + SQLModel implementation of the WebhookStore protocol.

Uses WAL mode for safe concurrent access from listener threads + API.
"""
from __future__ import annotations
import logging
from typing import List, Optional

from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy import text

from config import STORAGE_DB_PATH
from storage.models import WebhookRecord


logger = logging.getLogger(__name__)

# Global engine reference
_engine = None


def init_sqlite() -> None:
    """Initialize SQLite engine and create tables.
    
    Called once at startup. Creates the engine and tables.
    Enables WAL mode for concurrent read/write safety.
    """
    global _engine
    _engine = create_engine(
        f"sqlite:///{STORAGE_DB_PATH}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Enable WAL mode — critical for concurrent listener threads
    with _engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.commit()

    SQLModel.metadata.create_all(_engine)
    logger.info(f"SQLite store initialized at {STORAGE_DB_PATH} (WAL mode)")


def close_sqlite() -> None:
    """Close the SQLite engine.
    
    Called at shutdown to release database connections.
    """
    global _engine
    if _engine:
        _engine.dispose()
        _engine = None
        logger.info("SQLite store closed")


class _SQLiteBackend:
    """Simple backend wrapper exposing the engine.
    
    Used by ActivityTracker and other components that need direct
    engine access.
    """
    def __init__(self):
        pass
    
    @property
    def engine(self):
        """Get the SQLite engine.
        
        Returns:
            The SQLModel/engine instance
            
        Raises:
            RuntimeError: If SQLite not initialized
        """
        if _engine is None:
            raise RuntimeError("SQLite not initialized. Call init_sqlite().")
        return _engine
    
    def get_session(self) -> Session:
        """Create a new database session.
        
        Returns:
            SQLModel Session instance
            
        Raises:
            RuntimeError: If SQLite not initialized
        """
        if _engine is None:
            raise RuntimeError("SQLite not initialized. Call init_sqlite().")
        return Session(_engine)


class SQLiteWebhookStore:
    """WebhookStore implementation backed by SQLite + SQLModel."""
    
    def __init__(self):
        """Initialize the store with a backend wrapper."""
        self._backend = _SQLiteBackend()
    
    def _session(self) -> Session:
        """Create a new database session.
        
        Returns:
            SQLModel Session instance
            
        Raises:
            RuntimeError: If SQLite not initialized
        """
        if _engine is None:
            raise RuntimeError("SQLite not initialized. Call init_sqlite().")
        return Session(_engine)

    def create(self, record: WebhookRecord) -> WebhookRecord:
        """Persist a new webhook record.
        
        Args:
            record: The webhook record to persist
            
        Returns:
            The record with any generated fields populated
        """
        with self._session() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return record

    def get(self, webhook_id: str) -> Optional[WebhookRecord]:
        """Retrieve a single webhook by its ID.
        
        Args:
            webhook_id: The unique webhook identifier
            
        Returns:
            The webhook record if found, None otherwise
        """
        with self._session() as session:
            return session.get(WebhookRecord, webhook_id)

    def list_all(self) -> List[WebhookRecord]:
        """List all webhook records regardless of status.
        
        Returns:
            List of all webhook records
        """
        with self._session() as session:
            statement = select(WebhookRecord)
            return list(session.exec(statement).all())

    def list_active(self) -> List[WebhookRecord]:
        """List only records with status == 'active'.
        
        Returns:
            List of active webhook records
        """
        with self._session() as session:
            statement = select(WebhookRecord).where(
                WebhookRecord.status == "active"
            )
            return list(session.exec(statement).all())

    def deactivate(self, webhook_id: str) -> bool:
        """Set status to 'inactive'.
        
        Args:
            webhook_id: The unique webhook identifier
            
        Returns:
            True if the record existed and was deactivated, False otherwise
        """
        with self._session() as session:
            record = session.get(WebhookRecord, webhook_id)
            if record is None:
                return False
            record.status = "inactive"
            session.add(record)
            session.commit()
            return True
