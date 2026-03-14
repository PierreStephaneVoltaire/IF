"""LanceDB-backed store for user facts.

Provides context-scoped storage with semantic search capabilities.
Each context_id gets its own isolated LanceDB table.

Context ID format:
- OpenWebUI chat: openwebui_{chat_id}
- OpenWebUI channel: openwebui_{channel_id}
- Discord channel: discord_{channel_id}
"""
from __future__ import annotations
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

try:
    import lancedb
    from lancedb.pydantic import LanceModel, Vector
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    # Define placeholder types for type hints
    LanceModel = object
    Vector = lambda dim: None

from .embeddings import embed, get_embedding_dimension

logger = logging.getLogger(__name__)

# Import config with fallback
try:
    from config import FACTS_BASE_PATH
except ImportError:
    FACTS_BASE_PATH = os.getenv("FACTS_BASE_PATH", "./data/facts")


def _get_db_path(context_id: str) -> str:
    """Get the database path for a context.

    Args:
        context_id: The context identifier

    Returns:
        Path to the LanceDB database for this context
    """
    return f"{FACTS_BASE_PATH}/{context_id}"


class UserFactSchema(LanceModel):
    """LanceDB schema for user facts.

    This defines the table structure for LanceDB storage.
    """
    id: str
    context_id: str
    user_id: str
    content: str
    vector: Vector(get_embedding_dimension())
    category: str
    source: str
    confidence: float
    active: bool
    superseded_by: Optional[str] = None
    created_at: str
    updated_at: str
    session_key: Optional[str] = None
    metadata_json: str = "{}"

    class Config:
        # Allow extra fields for future compatibility
        extra = "ignore"


# Table cache - keyed by context_id
_tables: Dict[str, Any] = {}  # lancedb.Table


def get_table(context_id: str) -> Any:
    """Get or create the LanceDB table for a context.

    Args:
        context_id: The context identifier

    Returns:
        LanceDB Table for this context

    Raises:
        ImportError: If lancedb is not installed
    """
    if not LANCEDB_AVAILABLE:
        raise ImportError(
            "lancedb is required for user facts storage. "
            "Install with: pip install lancedb"
        )

    global _tables

    if context_id not in _tables:
        db_path = _get_db_path(context_id)

        # Create directory for local paths (not needed for S3)
        if not db_path.startswith("s3://"):
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

        db = lancedb.connect(db_path)

        table_name = "facts"
        if table_name not in db.table_names():
            # Create new table with schema
            _tables[context_id] = db.create_table(
                table_name,
                schema=UserFactSchema
            )
            logger.info(f"Created LanceDB table for context: {context_id}")
        else:
            _tables[context_id] = db.open_table(table_name)
            logger.debug(f"Opened existing LanceDB table for context: {context_id}")

    return _tables[context_id]


def clear_table_cache():
    """Clear the table cache.

    Useful for testing or when tables need to be re-opened.
    """
    global _tables
    _tables = {}


