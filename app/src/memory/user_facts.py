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
import json
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
    # ── Operator Facts (existing) ──
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
    
    # ── Agent Self-Knowledge ──
    AGENT_IDENTITY = "agent_identity"        # Name, purpose, design facts
    AGENT_OPINION = "agent_opinion"          # Agent's formed positions
    AGENT_PRINCIPLE = "agent_principle"      # Operating principles learned
    
    # ── Capability Tracking ──
    CAPABILITY_GAP = "capability_gap"        # Things agent can't do
    TOOL_SUGGESTION = "tool_suggestion"      # Derived from frequent gaps
    
    # ── Opinion Pairs ──
    OPINION_PAIR = "opinion_pair"            # User opinion + agent response
    
    # ── Operator Growth ──
    MISCONCEPTION = "misconception"          # Things user got wrong
    INTEREST_AREA = "interest_area"          # Topics they gravitate toward
    
    # ── Session Reflection ──
    SESSION_REFLECTION = "session_reflection"  # Post-session learnings


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
    metadata: Dict[str, Any] = field(default_factory=dict)  # For structured data (CapabilityGap, OpinionPair, etc.)

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
            "metadata": self.metadata,
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
            metadata=data.get("metadata", {}),
        )


@dataclass
class CapabilityGap:
    """Tracks things the agent cannot do natively."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""                            # "Cannot send emails"
    trigger_count: int = 1                      # How many times hit
    first_seen: str = ""
    last_seen: str = ""
    trigger_contexts: list[str] = field(default_factory=list)  # When it was hit
    workaround: str | None = None               # Suggested workaround
    suggested_tool: str | None = None           # "email_mcp_server"
    acceptance_criteria: list[str] = field(default_factory=list)
    status: str = "open"                        # "open" | "workaround_exists" | "resolved"
    priority_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "trigger_count": self.trigger_count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "trigger_contexts": self.trigger_contexts,
            "workaround": self.workaround,
            "suggested_tool": self.suggested_tool,
            "acceptance_criteria": self.acceptance_criteria,
            "status": self.status,
            "priority_score": self.priority_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityGap":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data.get("content", ""),
            trigger_count=data.get("trigger_count", 1),
            first_seen=data.get("first_seen", ""),
            last_seen=data.get("last_seen", ""),
            trigger_contexts=data.get("trigger_contexts", []),
            workaround=data.get("workaround"),
            suggested_tool=data.get("suggested_tool"),
            acceptance_criteria=data.get("acceptance_criteria", []),
            status=data.get("status", "open"),
            priority_score=data.get("priority_score", 0.0),
        )


@dataclass
class OpinionPair:
    """Tracks user opinions alongside agent responses."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""                              # "Microservices vs monoliths"
    user_position: str = ""                      # "Microservices are always better"
    agent_position: str = ""                     # "Disagree. Monoliths are correct default"
    agent_reasoning: str = ""                    # The why
    agent_confidence: float = 0.7               # 0.0-1.0
    agreement_level: str = "partial"             # "agree" | "partial" | "disagree" | "insufficient_data"
    evolution: list[dict] = field(default_factory=list)  # Track position changes
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "user_position": self.user_position,
            "agent_position": self.agent_position,
            "agent_reasoning": self.agent_reasoning,
            "agent_confidence": self.agent_confidence,
            "agreement_level": self.agreement_level,
            "evolution": self.evolution,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpinionPair":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            user_position=data.get("user_position", ""),
            agent_position=data.get("agent_position", ""),
            agent_reasoning=data.get("agent_reasoning", ""),
            agent_confidence=data.get("agent_confidence", 0.7),
            agreement_level=data.get("agreement_level", "partial"),
            evolution=data.get("evolution", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class Misconception:
    """Tracks operator factual misunderstandings."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""                              # "CIDR notation"
    what_they_said: str = ""                     # "A /24 gives you 512 addresses"
    what_is_correct: str = ""                    # "A /24 gives you 256 addresses"
    domain: str = ""                             # "networking"
    severity: str = "minor"                      # "minor" | "moderate" | "critical"
    corrected_in_session: bool = True            # Did we correct it live?
    recurrence_count: int = 0                   # How many times this came up
    suggested_resources: list[str] = field(default_factory=list)
    created_at: str = ""
    last_seen: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "what_they_said": self.what_they_said,
            "what_is_correct": self.what_is_correct,
            "domain": self.domain,
            "severity": self.severity,
            "corrected_in_session": self.corrected_in_session,
            "recurrence_count": self.recurrence_count,
            "suggested_resources": self.suggested_resources,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Misconception":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            topic=data.get("topic", ""),
            what_they_said=data.get("what_they_said", ""),
            what_is_correct=data.get("what_is_correct", ""),
            domain=data.get("domain", ""),
            severity=data.get("severity", "minor"),
            corrected_in_session=data.get("corrected_in_session", True),
            recurrence_count=data.get("recurrence_count", 0),
            suggested_resources=data.get("suggested_resources", []),
            created_at=data.get("created_at", ""),
            last_seen=data.get("last_seen", ""),
        )


@dataclass
class SessionReflection:
    """Post-session reflection replacing shallow conversation summaries."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""                         # conversation_id
    summary: str = ""                            # What happened
    what_worked: list[str] = field(default_factory=list)   # Approaches that worked
    what_failed: list[str] = field(default_factory=list)   # Approaches that didn't
    operator_satisfaction: str = "neutral"       # "positive" | "neutral" | "negative"
    new_facts_stored: int = 0                    # How many facts captured
    capability_gaps_hit: list[str] = field(default_factory=list)  # Gap IDs triggered
    misconceptions_found: list[str] = field(default_factory=list)  # Misconceptions corrected
    open_threads: list[str] = field(default_factory=list)   # Unresolved questions
    meta_notes: str = ""                         # Agent's free-form reflection
    preset_used: str = ""                        # Which routing preset
    preset_fit_score: float = 0.0                # Self-assessed routing accuracy
    created_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "summary": self.summary,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "operator_satisfaction": self.operator_satisfaction,
            "new_facts_stored": self.new_facts_stored,
            "capability_gaps_hit": self.capability_gaps_hit,
            "misconceptions_found": self.misconceptions_found,
            "open_threads": self.open_threads,
            "meta_notes": self.meta_notes,
            "preset_used": self.preset_used,
            "preset_fit_score": self.preset_fit_score,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionReflection":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            session_id=data.get("session_id", ""),
            summary=data.get("summary", ""),
            what_worked=data.get("what_worked", []),
            what_failed=data.get("what_failed", []),
            operator_satisfaction=data.get("operator_satisfaction", "neutral"),
            new_facts_stored=data.get("new_facts_stored", 0),
            capability_gaps_hit=data.get("capability_gaps_hit", []),
            misconceptions_found=data.get("misconceptions_found", []),
            open_threads=data.get("open_threads", []),
            meta_notes=data.get("meta_notes", ""),
            preset_used=data.get("preset_used", ""),
            preset_fit_score=data.get("preset_fit_score", 0.0),
            created_at=data.get("created_at", ""),
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
    
    def _metadata_to_dict(self, metadata: dict) -> dict:
        """Convert ChromaDB metadata back to format for UserFact.from_dict().
        
        ChromaDB only accepts primitive types in metadata, so we store
        the nested metadata dict as a JSON string. This method converts
        it back when reading.
        
        Args:
            metadata: The metadata dict from ChromaDB
            
        Returns:
            Dict suitable for spreading into UserFact.from_dict()
        """
        result = dict(metadata)
        # Convert metadata_json back to metadata dict
        if "metadata_json" in result:
            try:
                result["metadata"] = json.loads(result.get("metadata_json", "{}") or "{}")
            except json.JSONDecodeError:
                result["metadata"] = {}
            del result["metadata_json"]
        # Handle legacy "metadata" key for backward compatibility
        elif "metadata" in result and isinstance(result["metadata"], str):
            try:
                result["metadata"] = json.loads(result["metadata"] or "{}")
            except json.JSONDecodeError:
                result["metadata"] = {}
        return result
    
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
            "metadata_json": json.dumps(fact.metadata) if fact.metadata else "",
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
                    **self._metadata_to_dict(metadata)
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
            **self._metadata_to_dict(results["metadatas"][0])
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
        # Build where clause - ChromaDB requires $and for multiple conditions
        where = None
        where_conditions = []
        
        if not include_history:
            where_conditions.append({"active": True})
        if category:
            where_conditions.append({"category": category.value})
        
        # ChromaDB requires $and operator when combining multiple conditions
        if len(where_conditions) == 1:
            where = where_conditions[0]
        elif len(where_conditions) > 1:
            where = {"$and": where_conditions}
        
        results = self.collection.get(
            where=where,
            include=["documents", "metadatas"]
        )
        
        facts = []
        if results["ids"]:
            for i, fact_id in enumerate(results["ids"]):
                facts.append(UserFact.from_dict({
                    "id": fact_id,
                    "content": results["documents"][i],
                    **self._metadata_to_dict(results["metadatas"][i])
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
    
    def log_capability_gap(
        self,
        content: str,
        context: str,
        cache_key: str,
        workaround: str | None = None,
    ) -> str:
        """Log a capability gap, incrementing count if exists.
        
        Args:
            content: What the agent cannot do
            context: The specific request that triggered this gap
            cache_key: Cache key where the gap was encountered
            workaround: Any workaround suggested to the operator
            
        Returns:
            The gap ID
        """
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Search for existing gap (semantic match)
        existing = self.search(
            query=content,
            category=FactCategory.CAPABILITY_GAP,
            limit=1,
        )
        
        # Check if existing gap is semantically similar enough
        if existing:
            gap_fact = existing[0]
            gap_metadata = gap_fact.metadata if hasattr(gap_fact, 'metadata') else {}
            
            # Increment existing gap
            gap = CapabilityGap.from_dict(gap_metadata)
            gap.trigger_count += 1
            gap.last_seen = now
            gap.trigger_contexts = gap.trigger_contexts or []
            gap.trigger_contexts.append(context)
            if workaround and not gap.workaround:
                gap.workaround = workaround
            gap.priority_score = self._compute_gap_priority(gap)
            
            # Update the fact metadata
            gap_fact.metadata = gap.to_dict()
            self._update_metadata(gap_fact)
            return gap_fact.id
        
        # Create new gap
        gap = CapabilityGap(
            content=content,
            trigger_count=1,
            first_seen=now,
            last_seen=now,
            trigger_contexts=[context],
            workaround=workaround,
            status="open",
        )
        gap.priority_score = self._compute_gap_priority(gap)
        
        # Store as a fact with metadata
        fact = UserFact(
            content=content,
            category=FactCategory.CAPABILITY_GAP,
            source=FactSource.MODEL_OBSERVED,
            confidence=0.7,
            cache_key=cache_key,
            created_at=now,
            updated_at=now,
        )
        fact.metadata = gap.to_dict()
        
        self.add(fact)
        return fact.id
    
    def _compute_gap_priority(self, gap: CapabilityGap) -> float:
        """Compute priority score for a capability gap.
        
        Formula: (frequency * 0.4) + (recency * 0.3) + (impact * 0.3)
        """
        from datetime import datetime, timezone
        
        # Recency weight: e^(-λ * days_since_last_seen)
        days_since = 0.0
        if gap.last_seen:
            try:
                last = datetime.fromisoformat(gap.last_seen.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - last).days
            except (ValueError, TypeError):
                pass
        
        recency_weight = 2.718 ** (-0.05 * days_since)  # λ = 0.05
        
        # Normalize trigger count (assume max ~20)
        frequency_weight = min(gap.trigger_count / 20.0, 1.0)
        
        # Impact estimate (placeholder - could be enhanced)
        impact = 0.5
        
        return (frequency_weight * 0.4) + (recency_weight * 0.3) + (impact * 0.3)
    
    def list_capability_gaps(self, min_triggers: int = 1) -> List[CapabilityGap]:
        """List all capability gaps sorted by priority.
        
        Args:
            min_triggers: Minimum trigger count to include
            
        Returns:
            List of CapabilityGap objects sorted by priority score
        """
        facts = self.list_facts(category=FactCategory.CAPABILITY_GAP, include_history=False)
        
        gaps = []
        for fact in facts:
            gap_metadata = fact.metadata if hasattr(fact, 'metadata') else {}
            gap = CapabilityGap.from_dict(gap_metadata)
            gap.id = fact.id  # Use fact ID
            if gap.trigger_count >= min_triggers:
                gaps.append(gap)
        
        # Sort by priority score descending
        gaps.sort(key=lambda g: g.priority_score, reverse=True)
        return gaps
    
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
            "metadata_json": json.dumps(fact.metadata) if fact.metadata else "",
        }
        self.collection.update(
            ids=[fact.id],
            metadatas=[metadata]
        )
    
    def list_by_category(self, category: FactCategory) -> List[UserFact]:
        """List all facts in a specific category.
        
        Args:
            category: The category to filter by
            
        Returns:
            List of UserFact objects in the category
        """
        return self.list_facts(category=category, include_history=False)
    
    def get_recent_facts(self, days: int = 30, limit: int = 100) -> List[UserFact]:
        """Get facts created within the last N days.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of facts to return
            
        Returns:
            List of recent UserFact objects
        """
        from datetime import datetime, timezone, timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get all active facts
        all_facts = self.list_facts(include_history=False)
        
        # Filter by date
        recent = []
        for fact in all_facts:
            if fact.created_at:
                try:
                    created = datetime.fromisoformat(fact.created_at.replace("Z", "+00:00"))
                    if created > cutoff:
                        recent.append(fact)
                except (ValueError, TypeError):
                    pass
        
        # Sort by created_at descending and limit
        recent.sort(key=lambda f: f.created_at or "", reverse=True)
        return recent[:limit]
    
    def get_all_facts(self) -> List[UserFact]:
        """Get all facts (active and inactive).
        
        Returns:
            List of all UserFact objects
        """
        return self.list_facts(include_history=True)
    
    def _assess_category_fit(self, content: str, category: FactCategory) -> float:
        """Assess how well content fits the given category.
        
        Uses semantic search to find similar facts in the category
        and returns a fit score based on similarity.
        
        Args:
            content: The fact content to assess
            category: The category to check fit for
            
        Returns:
            Fit score between 0.0 and 1.0
        """
        # Search for similar facts in this category
        similar = self.search(
            query=content,
            category=category,
            limit=5
        )
        
        if not similar:
            # No similar facts in this category
            # Check if this is an empty or new category
            existing = self.list_by_category(category)
            if not existing:
                return 0.7  # New category, assume good fit
            return 0.5  # No similar facts, neutral score
        
        # If we found similar facts, it's a good sign
        # More similar facts = better fit
        fit_score = min(0.6 + (len(similar) * 0.08), 0.95)
        return fit_score
    
    def add_with_categorization_tracking(
        self,
        content: str,
        category: FactCategory,
        source: FactSource = FactSource.USER_STATED,
        confidence: float = 0.8,
        cache_key: str = "",
        metadata: dict | None = None,
    ) -> str:
        """Add a fact and track categorization fit.
        
        If the fact doesn't fit well in the category, logs a meta_observation
        for later category evolution analysis.
        
        This implements Part7 of plan.md - Category Suggestion Mechanism.
        
        Args:
            content: The fact content
            category: Category to store under
            source: Source of the fact
            confidence: Confidence level
            cache_key: Conversation cache key
            metadata: Optional metadata
            
        Returns:
            The fact ID
        """
        # Store the fact
        fact_id = self.add(
            content=content,
            category=category,
            source=source,
            confidence=confidence,
            cache_key=cache_key,
            metadata=metadata,
        )
        
        # Assess category fit
        fit_score = self._assess_category_fit(content, category)
        
        # If fit is poor, log a meta_observation for category evolution
        if fit_score < 0.6:
            try:
                content_preview = content[:80] + "..." if len(content) > 80 else content
                meta_content = (
                    f"Fact '{content_preview}' was categorized as {category.value} "
                    f"but fit score was {fit_score:.2f}. This fact might belong to "
                    f"a category that doesn't exist yet."
                )
                
                self.add(
                    content=meta_content,
                    category=FactCategory.META_OBSERVATION,
                    source=FactSource.MODEL_OBSERVED,
                    confidence=0.7,
                    metadata={
                        "original_fact_id": fact_id,
                        "fit_score": fit_score,
                        "categorization_tension": True,
                        "original_category": category.value,
                    },
                )
            except Exception as e:
                # Don't fail the main operation if meta logging fails
                import logging
                logging.getLogger(__name__).warning(
                    f"[UserFactStore] Failed to log categorization tension: {e}"
                )
        
        return fact_id


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
