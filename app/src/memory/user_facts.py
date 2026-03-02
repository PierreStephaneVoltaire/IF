"""User facts store using ChromaDB for semantic search.

Replaces the simpler memory store with a structured fact system
supporting categories, sources, and supersession.

Categories:
- personal: Name, location, profession, relationships
- preference: Language/framework preferences, communication style
- opinion: Strong stances on technologies, approaches, topics
- skill: Self-reported or demonstrated understanding
- life_event: Job changes, moves, competitions, milestones
- future_direction: Goals, timelines, aspirations
- project_direction: Current project plans and direction
- mental_state: Noted shifts in mood, stress, outlook
- conversation_summary: Auto-generated summaries of discussions
- topic_log: Domains discussed and when
- model_assessment: Agent's observations about the operator

Sources:
- user_stated: Explicitly stated by the operator
- model_observed: Observed from operator behavior
- model_assessed: Agent's assessment of operator capabilities
- conversation_derived: Extracted from conversation context
"""
from __future__ import annotations
import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from config import MEMORY_DB_PATH


logger = logging.getLogger(__name__)


class FactCategory(str, Enum):
    """Categories for user facts."""
    PERSONAL = "personal"
    PREFERENCE = "preference"
    OPINION = "opinion"
    SKILL = "skill"
    LIFE_EVENT = "life_event"
    FUTURE_DIRECTION = "future_direction"
    PROJECT_DIRECTION = "project_direction"
    MENTAL_STATE = "mental_state"
    CONVERSATION_SUMMARY = "conversation_summary"
    TOPIC_LOG = "topic_log"
    MODEL_ASSESSMENT = "model_assessment"


class FactSource(str, Enum):
    """Source of a user fact."""
    USER_STATED = "user_stated"
    MODEL_OBSERVED = "model_observed"
    MODEL_ASSESSED = "model_assessed"
    CONVERSATION_DERIVED = "conversation_derived"


