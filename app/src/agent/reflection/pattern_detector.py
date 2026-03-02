"""Pattern detection for reflection engine.

Implements Part4 of plan.md - Pattern Detection.

Detects patterns in operator behavior including:
- Temporal patterns (same topic at regular intervals)
- Topical patterns (recurring themes)
- Behavioral patterns (skill gaps, repeated questions)
- Capability gap frequency spikes
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, List, Dict
from dataclasses import dataclass, field
import uuid

if TYPE_CHECKING:
    from memory.user_facts import UserFactStore

logger = logging.getLogger(__name__)


@dataclass
class Pattern:
    """Detected pattern in operator behavior."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""                # "Operator asks about AWS networking every Monday"
    pattern_type: str = ""               # "temporal" | "topical" | "behavioral" | "skill_gap"
    evidence: list[str] = field(default_factory=list)  # Fact IDs that support this pattern
    frequency: int = 1                   # How many times observed
    confidence: float = 0.5              # How confident the pattern is real
    trend_direction: str = "stable"      # "increasing" | "stable" | "decreasing"
    last_seen: str = ""
    actionable: bool = False             # Does this suggest something we should do?
    suggested_action: str | None = None  # "Proactively surface VPC docs on Mondays"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "pattern_type": self.pattern_type,
            "evidence": self.evidence,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "trend_direction": self.trend_direction,
            "last_seen": self.last_seen,
            "actionable": self.actionable,
            "suggested_action": self.suggested_action,
        }


