"""RAG-backed memory store using ChromaDB for semantic search.

This module provides a persistent vector database for storing and retrieving
operator context across sessions. Memory entries are embedded on write and
queried semantically on read.

Memory categories:
- preference: Language/framework preferences, communication style
- personal: Birthday, location, profession, roles, relationships
- skill_level: Self-reported or demonstrated understanding
- opinion: Strong stances on technologies, approaches, topics
- life_event: Job changes, moves, competitions, milestones
- future_plan: Goals, timelines, aspirations
- mental_state: Noted shifts in mood, stress, outlook
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from config import MEMORY_DB_PATH


@dataclass
class MemoryEntry:
    """A single memory entry stored in the vector database.
    
    Attributes:
        id: Unique identifier for the memory
        content: The text content to be embedded and searched
        category: Category for filtering (preference, personal, etc.)
        created_at: ISO timestamp when the memory was created
        metadata: Additional metadata fields
    """
    id: str
    content: str
    category: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "created_at": self.created_at,
            **self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryEntry:
        """Create from dictionary."""
        # Extract known fields
        id_val = data.pop("id")
        content = data.pop("content")
        category = data.pop("category")
        created_at = data.pop("created_at")
        
        # Remaining fields become metadata
        return cls(
            id=id_val,
            content=content,
            category=category,
            created_at=created_at,
            metadata=data
        )


class MemoryStore:
    """RAG-backed memory store using ChromaDB.
    
    Provides semantic search over stored memories. The database runs in
    embedded mode (no separate server process) and persists to MEMORY_DB_PATH.
    
    Example:
        >>> store = MemoryStore()
        >>> store.add("Operator prefers Python over JavaScript", "preference")
        >>> results = store.search("programming language preference")
        >>> print(results[0].content)
        "Operator prefers Python over JavaScript"
    """
    
    def __init__(self, db_path: str = None):
        """Initialize the memory store.
        
        Args:
            db_path: Path to ChromaDB persistent storage directory.
                     Defaults to MEMORY_DB_PATH from config.
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is required for memory storage. "
                "Install with: pip install chromadb"
            )
        
        self.db_path = db_path or MEMORY_DB_PATH
        
        # Ensure directory exists
        os.makedirs(self.db_path, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create the memories collection
        self.collection = self.client.get_or_create_collection(
            name="memories",
            metadata={"description": "Operator memory store"}
        )
    
    def add(
        self,
        content: str,
        category: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """Add a new memory entry.
        
        Args:
            content: The text content to store and embed
            category: Category for filtering (preference, personal, etc.)
            metadata: Optional additional metadata
            
        Returns:
            The created MemoryEntry
        """
        # Generate unique ID
        memory_id = str(uuid.uuid4())
        
        # Create timestamp
        created_at = datetime.utcnow().isoformat() + "Z"
        
        # Build metadata dict
        full_metadata = {
            "category": category,
            "created_at": created_at,
            **(metadata or {})
        }
        
        # Add to ChromaDB (embedding happens automatically)
        self.collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[full_metadata]
        )
        
        return MemoryEntry(
            id=memory_id,
            content=content,
            category=category,
            created_at=created_at,
            metadata=metadata or {}
        )
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        category_filter: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Semantic search across stored memories.
        
        Args:
            query: Search query (will be embedded and compared)
            n_results: Maximum number of results to return
            category_filter: Optional category to filter results
            
        Returns:
            List of matching MemoryEntry objects, ordered by relevance
        """
        # Build where clause for category filtering
        where = None
        if category_filter:
            where = {"category": category_filter}
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert results to MemoryEntry objects
        entries = []
        if results["ids"] and results["ids"][0]:
            for i, memory_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i]
                metadata = results["metadatas"][0][i]
                
                # Extract category and created_at from metadata
                category = metadata.pop("category")
                created_at = metadata.pop("created_at")
                
                entries.append(MemoryEntry(
                    id=memory_id,
                    content=content,
                    category=category,
                    created_at=created_at,
                    metadata=metadata
                ))
        
        return entries
    
    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a specific memory by ID.
        
        Args:
            memory_id: The unique identifier of the memory
            
        Returns:
            MemoryEntry if found, None otherwise
        """
        results = self.collection.get(
            ids=[memory_id],
            include=["documents", "metadatas"]
        )
        
        if not results["ids"]:
            return None
        
        content = results["documents"][0]
        metadata = results["metadatas"][0]
        
        # Extract category and created_at from metadata
        category = metadata.pop("category")
        created_at = metadata.pop("created_at")
        
        return MemoryEntry(
            id=memory_id,
            content=content,
            category=category,
            created_at=created_at,
            metadata=metadata
        )
    
    def remove(self, memory_id: str) -> bool:
        """Remove a memory by ID.
        
        Args:
            memory_id: The unique identifier of the memory to remove
            
        Returns:
            True if memory was removed, False if it didn't exist
            
        Note:
            Per Directive 0-1, this operation requires explicit operator
            confirmation. The tool implementation should enforce this.
        """
        try:
            # Check if memory exists first
            existing = self.get(memory_id)
            if not existing:
                return False
            
            # Remove from ChromaDB
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False
    
    def list_all(
        self,
        category_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[MemoryEntry]:
        """List all memories, optionally filtered by category.
        
        Args:
            category_filter: Optional category to filter results
            limit: Maximum number of results to return
            
        Returns:
            List of MemoryEntry objects
        """
        # Build where clause for category filtering
        where = None
        if category_filter:
            where = {"category": category_filter}
        
        # Get all items from collection
        results = self.collection.get(
            limit=limit,
            where=where,
            include=["documents", "metadatas"]
        )
        
        # Convert to MemoryEntry objects
        entries = []
        if results["ids"]:
            for i, memory_id in enumerate(results["ids"]):
                content = results["documents"][i]
                metadata = results["metadatas"][i]
                
                # Extract category and created_at from metadata
                category = metadata.pop("category")
                created_at = metadata.pop("created_at")
                
                entries.append(MemoryEntry(
                    id=memory_id,
                    content=content,
                    category=category,
                    created_at=created_at,
                    metadata=metadata
                ))
        
        return entries
    
    def count(self) -> int:
        """Get the total number of stored memories.
        
        Returns:
            Count of memories in the store
        """
        return self.collection.count()
    
    def clear(self) -> None:
        """Remove all memories from the store.
        
        Warning:
            This is a destructive operation. Per Directive 0-1, this
            requires explicit operator confirmation.
        """
        # Delete and recreate the collection
        self.client.delete_collection("memories")
        self.collection = self.client.create_collection(
            name="memories",
            metadata={"description": "Operator memory store"}
        )


# Global singleton instance
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get the global MemoryStore instance.
    
    Creates the instance on first call. Subsequent calls return the same instance.
    
    Returns:
        The global MemoryStore instance
    """
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


# Convenience functions for direct use
def search_memories(query: str, n_results: int = 5) -> List[MemoryEntry]:
    """Search memories using the global store.
    
    Args:
        query: Search query
        n_results: Maximum number of results
        
    Returns:
        List of matching MemoryEntry objects
    """
    return get_memory_store().search(query, n_results)


def add_memory(content: str, category: str, metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
    """Add a memory using the global store.
    
    Args:
        content: Memory content
        category: Memory category
        metadata: Optional metadata
        
    Returns:
        The created MemoryEntry
    """
    return get_memory_store().add(content, category, metadata)


def remove_memory(memory_id: str) -> bool:
    """Remove a memory using the global store.
    
    Args:
        memory_id: ID of memory to remove
        
    Returns:
        True if removed, False if not found
    """
    return get_memory_store().remove(memory_id)