@dataclass
class UserFact:
    """A single fact about the user."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    content: str = ""
    category: FactCategory = FactCategory.PERSONAL
    source: FactSource = FactSource.USER_STATED
    confidence: float = 0.8
    cache_key: str = ""  # Where this fact was captured
    created_at: str = ""
    updated_at: str = ""
    superseded_by: str | None = None
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "username": self.username,
            "content": self.content,
            "category": self.category.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "cache_key": self.cache_key,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "superseded_by": self.superseded_by,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserFact":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            username=data.get("username", ""),
            content=data.get("content", ""),
            category=FactCategory(data.get("category", "personal")),
            source=FactSource(data.get("source", "user_stated")),
            confidence=data.get("confidence", 0.8),
            cache_key=data.get("cache_key", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            superseded_by=data.get("superseded_by"),
            active=data.get("active", True),
        )


class UserFactStore:
    """ChromaDB-backed store for user facts.
    
    Provides semantic search over stored facts. The database runs in
    embedded mode and persists to MEMORY_DB_PATH.
    
    Example:
        >>> store = UserFactStore()
        >>> fact = UserFact(content="Operator prefers Python", category=FactCategory.PREFERENCE)
        >>> store.add(fact)
        >>> results = store.search("programming language preference")
        >>> print(results[0].content)
        "Operator prefers Python"
    """
    
    def __init__(self, db_path: str = None):
        """Initialize the user facts store.
        
        Args:
            db_path: Path to ChromaDB persistent storage directory.
                     Defaults to MEMORY_DB_PATH from config.
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb is required for user facts storage. "
                "Install with: pip install chromadb"
            )
        
        self.db_path = db_path or MEMORY_DB_PATH
        os.makedirs(self.db_path, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.collection = self.client.get_or_create_collection(
            name="user_facts",
            metadata={"description": "User facts store"}
        )
    
    def add(self, fact: UserFact) -> UserFact:
        """Store a new user fact.
        
        Args:
            fact: The UserFact to store
            
        Returns:
            The stored UserFact with timestamps set
        """
        if not fact.created_at:
            fact.created_at = datetime.utcnow().isoformat() + "Z"
        if not fact.updated_at:
            fact.updated_at = fact.created_at
        
        metadata = {
            "username": fact.username,
            "category": fact.category.value,
            "source": fact.source.value,
            "confidence": fact.confidence,
            "cache_key": fact.cache_key,
            "created_at": fact.created_at,
            "updated_at": fact.updated_at,
            "superseded_by": fact.superseded_by or "",
            "active": fact.active,
        }
        
        self.collection.add(
            ids=[fact.id],
            documents=[fact.content],
            metadatas=[metadata]
        )
        
        logger.debug(f"Stored fact: [{fact.category.value}] {fact.content[:50]}...")
        return fact
    
    def search(
        self,
        query: str,
        category: FactCategory | None = None,
        limit: int = 5,
        active_only: bool = True
    ) -> List[UserFact]:
        """Semantic search across user facts.
        
        Args:
            query: Search query (will be embedded and compared)
            category: Optional category filter
            limit: Maximum number of results
            active_only: Only return active (non-superseded) facts
            
        Returns:
            List of matching UserFact objects, ordered by relevance
        """
        # Build where clause - ChromaDB requires $and for multiple conditions
        where = None
        conditions = []
        if active_only:
            conditions.append({"active": True})
        if category:
            conditions.append({"category": category.value})
        
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}
        
        results = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where=where,
            include=["documents", "metadatas"]
        )
        
        facts = []
        if results["ids"] and results["ids"][0]:
            for i, fact_id in enumerate(results["ids"][0]):
                content = results["documents"][0][i]
                metadata = results["metadatas"][0][i]
                facts.append(UserFact.from_dict({
                    "id": fact_id,
                    "content": content,
                    **metadata
                }))
        
        return facts
    
    def supersede(
        self,
        old_fact_id: str,
        new_content: str,
        reason: str,
        cache_key: str
    ) -> UserFact:
        """Supersede an old fact with new content.
        
        Creates a new fact inheriting category/source/username from old.
        Marks old as active=False and sets superseded_by.
        
        Args:
            old_fact_id: ID of the fact to supersede
            new_content: New content for the replacement fact
            reason: Reason for the change (stored in metadata)
            cache_key: Cache key where the change was captured
            
        Returns:
            The new UserFact
            
        Raises:
            ValueError: If old fact not found
        """
        old_fact = self.get(old_fact_id)
        if not old_fact:
            raise ValueError(f"Fact not found: {old_fact_id}")
        
        # Create new fact inheriting from old
        new_fact = UserFact(
            username=old_fact.username,
            content=new_content,
            category=old_fact.category,
            source=old_fact.source,
            cache_key=cache_key,
            created_at=datetime.utcnow().isoformat() + "Z",
            updated_at=datetime.utcnow().isoformat() + "Z",
        )
        
        # Store new fact
        self.add(new_fact)
        
        # Mark old fact as superseded
        old_fact.superseded_by = new_fact.id
        old_fact.active = False
        old_fact.updated_at = datetime.utcnow().isoformat() + "Z"
        self._update_metadata(old_fact)
        
        logger.info(f"Superseded fact {old_fact_id} -> {new_fact.id}")
        return new_fact
    
    def get(self, fact_id: str) -> UserFact | None:
        """Get a single fact by ID.
        
        Args:
            fact_id: The unique identifier of the fact
            
        Returns:
            UserFact if found, None otherwise
        """
        results = self.collection.get(
            ids=[fact_id],
            include=["documents", "metadatas"]
        )
        
        if not results["ids"]:
            return None
        
        return UserFact.from_dict({
            "id": results["ids"][0],
            "content": results["documents"][0],
            **results["metadatas"][0]
        })
    
    def list_facts(
        self,
        category: FactCategory | None = None,
        include_history: bool = False
    ) -> List[UserFact]:
        """List all facts, optionally filtered.
        
        Args:
            category: Optional category filter
            include_history: Include superseded (inactive) facts
            
        Returns:
            List of UserFact objects
        """
        where = {}
        if not include_history:
            where["active"] = True
        if category:
            where["category"] = category.value
        
        results = self.collection.get(
            where=where if where else None,
            include=["documents", "metadatas"]
        )
        
        facts = []
        if results["ids"]:
            for i, fact_id in enumerate(results["ids"]):
                facts.append(UserFact.from_dict({
                    "id": fact_id,
                    "content": results["documents"][i],
                    **results["metadatas"][i]
                }))
        
        return facts
    
    def remove(self, fact_id: str) -> bool:
        """Hard delete a fact.
        
        Note: Per Directive 0-1, this operation requires explicit operator
        confirmation. The tool implementation should enforce this.
        
        Args:
            fact_id: The unique identifier of the fact to remove
            
        Returns:
            True if fact was removed, False if not found
        """
        try:
            existing = self.get(fact_id)
            if not existing:
                return False
            self.collection.delete(ids=[fact_id])
            logger.info(f"Removed fact {fact_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove fact {fact_id}: {e}")
            return False
    
    @property
    def count(self) -> int:
        """Count of all facts (including inactive)."""
        return self.collection.count()
    
    @property
    def active_count(self) -> int:
        """Count of active facts only."""
        results = self.collection.get(
            where={"active": True},
            include=[]
        )
        return len(results["ids"]) if results["ids"] else 0
    
    def _update_metadata(self, fact: UserFact) -> None:
        """Update metadata for an existing fact.
        
        Args:
            fact: The UserFact with updated metadata
        """
        metadata = {
            "username": fact.username,
            "category": fact.category.value,
            "source": fact.source.value,
            "confidence": fact.confidence,
            "cache_key": fact.cache_key,
            "created_at": fact.created_at,
            "updated_at": fact.updated_at,
            "superseded_by": fact.superseded_by or "",
            "active": fact.active,
        }
        self.collection.update(
            ids=[fact.id],
            metadatas=[metadata]
        )


# Global singleton
_user_fact_store: Optional[UserFactStore] = None


def get_user_fact_store() -> UserFactStore:
    """Get the global UserFactStore instance.
    
    Creates the instance on first call. Subsequent calls return the same instance.
    
    Returns:
        The global UserFactStore instance
        
    Raises:
        ImportError: If chromadb is not installed
    """
    global _user_fact_store
    if _user_fact_store is None:
        _user_fact_store = UserFactStore()
    return _user_fact_store
