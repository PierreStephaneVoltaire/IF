"""User facts store using LanceDB for semantic search.

Replaces ChromaDB with LanceDB for multi-instance safe storage.
Each context (conversation/channel) gets its own isolated storage.

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

Context ID format:
- OpenWebUI chat: openwebui_{chat_id}
- OpenWebUI channel: openwebui_{channel_id}
- Discord channel: discord_{channel_id}
"""
from __future__ import annotations
import uuid
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

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
    context_id: str = ""  # The conversational context
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
            "context_id": self.context_id,
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
            context_id=data.get("context_id", ""),
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
    """LanceDB-backed store for user facts with context scoping.

    Each context (conversation/channel) gets its own isolated storage.
    Provides semantic search over stored facts within a context.

    Example:
        >>> store = UserFactStore()
        >>> fact_id = store.add(
        ...     context_id="openwebui_chat123",
        ...     content="Operator prefers Python",
        ...     category=FactCategory.PREFERENCE,
        ...     source=FactSource.USER_STATED,
        ...     username="alice"
        ... )
        >>> results = store.search("openwebui_chat123", "programming preference")
        >>> print(results[0].content)
        "Operator prefers Python"
    """

    def __init__(self, base_path: str = None):
        """Initialize the user facts store.

        Args:
            base_path: Base path for LanceDB storage.
                       Can be local path or S3 URI.
                       Defaults to FACTS_BASE_PATH from environment.
        """
        # Import here to avoid circular dependency
        from .lancedb_store import UserFactStore as LanceDBStore
        self._store = LanceDBStore(base_path)

    def add(
        self,
        context_id: str,
        content: str,
        category: FactCategory | str,
        source: FactSource | str = FactSource.USER_STATED,
        username: str = "",
        confidence: float = 0.8,
        cache_key: str = "",
        metadata: Dict[str, Any] | None = None,
        fact: UserFact | None = None,
    ) -> str:
        """Store a new user fact.

        Can be called with individual parameters or with a UserFact object.

        Args:
            context_id: The context/conversation identifier
            content: The fact content text
            category: Category from FactCategory enum
            source: Source from FactSource enum
            username: The user this fact is about
            confidence: Confidence level (0.0-1.0)
            cache_key: Session/cache key where fact was captured
            metadata: Optional structured metadata
            fact: Alternative: pass a UserFact object directly

        Returns:
            The fact ID
        """
        if fact is not None:
            # Use the fact object
            context_id = fact.context_id or context_id
            content = fact.content
            category = fact.category
            source = fact.source
            username = fact.username
            confidence = fact.confidence
            cache_key = fact.cache_key
            metadata = fact.metadata
            fact_id = fact.id
            created_at = fact.created_at
            updated_at = fact.updated_at
        else:
            fact_id = None
            created_at = None
            updated_at = None

        # Convert enums to strings
        category_str = category.value if isinstance(category, FactCategory) else category
        source_str = source.value if isinstance(source, FactSource) else source

        return self._store.add(
            context_id=context_id,
            user_id=username,
            content=content,
            category=category_str,
            source=source_str,
            confidence=confidence,
            session_key=cache_key,
            metadata=metadata,
            fact_id=fact_id,
            created_at=created_at,
            updated_at=updated_at,
        )

    def search(
        self,
        context_id: str,
        query: str,
        category: FactCategory | None = None,
        username: str | None = None,
        limit: int = 5,
        active_only: bool = True
    ) -> List[UserFact]:
        """Semantic search across user facts in a context.

        Args:
            context_id: The context to search in
            query: Search query (will be embedded and compared)
            category: Optional category filter
            username: Optional user filter
            limit: Maximum number of results
            active_only: Only return active (non-superseded) facts

        Returns:
            List of matching UserFact objects, ordered by relevance
        """
        category_str = category.value if category and isinstance(category, FactCategory) else None

        results = self._store.search(
            context_id=context_id,
            query=query,
            category=category_str,
            user_id=username,
            active_only=active_only,
            limit=limit,
        )

        return [UserFact.from_dict(r) for r in results]

    def get(self, context_id: str, fact_id: str) -> UserFact | None:
        """Get a single fact by ID.

        Args:
            context_id: The context identifier
            fact_id: The unique identifier of the fact

        Returns:
            UserFact if found, None otherwise
        """
        result = self._store.get(context_id, fact_id)
        if result is None:
            return None
        return UserFact.from_dict(result)

    def supersede(
        self,
        context_id: str,
        old_fact_id: str,
        new_content: str,
        reason: str,
        cache_key: str = ""
    ) -> UserFact:
        """Supersede an old fact with new content.

        Creates a new fact inheriting category/source/username from old.
        Marks old as active=False and sets superseded_by.

        Args:
            context_id: The context identifier
            old_fact_id: ID of the fact to supersede
            new_content: New content for the replacement fact
            reason: Reason for the change (stored in metadata)
            cache_key: Cache key where the change was captured

        Returns:
            The new UserFact

        Raises:
            ValueError: If old fact not found
        """
        new_id = self._store.supersede(
            context_id=context_id,
            old_fact_id=old_fact_id,
            new_content=new_content,
            reason=reason,
            session_key=cache_key,
        )

        # Return the new fact
        new_fact = self.get(context_id, new_id)
        return new_fact

    def list_facts(
        self,
        context_id: str,
        category: FactCategory | None = None,
        username: str | None = None,
        include_history: bool = False
    ) -> List[UserFact]:
        """List all facts in a context, optionally filtered.

        Args:
            context_id: The context identifier
            category: Optional category filter
            username: Optional user filter
            include_history: Include superseded (inactive) facts

        Returns:
            List of UserFact objects
        """
        category_str = category.value if category and isinstance(category, FactCategory) else None

        results = self._store.list_facts(
            context_id=context_id,
            category=category_str,
            user_id=username,
            include_inactive=include_history,
        )

        return [UserFact.from_dict(r) for r in results]

    def remove(self, context_id: str, fact_id: str) -> bool:
        """Hard delete a fact.

        Note: Per Directive 0-1, this operation requires explicit operator
        confirmation. The tool implementation should enforce this.

        Args:
            context_id: The context identifier
            fact_id: The unique identifier of the fact to remove

        Returns:
            True if fact was removed, False if not found
        """
        return self._store.remove(context_id, fact_id)

    @property
    def count(self) -> int:
        """Count of all facts across all contexts.

        Note: This is expensive for LanceDB. Use count_context() instead.
        """
        return self._store.count

    def count_context(self, context_id: str, active_only: bool = True) -> int:
        """Count facts in a specific context.

        Args:
            context_id: The context identifier
            active_only: Only count active facts

        Returns:
            Number of facts in the context
        """
        return self._store.count_context(context_id, active_only)

    def list_by_category(self, context_id: str, category: FactCategory) -> List[UserFact]:
        """List all facts in a specific category within a context.

        Args:
            context_id: The context identifier
            category: The category to filter by

        Returns:
            List of UserFact objects in the category
        """
        return self.list_facts(context_id, category=category, include_history=False)

    def get_recent_facts(self, context_id: str, days: int = 30, limit: int = 100) -> List[UserFact]:
        """Get facts created within the last N days in a context.

        Args:
            context_id: The context identifier
            days: Number of days to look back
            limit: Maximum number of facts to return

        Returns:
            List of recent UserFact objects
        """
        results = self._store.get_recent_facts(context_id, days, limit)
        return [UserFact.from_dict(r) for r in results]

    def get_all_facts(self, context_id: str) -> List[UserFact]:
        """Get all facts (active and inactive) in a context.

        Args:
            context_id: The context identifier

        Returns:
            List of all UserFact objects in the context
        """
        return self.list_facts(context_id, include_history=True)

    @property
    def active_count(self) -> int:
        """Count of active facts only.

        Note: This is not context-scoped. Prefer count_context().
        """
        # This is a compatibility shim - it's expensive
        return self.count  # Will return -1, but maintains API compatibility

    def log_capability_gap(
        self,
        context_id: str,
        content: str,
        trigger_context: str,
        cache_key: str = "",
        workaround: str | None = None,
    ) -> str:
        """Log a capability gap, incrementing count if exists.

        Args:
            context_id: The context identifier
            content: What the agent cannot do
            trigger_context: The specific request that triggered this gap
            cache_key: Cache key where the gap was encountered
            workaround: Any workaround suggested to the operator

        Returns:
            The gap ID
        """
        return self._store.log_capability_gap(
            context_id=context_id,
            content=content,
            trigger_context=trigger_context,
            session_key=cache_key,
            workaround=workaround,
        )

    def list_capability_gaps(self, context_id: str, min_triggers: int = 1) -> List[CapabilityGap]:
        """List all capability gaps sorted by priority.

        Args:
            context_id: The context identifier
            min_triggers: Minimum trigger count to include

        Returns:
            List of CapabilityGap objects sorted by priority score
        """
        results = self._store.list_capability_gaps(context_id, min_triggers)

        gaps = []
        for r in results:
            gap_data = r.get("gap_data", {})
            gap = CapabilityGap.from_dict(gap_data)
            gap.id = r.get("id", gap.id)
            gaps.append(gap)

        return gaps

    def add_with_categorization_tracking(
        self,
        context_id: str,
        content: str,
        category: FactCategory,
        source: FactSource = FactSource.USER_STATED,
        confidence: float = 0.8,
        cache_key: str = "",
        metadata: dict | None = None,
        username: str = "",
    ) -> str:
        """Add a fact and track categorization fit.

        If the fact doesn't fit well in the category, logs a meta observation
        for later category evolution analysis.

        Args:
            context_id: The context identifier
            content: The fact content
            category: Category to store under
            source: Source of the fact
            confidence: Confidence level
            cache_key: Session/cache key
            metadata: Optional metadata
            username: The user this fact is about

        Returns:
            The fact ID
        """
        category_str = category.value if isinstance(category, FactCategory) else category
        source_str = source.value if isinstance(source, FactSource) else source

        return self._store.add_with_categorization_tracking(
            context_id=context_id,
            user_id=username,
            content=content,
            category=category_str,
            source=source_str,
            confidence=confidence,
            session_key=cache_key,
            metadata=metadata,
        )


# Global singleton
_user_fact_store: Optional[UserFactStore] = None


def get_user_fact_store() -> UserFactStore:
    """Get the global UserFactStore instance.

    Creates the instance on first call. Subsequent calls return the same instance.

    Returns:
        The global UserFactStore instance

    Raises:
        ImportError: If lancedb is not installed
    """
    global _user_fact_store
    if _user_fact_store is None:
        _user_fact_store = UserFactStore()
    return _user_fact_store
