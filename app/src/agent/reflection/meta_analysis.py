"""Meta-analysis for reflection engine.

Implements Part4 of plan.md - Meta-Analysis.

Analyzes the fact store itself to identify:
- Category distribution and health
- Stale fact detection
- Category fit analysis
- Store health metrics
- Category evolution suggestions
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, List, Dict
from dataclasses import dataclass, field
from collections import defaultdict

from config import REFLECTION_CONTEXT_ID

if TYPE_CHECKING:
    from memory.user_facts import UserFactStore

logger = logging.getLogger(__name__)


@dataclass
class StoreHealthMetrics:
    """Health metrics for the fact store."""
    total_facts: int = 0
    active_facts: int = 0
    superseded_facts: int = 0
    category_distribution: Dict[str, int] = field(default_factory=dict)
    stalest_category: str = ""
    fastest_growing: str = ""
    most_superseded: str = ""
    uncategorized_pressure: List[str] = field(default_factory=list)
    suggested_new_categories: List[Dict[str, Any]] = field(default_factory=list)
    capability_gap_summary: Dict[str, Any] = field(default_factory=dict)
    reflection_count: int = 0
    avg_satisfaction_trend: str = "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_facts": self.total_facts,
            "active_facts": self.active_facts,
            "superseded_facts": self.superseded_facts,
            "category_distribution": self.category_distribution,
            "stalest_category": self.stalest_category,
            "fastest_growing": self.fastest_growing,
            "most_superseded": self.most_superseded,
            "uncategorized_pressure": self.uncategorized_pressure,
            "suggested_new_categories": self.suggested_new_categories,
            "capability_gap_summary": self.capability_gap_summary,
            "reflection_count": self.reflection_count,
            "avg_satisfaction_trend": self.avg_satisfaction_trend,
        }


class MetaAnalyzer:
    """Analyzes fact store health and suggests improvements.
    
    Provides meta-analysis of the knowledge store including:
    - Category distribution and growth
    - Stale fact detection
    - Category fit analysis
    - New category suggestions
    
    Example:
        >>> analyzer = MetaAnalyzer(store)
        >>> metrics = analyzer.analyze()
        >>> print(f"Total facts: {metrics.total_facts}")
        >>> print(f"Fastest growing: {metrics.fastest_growing}")
    """
    
    def __init__(self, store: "UserFactStore"):
        """Initialize meta analyzer.
        
        Args:
            store: UserFactStore to analyze
        """
        self.store = store
    
    def analyze(self) -> Dict[str, Any]:
        """Run full meta-analysis of the fact store.
        
        Returns:
            Dict containing StoreHealthMetrics and analysis results
        """
        metrics = StoreHealthMetrics()
        
        try:
            # Get all facts for analysis
            all_facts = self.store.get_all_facts(REFLECTION_CONTEXT_ID)
            
            # Basic counts
            metrics.total_facts = len(all_facts)
            metrics.active_facts = sum(1 for f in all_facts if f.active)
            metrics.superseded_facts = metrics.total_facts - metrics.active_facts
            
            # Category distribution
            metrics.category_distribution = self._compute_category_distribution(all_facts)
            
            # Stalest category (oldest average fact age)
            metrics.stalest_category = self._find_stalest_category(all_facts)
            
            # Fastest growing category
            metrics.fastest_growing = self._find_fastest_growing(all_facts)
            
            # Most superseded category
            metrics.most_superseded = self._find_most_superseded(all_facts)
            
            # Uncategorized pressure (facts that were hard to categorize)
            metrics.uncategorized_pressure = self._find_uncategorized_pressure(all_facts)
            
            # Suggested new categories
            metrics.suggested_new_categories = self._suggest_categories(all_facts)
            
            # Capability gap summary
            metrics.capability_gap_summary = self._summarize_capability_gaps(all_facts)
            
            # Reflection count
            metrics.reflection_count = metrics.category_distribution.get("session_reflection", 0)
            
            # Satisfaction trend
            metrics.avg_satisfaction_trend = self._compute_satisfaction_trend(all_facts)
            
            # Store metrics as meta_observation
            self._store_metrics(metrics)
            
            logger.info(f"[MetaAnalyzer] Analysis complete: {metrics.total_facts} facts, "
                       f"{len(metrics.category_distribution)} categories")
            
        except Exception as e:
            logger.error(f"[MetaAnalyzer] Analysis failed: {e}")
        
        return metrics.to_dict()
    
    def _compute_category_distribution(self, facts: List[Any]) -> Dict[str, int]:
        """Compute distribution of facts across categories.
        
        Args:
            facts: List of all facts
            
        Returns:
            Dict mapping category name to count
        """
        distribution = defaultdict(int)
        for fact in facts:
            cat = fact.category.value if hasattr(fact, 'category') else 'unknown'
            distribution[cat] += 1
        return dict(distribution)
    
    def _find_stalest_category(self, facts: List[Any]) -> str:
        """Find category with oldest average fact age.
        
        Args:
            facts: List of all facts
            
        Returns:
            Category name with oldest average age
        """
        now = datetime.now(timezone.utc)
        category_ages: Dict[str, List[float]] = defaultdict(list)
        
        for fact in facts:
            if not fact.created_at:
                continue
            try:
                created = datetime.fromisoformat(fact.created_at.replace("Z", "+00:00"))
                age_days = (now - created).days
                cat = fact.category.value if hasattr(fact, 'category') else 'unknown'
                category_ages[cat].append(age_days)
            except:
                pass
        
        if not category_ages:
            return ""
        
        # Find category with highest average age
        avg_ages = {
            cat: sum(ages) / len(ages)
            for cat, ages in category_ages.items()
        }
        
        return max(avg_ages.items(), key=lambda x: x[1])[0] if avg_ages else ""
    
    def _find_fastest_growing(self, facts: List[Any]) -> str:
        """Find category with most new facts in last30 days.
        
        Args:
            facts: List of all facts
            
        Returns:
            Category name with most recent growth
        """
        now = datetime.now(timezone.utc)
        month_ago = now - timedelta(days=30)
        
        recent_counts: Dict[str, int] = defaultdict(int)
        
        for fact in facts:
            if not fact.created_at:
                continue
            try:
                created = datetime.fromisoformat(fact.created_at.replace("Z", "+00:00"))
                if created > month_ago:
                    cat = fact.category.value if hasattr(fact, 'category') else 'unknown'
                    recent_counts[cat] += 1
            except:
                pass
        
        return max(recent_counts.items(), key=lambda x: x[1])[0] if recent_counts else ""
    
    def _find_most_superseded(self, facts: List[Any]) -> str:
        """Find category with most superseded facts.
        
        Args:
            facts: List of all facts
            
        Returns:
            Category name with most superseded facts
        """
        superseded_counts: Dict[str, int] = defaultdict(int)
        
        for fact in facts:
            if not fact.active and fact.superseded_by:
                cat = fact.category.value if hasattr(fact, 'category') else 'unknown'
                superseded_counts[cat] += 1
        
        return max(superseded_counts.items(), key=lambda x: x[1])[0] if superseded_counts else ""
    
    def _find_uncategorized_pressure(self, facts: List[Any]) -> List[str]:
        """Find facts that were hard to categorize.
        
        Looks for meta_observations about poor category fit.
        
        Args:
            facts: List of all facts
            
        Returns:
            List of fact IDs or descriptions that were hard to categorize
        """
        from memory.user_facts import FactCategory
        
        pressure = []
        
        for fact in facts:
            if fact.category == FactCategory.SESSION_REFLECTION:
                metadata = fact.metadata or {}
                # Check if this is a category fit observation
                if "fit_score" in metadata or "categorization_tension" in metadata:
                    content_preview = fact.content[:80] if fact.content else ""
                    pressure.append(content_preview)
        
        return pressure[:10]  # Limit to top10
    
    def _suggest_categories(self, facts: List[Any]) -> List[Dict[str, Any]]:
        """Suggest new categories based on clustering.
        
        Analyzes uncategorized pressure and suggests new categories
        when a cluster of similar facts is detected.
        
        Args:
            facts: List of all facts
            
        Returns:
            List of category suggestions with reasons
        """
        suggestions = []
        
        # This is a simplified implementation
        # A full implementation would use semantic clustering
        
        # Check for patterns in uncategorized pressure
        pressure = self._find_uncategorized_pressure(facts)
        
        if len(pressure) >= 3:
            # There's enough pressure to suggest a new category
            suggestions.append({
                "name": "emerging_topic",
                "reason": f"{len(pressure)} facts were hard to categorize",
                "example_facts": pressure[:3],
                "confidence": 0.6,
            })
        
        return suggestions
    
    def _summarize_capability_gaps(self, facts: List[Any]) -> Dict[str, Any]:
        """Summarize capability gaps for the report.
        
        Args:
            facts: List of all facts
            
        Returns:
            Summary dict with total, open, resolved, top priority
        """
        from memory.user_facts import FactCategory
        
        gaps = [f for f in facts if f.category == FactCategory.CAPABILITY_GAP]
        
        total = len(gaps)
        open_gaps = sum(1 for g in gaps if g.metadata.get("status") == "open")
        resolved = sum(1 for g in gaps if g.metadata.get("status") == "resolved")
        
        # Find top priority gap
        top_priority = None
        top_score = 0
        
        for gap in gaps:
            score = gap.metadata.get("priority_score", 0)
            if score > top_score:
                top_score = score
                top_priority = gap.content[:100] if gap.content else ""
        
        return {
            "total": total,
            "open": open_gaps,
            "resolved": resolved,
            "workaround_exists": total - open_gaps - resolved,
            "top_priority": top_priority,
            "top_priority_score": top_score,
        }
    
    def _compute_satisfaction_trend(self, facts: List[Any]) -> str:
        """Compute operator satisfaction trend from session reflections.
        
        Args:
            facts: List of all facts
            
        Returns:
            "improving", "stable", or "declining"
        """
        from memory.user_facts import FactCategory
        
        reflections = [f for f in facts if f.category == FactCategory.SESSION_REFLECTION]
        
        if len(reflections) < 2:
            return "stable"
        
        # Sort by created_at
        sorted_refs = sorted(
            [r for r in reflections if r.created_at],
            key=lambda r: r.created_at
        )
        
        if len(sorted_refs) < 2:
            return "stable"
        
        # Compare recent vs older satisfaction
        satisfaction_map = {"positive": 1, "neutral": 0, "negative": -1}
        
        mid = len(sorted_refs) // 2
        older = sorted_refs[:mid]
        recent = sorted_refs[mid:]
        
        def avg_satisfaction(refs):
            scores = []
            for r in refs:
                sat = r.metadata.get("operator_satisfaction", "neutral")
                scores.append(satisfaction_map.get(sat, 0))
            return sum(scores) / len(scores) if scores else 0
        
        older_avg = avg_satisfaction(older)
        recent_avg = avg_satisfaction(recent)
        
        if recent_avg > older_avg + 0.2:
            return "improving"
        elif recent_avg < older_avg - 0.2:
            return "declining"
        return "stable"
    
    def _store_metrics(self, metrics: StoreHealthMetrics) -> None:
        """Store metrics as a meta_observation.
        
        Args:
            metrics: Computed health metrics
        """
        from memory.user_facts import FactCategory, FactSource, UserFact
        
        try:
            self.store.add(
                context_id=REFLECTION_CONTEXT_ID,
                content=f"Store health: {metrics.total_facts} facts, "
                       f"{len(metrics.category_distribution)} categories, "
                       f"satisfaction {metrics.avg_satisfaction_trend}",
                category=FactCategory.SESSION_REFLECTION,
                source=FactSource.MODEL_OBSERVED,
                confidence=0.9,
                metadata={
                    "meta_type": "store_health_metrics",
                    "metrics": metrics.to_dict(),
                }
            )
            
        except Exception as e:
            logger.warning(f"[MetaAnalyzer] Failed to store metrics: {e}")
    
    def get_category_report(self) -> str:
        """Generate a human-readable category report.
        
        Returns:
            Markdown-formatted report string
        """
        metrics = self.analyze()
        
        lines = [
            "# Fact Store Health Report",
            "",
            f"**Total Facts:** {metrics['total_facts']}",
            f"**Active:** {metrics['active_facts']}",
            f"**Superseded:** {metrics['superseded_facts']}",
            "",
            "## Category Distribution",
            "",
        ]
        
        for cat, count in sorted(metrics['category_distribution'].items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}:** {count}")
        
        lines.extend([
            "",
            "## Trends",
            "",
            f"- **Fastest Growing:** {metrics['fastest_growing'] or 'N/A'}",
            f"- **Stalest Category:** {metrics['stalest_category'] or 'N/A'}",
            f"- **Most Churn:** {metrics['most_superseded'] or 'N/A'}",
            f"- **Satisfaction Trend:** {metrics['avg_satisfaction_trend']}",
            "",
            "## Capability Gaps",
            "",
            f"- **Total:** {metrics['capability_gap_summary'].get('total', 0)}",
            f"- **Open:** {metrics['capability_gap_summary'].get('open', 0)}",
            f"- **Top Priority:** {metrics['capability_gap_summary'].get('top_priority', 'N/A')}",
        ])
        
        if metrics['suggested_new_categories']:
            lines.extend([
                "",
                "## Suggested Categories",
                "",
            ])
            for suggestion in metrics['suggested_new_categories']:
                lines.append(f"- **{suggestion['name']}**: {suggestion['reason']}")
        
        return "\n".join(lines)