class UserFactStore:
    """LanceDB-backed store for user facts with context scoping.

    Each context (conversation/channel) gets its own isolated storage.
    Provides semantic search over stored facts within a context.

    Example:
        >>> store = UserFactStore()
        >>> store.add(
        ...     context_id="openwebui_chat123",
        ...     user_id="alice",
        ...     content="Operator prefers Python",
        ...     category="preference",
        ...     source="user_stated"
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
        if not LANCEDB_AVAILABLE:
            raise ImportError(
                "lancedb is required for user facts storage. "
                "Install with: pip install lancedb"
            )

        self.base_path = base_path or FACTS_BASE_PATH
        logger.info(f"UserFactStore initialized with base path: {self.base_path}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a LanceDB row to a dictionary for UserFact.from_dict().

        Args:
            row: Row from LanceDB query

        Returns:
            Dictionary suitable for UserFact.from_dict()
        """
        result = dict(row)
        # Remove vector from result (not needed for UserFact)
        result.pop("vector", None)
        # Convert metadata_json to metadata dict
        if "metadata_json" in result:
            try:
                result["metadata"] = json.loads(result.get("metadata_json", "{}") or "{}")
            except json.JSONDecodeError:
                result["metadata"] = {}
            del result["metadata_json"]
        # Map user_id to username for backward compatibility
        if "user_id" in result:
            result["username"] = result["user_id"]
        # Map session_key to cache_key for backward compatibility
        if "session_key" in result:
            result["cache_key"] = result["session_key"]
        return result

    def _build_filter(
        self,
        active_only: bool = True,
        category: str | None = None,
        user_id: str | None = None
    ) -> str | None:
        """Build a SQL-style filter string for LanceDB queries.

        Args:
            active_only: Filter to active facts only
            category: Optional category filter
            user_id: Optional user filter

        Returns:
            Filter string or None
        """
        conditions = []
        if active_only:
            conditions.append("active = true")
        if category:
            conditions.append(f"category = '{category}'")
        if user_id:
            conditions.append(f"user_id = '{user_id}'")

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return " AND ".join(conditions)

    # -------------------------------------------------------------------------
    # Core CRUD Methods
    # -------------------------------------------------------------------------

    def add(
        self,
        context_id: str,
        user_id: str,
        content: str,
        category: str,
        source: str,
        confidence: float = 0.8,
        session_key: str | None = None,
        metadata: Dict[str, Any] | None = None,
        fact_id: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ) -> str:
        """Store a new user fact.

        Args:
            context_id: The context/conversation identifier
            user_id: The user this fact is about
            content: The fact content text
            category: Category from FactCategory enum
            source: Source from FactSource enum
            confidence: Confidence level (0.0-1.0)
            session_key: Session/cache key where fact was captured
            metadata: Optional structured metadata
            fact_id: Optional fact ID (auto-generated if not provided)
            created_at: Optional creation timestamp
            updated_at: Optional update timestamp

        Returns:
            The fact ID
        """
        now = datetime.now(timezone.utc).isoformat()
        fact_id = fact_id or str(uuid.uuid4())
        created_at = created_at or now
        updated_at = updated_at or now

        # Generate embedding
        vector = embed(content)

        # Build row data
        row = {
            "id": fact_id,
            "context_id": context_id,
            "user_id": user_id,
            "content": content,
            "vector": vector,
            "category": category,
            "source": source,
            "confidence": confidence,
            "active": True,
            "superseded_by": None,
            "created_at": created_at,
            "updated_at": updated_at,
            "session_key": session_key,
            "metadata_json": json.dumps(metadata) if metadata else "{}",
        }

        table = get_table(context_id)
        table.add([row])

        logger.debug(f"Stored fact: [{category}] {content[:50]}... in context {context_id}")
        return fact_id

    def get(self, context_id: str, fact_id: str) -> Dict[str, Any] | None:
        """Get a single fact by ID.

        Args:
            context_id: The context identifier
            fact_id: The fact ID

        Returns:
            Fact dictionary or None if not found
        """
        table = get_table(context_id)

        # LanceDB uses search with filter for ID lookup
        results = table.search().where(f"id = '{fact_id}'").limit(1).to_list()

        if not results:
            return None

        return self._row_to_dict(results[0])

    def remove(self, context_id: str, fact_id: str) -> bool:
        """Hard delete a fact.

        Note: Per Directive 0-1, this operation requires explicit operator
        confirmation. The tool implementation should enforce this.

        Args:
            context_id: The context identifier
            fact_id: The fact ID to remove

        Returns:
            True if fact was removed, False if not found
        """
        try:
            table = get_table(context_id)

            # Check if fact exists
            existing = self.get(context_id, fact_id)
            if not existing:
                return False

            table.delete(f"id = '{fact_id}'")
            logger.info(f"Removed fact {fact_id} from context {context_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to remove fact {fact_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Search Methods
    # -------------------------------------------------------------------------

    def search(
        self,
        context_id: str,
        query: str,
        category: str | None = None,
        user_id: str | None = None,
        active_only: bool = True,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Semantic search across facts in a context.

        Args:
            context_id: The context to search in
            query: Search query (will be embedded and compared)
            category: Optional category filter
            user_id: Optional user filter
            active_only: Only return active (non-superseded) facts
            limit: Maximum number of results

        Returns:
            List of matching fact dictionaries, ordered by relevance
        """
        table = get_table(context_id)

        # Generate query embedding
        query_vector = embed(query)

        # Build search
        search = table.search(query_vector).limit(limit)

        # Apply filters
        filter_str = self._build_filter(active_only, category, user_id)
        if filter_str:
            search = search.where(filter_str)

        results = search.to_list()

        return [self._row_to_dict(row) for row in results]

    def list_facts(
        self,
        context_id: str,
        category: str | None = None,
        user_id: str | None = None,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """List all facts in a context with optional filtering.

        Args:
            context_id: The context identifier
            category: Optional category filter
            user_id: Optional user filter
            include_inactive: Include superseded facts

        Returns:
            List of fact dictionaries
        """
        table = get_table(context_id)

        # Use empty vector for listing (no semantic search)
        # LanceDB requires a vector for search, so we use a zero vector
        dim = get_embedding_dimension()
        zero_vector = [0.0] * dim

        filter_str = self._build_filter(not include_inactive, category, user_id)

        # For listing, we don't need semantic ordering
        # Use a large limit to get all facts
        search = table.search(zero_vector).limit(10000)
        if filter_str:
            search = search.where(filter_str)

        results = search.to_list()

        return [self._row_to_dict(row) for row in results]

    # -------------------------------------------------------------------------
    # Supersession Methods
    # -------------------------------------------------------------------------

    def supersede(
        self,
        context_id: str,
        old_fact_id: str,
        new_content: str,
        reason: str,
        session_key: str | None = None
    ) -> str:
        """Supersede an old fact with new content.

        Creates a new fact inheriting category/source/user_id from old.
        Marks old as active=False and sets superseded_by.

        Args:
            context_id: The context identifier
            old_fact_id: ID of the fact to supersede
            new_content: New content for the replacement fact
            reason: Reason for the change (stored in metadata)
            session_key: Session key where the change was captured

        Returns:
            The new fact ID

        Raises:
            ValueError: If old fact not found
        """
        old_fact = self.get(context_id, old_fact_id)
        if not old_fact:
            raise ValueError(f"Fact not found: {old_fact_id}")

        # Create new fact inheriting from old
        new_fact_id = self.add(
            context_id=context_id,
            user_id=old_fact.get("username", old_fact.get("user_id", "")),
            content=new_content,
            category=old_fact.get("category", "personal"),
            source=old_fact.get("source", "user_stated"),
            confidence=old_fact.get("confidence", 0.8),
            session_key=session_key or old_fact.get("cache_key", ""),
            metadata={
                **old_fact.get("metadata", {}),
                "supersession_reason": reason,
                "superseded_fact_id": old_fact_id,
            },
        )

        # Mark old fact as superseded
        table = get_table(context_id)
        table.update(
            where=f"id = '{old_fact_id}'",
            updates={
                "active": False,
                "superseded_by": new_fact_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        logger.info(f"Superseded fact {old_fact_id} -> {new_fact_id}")
        return new_fact_id

    # -------------------------------------------------------------------------
    # Capability Gap Methods
    # -------------------------------------------------------------------------

    def log_capability_gap(
        self,
        context_id: str,
        content: str,
        trigger_context: str,
        session_key: str | None = None,
        workaround: str | None = None,
    ) -> str:
        """Log a capability gap, incrementing count if exists.

        Args:
            context_id: The context identifier
            content: What the agent cannot do
            trigger_context: The specific request that triggered this gap
            session_key: Session key where the gap was encountered
            workaround: Any workaround suggested

        Returns:
            The gap ID
        """
        now = datetime.now(timezone.utc).isoformat()

        # Search for existing gap (semantic match)
        existing = self.search(
            context_id=context_id,
            query=content,
            category="capability_gap",
            limit=1,
        )

        if existing:
            gap_fact = existing[0]
            gap_metadata = gap_fact.get("metadata", {})

            # Increment existing gap
            trigger_count = gap_metadata.get("trigger_count", 0) + 1
            trigger_contexts = gap_metadata.get("trigger_contexts", [])
            trigger_contexts.append(trigger_context)

            gap_metadata["trigger_count"] = trigger_count
            gap_metadata["last_seen"] = now
            gap_metadata["trigger_contexts"] = trigger_contexts
            if workaround and not gap_metadata.get("workaround"):
                gap_metadata["workaround"] = workaround

            # Compute priority score
            gap_metadata["priority_score"] = self._compute_gap_priority(
                trigger_count, now
            )

            # Update the fact
            table = get_table(context_id)
            table.update(
                where=f"id = '{gap_fact['id']}'",
                updates={
                    "metadata_json": json.dumps(gap_metadata),
                    "updated_at": now,
                }
            )
            return gap_fact["id"]

        # Create new gap
        gap_metadata = {
            "trigger_count": 1,
            "first_seen": now,
            "last_seen": now,
            "trigger_contexts": [trigger_context],
            "workaround": workaround,
            "status": "open",
            "priority_score": 0.5,
        }

        return self.add(
            context_id=context_id,
            user_id="system",
            content=content,
            category="capability_gap",
            source="model_observed",
            confidence=0.7,
            session_key=session_key,
            metadata=gap_metadata,
        )

    def _compute_gap_priority(self, trigger_count: int, last_seen: str) -> float:
        """Compute priority score for a capability gap.

        Formula: (frequency * 0.4) + (recency * 0.3) + (impact * 0.3)
        """
        # Recency weight: e^(-λ * days_since_last_seen)
        days_since = 0.0
        if last_seen:
            try:
                last = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - last).days
            except (ValueError, TypeError):
                pass

        recency_weight = 2.718 ** (-0.05 * days_since)  # λ = 0.05

        # Normalize trigger count (assume max ~20)
        frequency_weight = min(trigger_count / 20.0, 1.0)

        # Impact estimate (placeholder)
        impact = 0.5

        return (frequency_weight * 0.4) + (recency_weight * 0.3) + (impact * 0.3)

    def list_capability_gaps(
        self,
        context_id: str,
        min_triggers: int = 1
    ) -> List[Dict[str, Any]]:
        """List all capability gaps sorted by priority.

        Args:
            context_id: The context identifier
            min_triggers: Minimum trigger count to include

        Returns:
            List of gap dictionaries sorted by priority score
        """
        facts = self.list_facts(
            context_id=context_id,
            category="capability_gap",
            include_inactive=False,
        )

        gaps = []
        for fact in facts:
            metadata = fact.get("metadata", {})
            if metadata.get("trigger_count", 0) >= min_triggers:
                fact["gap_data"] = metadata
                gaps.append(fact)

        # Sort by priority score descending
        gaps.sort(key=lambda g: g.get("gap_data", {}).get("priority_score", 0), reverse=True)
        return gaps

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    @property
    def count(self) -> int:
        """Total count of all facts across all contexts.

        Note: This requires iterating all contexts, which may be slow.
        For context-specific counts, use count_context().
        """
        # This is expensive - we need to scan all tables
        # For now, return -1 to indicate not implemented
        return -1

    def count_context(self, context_id: str, active_only: bool = True) -> int:
        """Count facts in a specific context.

        Args:
            context_id: The context identifier
            active_only: Only count active facts

        Returns:
            Number of facts in the context
        """
        facts = self.list_facts(context_id, include_inactive=not active_only)
        return len(facts)

    def get_recent_facts(
        self,
        context_id: str,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get facts created within the last N days in a context.

        Args:
            context_id: The context identifier
            days: Number of days to look back
            limit: Maximum number of facts to return

        Returns:
            List of recent fact dictionaries
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        all_facts = self.list_facts(context_id, include_inactive=False)

        recent = []
        for fact in all_facts:
            created_at_str = fact.get("created_at", "")
            if created_at_str:
                try:
                    created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    if created > cutoff:
                        recent.append(fact)
                except (ValueError, TypeError):
                    pass

        # Sort by created_at descending
        recent.sort(key=lambda f: f.get("created_at", ""), reverse=True)
        return recent[:limit]

    def add_with_categorization_tracking(
        self,
        context_id: str,
        user_id: str,
        content: str,
        category: str,
        source: str = "user_stated",
        confidence: float = 0.8,
        session_key: str | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> str:
        """Add a fact and track categorization fit.

        If the fact doesn't fit well in the category, logs a meta observation
        for later category evolution analysis.

        Args:
            context_id: The context identifier
            user_id: The user this fact is about
            content: The fact content
            category: Category to store under
            source: Source of the fact
            confidence: Confidence level
            session_key: Session key
            metadata: Optional metadata

        Returns:
            The fact ID
        """
        # Store the fact
        fact_id = self.add(
            context_id=context_id,
            user_id=user_id,
            content=content,
            category=category,
            source=source,
            confidence=confidence,
            session_key=session_key,
            metadata=metadata,
        )

        # Assess category fit (simplified - just check if category has similar facts)
        fit_score = self._assess_category_fit(context_id, content, category)

        # If fit is poor, log a meta observation for category evolution
        if fit_score < 0.6:
            try:
                content_preview = content[:80] + "..." if len(content) > 80 else content
                meta_content = (
                    f"Fact '{content_preview}' was categorized as {category} "
                    f"but fit score was {fit_score:.2f}. This fact might belong to "
                    f"a category that doesn't exist yet."
                )

                self.add(
                    context_id=context_id,
                    user_id="system",
                    content=meta_content,
                    category="model_assessment",  # Use existing category
                    source="model_observed",
                    confidence=0.7,
                    metadata={
                        "original_fact_id": fact_id,
                        "fit_score": fit_score,
                        "categorization_tension": True,
                        "original_category": category,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to log categorization tension: {e}")

        return fact_id

    def _assess_category_fit(
        self,
        context_id: str,
        content: str,
        category: str
    ) -> float:
        """Assess how well content fits the given category.

        Args:
            context_id: The context identifier
            content: The fact content to assess
            category: The category to check fit for

        Returns:
            Fit score between 0.0 and 1.0
        """
        # Search for similar facts in this category
        similar = self.search(
            context_id=context_id,
            query=content,
            category=category,
            limit=5,
        )

        if not similar:
            # Check if this is an empty category
            existing = self.list_facts(context_id, category=category)
            if not existing:
                return 0.7  # New category, assume good fit
            return 0.5  # No similar facts, neutral score

        # More similar facts = better fit
        fit_score = min(0.6 + (len(similar) * 0.08), 0.95)
        return fit_score


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
