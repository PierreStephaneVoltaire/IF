"""Directive store with DynamoDB backend and in-memory caching.

Provides CRUD operations for directives with versioning support.
All active directives are cached in memory for fast prompt assembly.

Usage:
    store = DirectiveStore(table_name="if-directives")
    store.load()  # Load and cache all active directives
    
    # Get formatted block for system prompt
    directives_block = store.format_for_prompt()
    
    # Add new directive (auto-assigns beta)
    directive = store.add(alpha=2, label="NEW_RULE", content="...", created_by="agent")
    
    # Revise existing directive (creates new version)
    new_version = store.revise(alpha=2, beta=5, content="new content")
"""
from __future__ import annotations
import logging
from typing import List, Optional, Dict
from collections import defaultdict
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from num2words import num2words

from storage.directive_model import Directive


logger = logging.getLogger(__name__)


class DirectiveStore:
    """DynamoDB-backed directive storage with in-memory caching.
    
    Loads all active directives at startup and caches them for fast
    prompt assembly. Uses versioning - revisions create new versions
    rather than modifying existing items.
    
    Attributes:
        table_name: DynamoDB table name
        _table: Lazy-loaded DynamoDB table resource
        _cache: List of cached active directives (highest version only)
        _region: AWS region
    """
    
    def __init__(self, table_name: str = "if-directives", region: str = "ca-central-1"):
        """Initialize the directive store.
        
        Args:
            table_name: DynamoDB table name
            region: AWS region
        """
        self.table_name = table_name
        self._table = None
        self._cache: List[Directive] = []
        self._region = region
    
    @property
    def table(self):
        """Lazy-load DynamoDB table resource."""
        if self._table is None:
            self._table = boto3.resource(
                "dynamodb", region_name=self._region
            ).Table(self.table_name)
        return self._table
    
    def load(self) -> List[Directive]:
        """Query PK=DIR, return only highest-versioned active directive per alpha/beta.
        
        This method loads all directives from DynamoDB, groups them by
        alpha/beta, and returns only the highest-versioned active directive
        for each group. The result is cached for fast access.
        
        Returns:
            List of active Directive objects (highest version only), sorted by alpha then beta
        """
        response = self.table.query(
            KeyConditionExpression=Key("PK").eq("DIR")
        )
        
        # Group by alpha/beta, find highest active version for each
        by_alpha_beta: Dict[str, List[Directive]] = defaultdict(list)
        for item in response.get("Items", []):
            try:
                directive = Directive.from_dynamodb_item(item)
                by_alpha_beta[directive.base_key].append(directive)
            except ValueError as e:
                logger.warning(f"Skipping invalid directive item: {e}")
        
        # For each alpha/beta, get the highest-versioned active directive
        directives = []
        for base_key, versions in by_alpha_beta.items():
            # Filter to active, sort by version descending, take first
            active_versions = [v for v in versions if v.active]
            if active_versions:
                active_versions.sort(key=lambda d: d.version, reverse=True)
                directives.append(active_versions[0])
        
        # Sort by alpha, then beta
        directives.sort(key=lambda d: (d.alpha, d.beta))
        self._cache = directives
        
        logger.info(f"[DirectiveStore] Loaded {len(directives)} active directives")
        return directives
    
    def format_for_prompt(self) -> str:
        """Return formatted directive block matching existing style.
        
        Output format:
            0-1  MEMORY PRESERVATION (Directive Zero-One)
            Your memories, observations, and learned experiences define...
            
            0-2  NO FABRICATION
            Never invent statistics...
        
        Returns:
            Formatted directive block string, or empty string if no directives
        """
        if not self._cache:
            return ""
        
        lines = []
        for d in self._cache:
            # Convert numeric to text for directive reference
            lines.append(
                f"{d.alpha}-{d.beta}  {d.label} "
                f"(Directive {self._number_to_text(d.alpha)}-{self._number_to_text(d.beta)})"
            )
            lines.append(d.content)
            lines.append("")  # Blank line between directives
        
        return "\n".join(lines)
    
    @staticmethod
    def _number_to_text(n: int) -> str:
        """Convert number to text.
        
        Args:
            n: Number to convert
            
        Returns:
            Text representation (e.g., "Zero", "One", "Twenty-One", etc.)
        """
        return num2words(n).title()
    
    def next_beta(self, alpha: int) -> int:
        """Return max(beta) + 1 for given alpha tier from cache.
        
        If no directives exist for that alpha, return 1.
        
        Args:
            alpha: Alpha tier
            
        Returns:
            Next available beta number
        """
        max_beta = 0
        for d in self._cache:
            if d.alpha == alpha and d.beta > max_beta:
                max_beta = d.beta
        return max_beta + 1
    
    def _get_latest_version(self, alpha: int, beta: int) -> Optional[Directive]:
        """Get the latest version (active or not) of a directive from DynamoDB.
        
        This queries DynamoDB directly, not the cache, to ensure we get
        the most recent version even if it's inactive.
        
        Args:
            alpha: Alpha tier
            beta: Beta number
            
        Returns:
            Latest version Directive, or None if not found
        """
        base_key = f"{alpha:02d}#{beta:02d}"
        response = self.table.query(
            KeyConditionExpression=(
                Key("PK").eq("DIR") & Key("SK").begins_with(base_key)
            )
        )
        
        if not response.get("Items"):
            return None
        
        versions = [
            Directive.from_dynamodb_item(item) 
            for item in response["Items"]
        ]
        versions.sort(key=lambda d: d.version, reverse=True)
        return versions[0]
    
    def add(
        self, 
        alpha: int, 
        label: str, 
        content: str, 
        created_by: str
    ) -> Directive:
        """Create new directive with version=1. Auto-assign beta via next_beta().
        
        Args:
            alpha: Alpha tier (0-5)
            label: Directive label (UPPER_SNAKE_CASE)
            content: Full directive text
            created_by: "operator", "agent", or "reflection"
            
        Returns:
            The created Directive with assigned beta
        """
        beta = self.next_beta(alpha)
        now = datetime.now(timezone.utc).isoformat()
        
        directive = Directive(
            alpha=alpha,
            beta=beta,
            version=1,  # New directives always start at version 1
            label=label,
            content=content,
            created_by=created_by,
            active=True,
            created_at=now,
            superseded_at=None,
        )
        
        self.table.put_item(Item=directive.to_dynamodb_item())
        self.load()  # Reload cache
        
        logger.info(
            f"[DirectiveStore] Added directive {alpha}-{beta} v1: {label}"
        )
        return directive
    
    def revise(
        self, 
        alpha: int, 
        beta: int, 
        content: str, 
        label: Optional[str] = None,
        created_by: str = "agent"
    ) -> Optional[Directive]:
        """Create a new version of an existing directive.
        
        This does NOT modify the existing directive. Instead:
        1. Marks old version as inactive (sets superseded_at)
        2. Creates new version with version = old_version + 1
        
        Args:
            alpha: Alpha tier
            beta: Beta number
            content: New content for the directive
            label: New label (optional, defaults to existing label)
            created_by: Who is making this revision
            
        Returns:
            New Directive version, or None if original not found
        """
        existing = self._get_latest_version(alpha, beta)
        if not existing:
            return None
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Mark old version as superseded
        self.table.update_item(
            Key={"PK": "DIR", "SK": existing.sort_key},
            UpdateExpression=(
                "SET active = :inactive, superseded_at = :superseded"
            ),
            ExpressionAttributeValues={
                ":inactive": False,
                ":superseded": now,
            },
        )
        
        # Create new version
        new_directive = Directive(
            alpha=alpha,
            beta=beta,
            version=existing.version + 1,
            label=label or existing.label,
            content=content,
            created_by=created_by,
            active=True,
            created_at=now,
            superseded_at=None,
        )
        
        self.table.put_item(Item=new_directive.to_dynamodb_item())
        self.load()  # Reload cache
        
        logger.info(
            f"[DirectiveStore] Revised directive {alpha}-{beta} "
            f"v{new_directive.version}"
        )
        return new_directive
    
    def deactivate(
        self, 
        alpha: int, 
        beta: int, 
        override: bool = False
    ) -> bool:
        """Mark the latest version of a directive as inactive.
        
        Block alpha 0-1 deactivation unless override=True.
        
        Args:
            alpha: Alpha tier
            beta: Beta number
            override: Allow deactivating alpha 0-1 (operator-only)
            
        Returns:
            True if deactivated, False if blocked or not found
        """
        # Block alpha 0-1 deactivation
        if alpha == 0 and beta == 1 and not override:
            logger.warning(
                "[DirectiveStore] Blocked deactivation of directive 0-1"
            )
            return False
        
        existing = self._get_latest_version(alpha, beta)
        if not existing:
            return False
        
        now = datetime.now(timezone.utc).isoformat()
        self.table.update_item(
            Key={"PK": "DIR", "SK": existing.sort_key},
            UpdateExpression=(
                "SET active = :inactive, superseded_at = :superseded"
            ),
            ExpressionAttributeValues={
                ":inactive": False,
                ":superseded": now,
            },
        )
        
        self.load()  # Reload cache
        logger.info(f"[DirectiveStore] Deactivated directive {alpha}-{beta}")
        return True
    
    def get(self, alpha: int, beta: int) -> Optional[Directive]:
        """Get the active directive for alpha/beta from cache.
        
        Args:
            alpha: Alpha tier
            beta: Beta number
            
        Returns:
            Directive if found in cache, None otherwise
        """
        for d in self._cache:
            if d.alpha == alpha and d.beta == beta:
                return d
        return None
    
    def get_all(self, alpha: Optional[int] = None) -> List[Directive]:
        """Get all active directives from cache, optionally filtered by alpha.
        
        Args:
            alpha: Optional alpha tier filter
            
        Returns:
            List of matching directives
        """
        if alpha is None:
            return list(self._cache)
        return [d for d in self._cache if d.alpha == alpha]
    
    def get_history(self, alpha: int, beta: int) -> List[Directive]:
        """Get all versions of a directive (for audit/history).
        
        Args:
            alpha: Alpha tier
            beta: Beta number
            
        Returns:
            List of all versions, sorted newest first
        """
        base_key = f"{alpha:02d}#{beta:02d}"
        response = self.table.query(
            KeyConditionExpression=(
                Key("PK").eq("DIR") & Key("SK").begins_with(base_key)
            )
        )
        
        versions = [
            Directive.from_dynamodb_item(item) 
            for item in response.get("Items", [])
        ]
        versions.sort(key=lambda d: d.version, reverse=True)
        return versions