class PatternDetector:
    """Detects patterns in operator behavior.
    
    Analyzes stored facts to identify:
    - Temporal patterns (regular intervals)
    - Topical patterns (recurring themes)
    - Behavioral patterns (skill gaps, repeated questions)
    - Capability gap frequency spikes
    
    Example:
        >>> detector = PatternDetector(store)
        >>> patterns = await detector.detect_patterns()
        >>> for p in patterns:
        ...     print(f"{p.pattern_type}: {p.description}")
    """
    
    def __init__(self, store: "UserFactStore"):
        """Initialize pattern detector.
        
        Args:
            store: UserFactStore for reading facts
        """
        self.store = store
    
    async def detect_patterns(self) -> List[Pattern]:
        """Run all pattern detection algorithms.
        
        Returns:
            List of detected or updated patterns
        """
        patterns = []
        
        try:
            # Detect topical patterns
            topical = await self._detect_topical_patterns()
            patterns.extend(topical)
            
            # Detect temporal patterns
            temporal = await self._detect_temporal_patterns()
            patterns.extend(temporal)
            
            # Detect skill gap patterns
            skill_gaps = await self._detect_skill_gap_patterns()
            patterns.extend(skill_gaps)
            
            # Detect capability gap spikes
            gap_spikes = await self._detect_capability_gap_spikes()
            patterns.extend(gap_spikes)
            
            # Store new patterns and update existing ones
            await self._store_patterns(patterns)
            
            logger.info(f"[PatternDetector] Detected {len(patterns)} patterns")
            
        except Exception as e:
            logger.error(f"[PatternDetector] Detection failed: {e}")
        
        return patterns
    
    async def _detect_topical_patterns(self) -> List[Pattern]:
        """Detect recurring topical themes.
        
        Clusters facts by semantic similarity and identifies
        topics that appear frequently.
        
        Returns:
            List of topical patterns
        """
        from memory.user_facts import FactCategory
        
        patterns = []
        
        try:
            # Get recent facts from the last30 days
            recent_facts = self.store.get_recent_facts(days=30, limit=100)
            
            # Group by category for initial clustering
            category_counts: Dict[str, int] = {}
            for fact in recent_facts:
                cat = fact.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            # Look for high-frequency categories
            for cat, count in category_counts.items():
                if count >= 5:  # Threshold for "pattern"
                    # Check if we already have this pattern
                    existing = self._find_existing_pattern(
                        pattern_type="topical",
                        description_fragment=cat
                    )
                    
                    if existing:
                        # Update existing pattern
                        existing.frequency += 1
                        existing.confidence = min(existing.confidence + 0.05, 0.95)
                        patterns.append(existing)
                    else:
                        # Create new pattern
                        pattern = Pattern(
                            description=f"Operator frequently discusses {cat} topics ({count} times in 30 days)",
                            pattern_type="topical",
                            frequency=count,
                            confidence=min(0.5 + count * 0.05, 0.9),
                            trend_direction=self._compute_trend(cat, recent_facts),
                            last_seen=datetime.now(timezone.utc).isoformat(),
                            actionable=True,
                            suggested_action=f"Consider proactively surfacing {cat} resources",
                        )
                        patterns.append(pattern)
                        
        except Exception as e:
            logger.warning(f"[PatternDetector] Topical detection failed: {e}")
        
        return patterns
    
    async def _detect_temporal_patterns(self) -> List[Pattern]:
        """Detect time-based patterns.
        
        Identifies topics that appear at regular intervals
        (e.g., "every Monday", "end of month").
        
        Returns:
            List of temporal patterns
        """
        from memory.user_facts import FactCategory
        
        patterns = []
        
        try:
            # Get facts with timestamps
            recent_facts = self.store.get_recent_facts(days=60, limit=200)
            
            # Group by day of week
            dow_counts: Dict[int, List[Any]] = {}
            for fact in recent_facts:
                if fact.created_at:
                    try:
                        dt = datetime.fromisoformat(fact.created_at.replace("Z", "+00:00"))
                        dow = dt.weekday()
                        if dow not in dow_counts:
                            dow_counts[dow] = []
                        dow_counts[dow].append(fact)
                    except:
                        pass
            
            # Check for day-skewed patterns
            dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            
            for dow, facts in dow_counts.items():
                if len(facts) >= 5:
                    # Check if this day has significantly more activity
                    avg_per_day = len(recent_facts) / 7
                    if len(facts) > avg_per_day * 1.5:
                        # Find common categories on this day
                        cat_counts: Dict[str, int] = {}
                        for f in facts:
                            cat = f.category.value
                            cat_counts[cat] = cat_counts.get(cat, 0) + 1
                        
                        top_cat = max(cat_counts.items(), key=lambda x: x[1])[0] if cat_counts else "various"
                        
                        pattern = Pattern(
                            description=f"Operator more active on {dow_names[dow]}s, especially about {top_cat}",
                            pattern_type="temporal",
                            frequency=len(facts),
                            confidence=0.6,
                            trend_direction="stable",
                            last_seen=datetime.now(timezone.utc).isoformat(),
                            actionable=True,
                            suggested_action=f"Consider proactive engagement on {dow_names[dow]}s",
                        )
                        patterns.append(pattern)
                        
        except Exception as e:
            logger.warning(f"[PatternDetector] Temporal detection failed: {e}")
        
        return patterns
    
    async def _detect_skill_gap_patterns(self) -> List[Pattern]:
        """Detect patterns indicating skill gaps.
        
        Identifies domains where the operator asks
        repeated basic questions, suggesting learning opportunities.
        
        Returns:
            List of skill gap patterns
        """
        from memory.user_facts import FactCategory
        
        patterns = []
        
        try:
            # Get misconceptions
            misconceptions = self.store.list_by_category(FactCategory.MISCONCEPTION)
            
            # Group by domain
            domain_counts: Dict[str, List[Any]] = {}
            for misc in misconceptions:
                domain = misc.metadata.get("domain", "unknown")
                if domain not in domain_counts:
                    domain_counts[domain] = []
                domain_counts[domain].append(misc)
            
            # Find domains with repeated misconceptions
            for domain, miscs in domain_counts.items():
                if len(miscs) >= 2:
                    total_recurrence = sum(
                        m.metadata.get("recurrence_count", 1) for m in miscs
                    )
                    
                    pattern = Pattern(
                        description=f"Operator has knowledge gaps in {domain} ({len(miscs)} misconceptions, {total_recurrence} total occurrences)",
                        pattern_type="skill_gap",
                        frequency=total_recurrence,
                        confidence=0.8,
                        trend_direction=self._compute_misconception_trend(miscs),
                        last_seen=datetime.now(timezone.utc).isoformat(),
                        actionable=True,
                        suggested_action=f"Suggest learning resources for {domain}",
                    )
                    patterns.append(pattern)
                    
        except Exception as e:
            logger.warning(f"[PatternDetector] Skill gap detection failed: {e}")
        
        return patterns
    
    async def _detect_capability_gap_spikes(self) -> List[Pattern]:
        """Detect spikes in capability gap triggers.
        
        Identifies capability gaps that are being triggered
        more frequently than usual.
        
        Returns:
            List of capability gap spike patterns
        """
        from memory.user_facts import FactCategory
        
        patterns = []
        
        try:
            # Get capability gaps
            gaps = self.store.list_by_category(FactCategory.CAPABILITY_GAP)
            
            for gap in gaps:
                trigger_count = gap.metadata.get("trigger_count", 0)
                
                if trigger_count >= 3:
                    # This is a recurring gap
                    trend = "stable"
                    contexts = gap.metadata.get("trigger_contexts", [])
                    
                    # Check recent vs older triggers
                    if len(contexts) >= 3:
                        # If last3 contexts are recent, trend is increasing
                        trend = "increasing"
                    
                    pattern = Pattern(
                        description=f"Recurring capability gap: {gap.content} ({trigger_count} times)",
                        pattern_type="behavioral",
                        frequency=trigger_count,
                        confidence=0.7,
                        trend_direction=trend,
                        last_seen=gap.metadata.get("last_seen", ""),
                        actionable=True,
                        suggested_action=f"Consider tool development: {gap.content}",
                    )
                    patterns.append(pattern)
                    
        except Exception as e:
            logger.warning(f"[PatternDetector] Capability gap spike detection failed: {e}")
        
        return patterns
    
    def _find_existing_pattern(
        self,
        pattern_type: str,
        description_fragment: str,
    ) -> Pattern | None:
        """Find an existing pattern matching criteria.
        
        Args:
            pattern_type: Type of pattern to find
            description_fragment: Text that should be in description
            
        Returns:
            Existing Pattern or None
        """
        from memory.user_facts import FactCategory
        
        try:
            # Search for existing patterns
            existing = self.store.list_by_category(FactCategory.SESSION_REFLECTION)
            
            for fact in existing:
                metadata = fact.metadata or {}
                if metadata.get("pattern_type") == pattern_type:
                    if description_fragment.lower() in fact.content.lower():
                        # Reconstruct pattern from metadata
                        return Pattern(
                            id=fact.id,
                            description=fact.content,
                            pattern_type=metadata.get("pattern_type", pattern_type),
                            frequency=metadata.get("frequency", 1),
                            confidence=metadata.get("confidence", 0.5),
                            trend_direction=metadata.get("trend_direction", "stable"),
                            last_seen=metadata.get("last_seen", ""),
                            actionable=metadata.get("actionable", False),
                            suggested_action=metadata.get("suggested_action"),
                        )
        except:
            pass
        
        return None
    
    def _compute_trend(self, category: str, facts: List[Any]) -> str:
        """Compute trend direction for a category.
        
        Compares recent activity (last7 days) to previous period.
        
        Args:
            category: Category to analyze
            facts: List of facts to analyze
            
        Returns:
            "increasing", "stable", or "decreasing"
        """
        try:
            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)
            two_weeks_ago = now - timedelta(days=14)
            
            recent_count = 0
            previous_count = 0
            
            for fact in facts:
                if fact.category.value != category:
                    continue
                    
                if not fact.created_at:
                    continue
                    
                try:
                    dt = datetime.fromisoformat(fact.created_at.replace("Z", "+00:00"))
                    if dt > week_ago:
                        recent_count += 1
                    elif dt > two_weeks_ago:
                        previous_count += 1
                except:
                    pass
            
            if recent_count > previous_count * 1.3:
                return "increasing"
            elif recent_count < previous_count * 0.7:
                return "decreasing"
            return "stable"
            
        except:
            return "stable"
    
    def _compute_misconception_trend(self, misconceptions: List[Any]) -> str:
        """Compute trend for misconceptions in a domain.
        
        Args:
            misconceptions: List of misconception facts
            
        Returns:
            "increasing", "stable", or "decreasing"
        """
        try:
            now = datetime.now(timezone.utc)
            week_ago = now - timedelta(days=7)
            
            recent = 0
            for misc in misconceptions:
                last_seen = misc.metadata.get("last_seen", "")
                if last_seen:
                    try:
                        dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        if dt > week_ago:
                            recent += 1
                    except:
                        pass
            
            # If recent misconceptions, trend is increasing (bad)
            # If no recent, trend is decreasing (good - learning)
            if recent > 0:
                return "increasing"
            return "decreasing"
            
        except:
            return "stable"
    
    async def _store_patterns(self, patterns: List[Pattern]) -> None:
        """Store detected patterns in the fact store.
        
        Args:
            patterns: Patterns to store
        """
        from memory.user_facts import FactCategory, FactSource, UserFact
        
        for pattern in patterns:
            try:
                if pattern.id:
                    # Update existing
                    # Find the fact and update metadata
                    pass
                else:
                    # Create new
                    fact = UserFact(
                        content=f"Pattern: {pattern.description}",
                        category=FactCategory.SESSION_REFLECTION,
                        source=FactSource.MODEL_OBSERVED,
                        confidence=pattern.confidence,
                        metadata={
                            "pattern_type": pattern.pattern_type,
                            "pattern_data": pattern.to_dict(),
                            "frequency": pattern.frequency,
                            "confidence": pattern.confidence,
                            "trend_direction": pattern.trend_direction,
                            "actionable": pattern.actionable,
                            "suggested_action": pattern.suggested_action,
                        }
                    )
                    self.store.add(fact)
                    
            except Exception as e:
                logger.warning(f"[PatternDetector] Failed to store pattern: {e}")
