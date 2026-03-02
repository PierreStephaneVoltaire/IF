"""Growth tracking for reflection engine.

Implements Part6 of plan.md - Misconception Tracking & Growth Suggestions.

Tracks operator growth including:
- Knowledge gaps identified (misconceptions)
- Skills trending up (progressive questions)
- Abandoned interests (topics no longer discussed)
- Learning suggestions
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, List, Dict
from collections import defaultdict

if TYPE_CHECKING:
    from memory.user_facts import UserFactStore

logger = logging.getLogger(__name__)


class GrowthTracker:
    """Tracks operator growth and generates learning suggestions.
    
    Analyzes misconceptions, skill progression, and topic engagement
    to generate growth reports.
    
    Example:
        >>> tracker = GrowthTracker(store)
        >>> report = tracker.generate_growth_report(days_back=30)
        >>> print(report['summary'])
    """
    
    def __init__(self, store: "UserFactStore"):
        """Initialize growth tracker.
        
        Args:
            store: UserFactStore for reading facts
        """
        self.store = store
    
    def generate_growth_report(self, days_back: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive growth report.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            Dict containing growth report sections
        """
        report = {
            "period_days": days_back,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "knowledge_gaps": [],
            "skills_trending_up": [],
            "abandoned_interests": [],
            "suggestions": [],
            "summary": "",
        }
        
        try:
            # Analyze knowledge gaps (misconceptions)
            report["knowledge_gaps"] = self._analyze_knowledge_gaps(days_back)
            
            # Analyze skills trending up
            report["skills_trending_up"] = self._analyze_skill_progression(days_back)
            
            # Find abandoned interests
            report["abandoned_interests"] = self._find_abandoned_interests(days_back)
            
            # Generate suggestions
            report["suggestions"] = self._generate_suggestions(report)
            
            # Generate summary
            report["summary"] = self._generate_summary(report)
            
            logger.info(f"[GrowthTracker] Generated growth report for {days_back} days")
            
        except Exception as e:
            logger.error(f"[GrowthTracker] Report generation failed: {e}")
        
        return report
    
    def _analyze_knowledge_gaps(self, days_back: int) -> List[Dict[str, Any]]:
        """Analyze knowledge gaps from misconceptions.
        
        Groups misconceptions by domain and identifies trends.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            List of knowledge gap summaries by domain
        """
        from memory.user_facts import FactCategory
        
        gaps = []
        
        try:
            misconceptions = self.store.list_by_category(FactCategory.MISCONCEPTION)
            
            # Filter to time period
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            recent = []
            
            for misc in misconceptions:
                last_seen = misc.metadata.get("last_seen", misc.created_at)
                if last_seen:
                    try:
                        dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                        if dt > cutoff:
                            recent.append(misc)
                    except:
                        pass
            
            # Group by domain
            by_domain: Dict[str, List[Any]] = defaultdict(list)
            for misc in recent:
                domain = misc.metadata.get("domain", "general")
                by_domain[domain].append(misc)
            
            # Create gap summaries
            for domain, miscs in by_domain.items():
                total_occurrences = sum(
                    m.metadata.get("recurrence_count", 1) for m in miscs
                )
                
                # Check trend (recent vs older)
                recent_count = 0
                older_count = 0
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                
                for m in miscs:
                    last_seen = m.metadata.get("last_seen", "")
                    if last_seen:
                        try:
                            dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                            if dt > week_ago:
                                recent_count += 1
                            else:
                                older_count += 1
                        except:
                            pass
                
                if recent_count > older_count:
                    trend = "increasing"
                elif recent_count < older_count:
                    trend = "decreasing"
                else:
                    trend = "stable"
                
                # Get suggested resources
                resources = []
                for m in miscs:
                    resources.extend(m.metadata.get("suggested_resources", []))
                resources = list(set(resources))[:3]  # Unique, top3
                
                gaps.append({
                    "domain": domain,
                    "misconception_count": len(miscs),
                    "total_occurrences": total_occurrences,
                    "trend": trend,
                    "examples": [
                        {
                            "what_they_said": m.metadata.get("what_they_said", ""),
                            "what_is_correct": m.metadata.get("what_is_correct", ""),
                        }
                        for m in miscs[:3]
                    ],
                    "suggested_resources": resources,
                })
            
            # Sort by occurrence count
            gaps.sort(key=lambda x: x["total_occurrences"], reverse=True)
            
        except Exception as e:
            logger.warning(f"[GrowthTracker] Knowledge gap analysis failed: {e}")
        
        return gaps
    
    def _analyze_skill_progression(self, days_back: int) -> List[Dict[str, Any]]:
        """Analyze skills that are trending up.
        
        Identifies topics where questions are getting progressively
        more advanced, indicating learning.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            List of skills trending up
        """
        from memory.user_facts import FactCategory
        
        trending = []
        
        try:
            # Get skill facts and topic logs
            skills = self.store.list_by_category(FactCategory.SKILL)
            topics = self.store.list_by_category(FactCategory.TOPIC_LOG)
            
            # Combine for analysis
            all_facts = skills + topics
            
            # Group by topic/domain
            by_topic: Dict[str, List[Any]] = defaultdict(list)
            
            for fact in all_facts:
                # Extract topic from content
                content = fact.content.lower()
                
                # Simple topic extraction (could be enhanced with NLP)
                topic = self._extract_topic(content)
                if topic:
                    by_topic[topic].append(fact)
            
            # Analyze progression for each topic
            for topic, facts in by_topic.items():
                if len(facts) < 2:
                    continue
                
                # Sort by date
                sorted_facts = sorted(
                    [f for f in facts if f.created_at],
                    key=lambda f: f.created_at
                )
                
                if len(sorted_facts) < 2:
                    continue
                
                # Check if content is getting more advanced
                # (simplified: more recent content is longer/more complex)
                early_facts = sorted_facts[:len(sorted_facts)//2]
                late_facts = sorted_facts[len(sorted_facts)//2:]
                
                early_avg_len = sum(len(f.content) for f in early_facts) / len(early_facts)
                late_avg_len = sum(len(f.content) for f in late_facts) / len(late_facts)
                
                # If recent facts are longer/more detailed, skill is progressing
                if late_avg_len > early_avg_len * 1.2:
                    trending.append({
                        "topic": topic,
                        "engagement_count": len(facts),
                        "progression_indicator": "increasing_complexity",
                        "first_seen": sorted_facts[0].created_at,
                        "last_seen": sorted_facts[-1].created_at,
                    })
            
            # Sort by engagement count
            trending.sort(key=lambda x: x["engagement_count"], reverse=True)
            
        except Exception as e:
            logger.warning(f"[GrowthTracker] Skill progression analysis failed: {e}")
        
        return trending
    
    def _find_abandoned_interests(self, days_back: int) -> List[Dict[str, Any]]:
        """Find topics that were discussed but abandoned.
        
        Identifies interests that were active but haven't been
        mentioned recently.
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            List of abandoned interests
        """
        from memory.user_facts import FactCategory
        
        abandoned = []
        
        try:
            # Get all topic-related facts
            topics = self.store.list_by_category(FactCategory.TOPIC_LOG)
            interests = self.store.list_by_category(FactCategory.INTEREST_AREA)
            
            all_facts = topics + interests
            
            # Define "abandoned" as not mentioned in last30 days
            # but was active in the 30 days before that
            now = datetime.now(timezone.utc)
            recent_cutoff = now - timedelta(days=30)
            older_cutoff = now - timedelta(days=60)
            
            # Group by topic
            by_topic: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"recent": 0, "older": 0, "last_seen": None})
            
            for fact in all_facts:
                if not fact.created_at:
                    continue
                    
                try:
                    dt = datetime.fromisoformat(fact.created_at.replace("Z", "+00:00"))
                    topic = self._extract_topic(fact.content.lower())
                    
                    if topic:
                        if dt > recent_cutoff:
                            by_topic[topic]["recent"] += 1
                        elif dt > older_cutoff:
                            by_topic[topic]["older"] += 1
                        
                        if by_topic[topic]["last_seen"] is None or dt > by_topic[topic]["last_seen"]:
                            by_topic[topic]["last_seen"] = dt
                            
                except:
                    pass
            
            # Find topics with older activity but no recent activity
            for topic, counts in by_topic.items():
                if counts["older"] >= 2 and counts["recent"] == 0:
                    abandoned.append({
                        "topic": topic,
                        "previous_engagement": counts["older"],
                        "last_seen": counts["last_seen"].isoformat() if counts["last_seen"] else None,
                        "abandoned_days": (now - counts["last_seen"]).days if counts["last_seen"] else None,
                    })
            
            # Sort by previous engagement
            abandoned.sort(key=lambda x: x["previous_engagement"], reverse=True)
            
        except Exception as e:
            logger.warning(f"[GrowthTracker] Abandoned interests analysis failed: {e}")
        
        return abandoned
    
    def _extract_topic(self, content: str) -> str | None:
        """Extract a topic from content.
        
        Simple keyword-based extraction. Could be enhanced with NLP.
        
        Args:
            content: Text content to analyze
            
        Returns:
            Extracted topic or None
        """
        # Technology keywords to look for
        tech_keywords = [
            "python", "javascript", "typescript", "rust", "golang", "go",
            "aws", "azure", "gcp", "kubernetes", "docker", "terraform",
            "react", "vue", "angular", "node", "django", "flask",
            "sql", "postgres", "mysql", "mongodb", "redis",
            "graphql", "rest", "api", "microservices",
            "machine learning", "ai", "llm", "gpt", "neural",
            "networking", "security", "devops", "ci/cd",
            "testing", "tdd", "agile", "scrum",
        ]
        
        content_lower = content.lower()
        
        for keyword in tech_keywords:
            if keyword in content_lower:
                return keyword
        
        return None
    
    def _generate_suggestions(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate learning suggestions based on analysis.
        
        Args:
            report: Current report dict
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        # Suggestions based on knowledge gaps
        for gap in report.get("knowledge_gaps", []):
            if gap["trend"] == "increasing":
                suggestions.append({
                    "type": "learning",
                    "priority": "high",
                    "domain": gap["domain"],
                    "suggestion": f"Consider focused learning on {gap['domain']} - "
                                 f"{gap['misconception_count']} misconceptions detected",
                    "resources": gap.get("suggested_resources", []),
                })
        
        # Suggestions based on trending skills
        for skill in report.get("skills_trending_up", []):
            suggestions.append({
                "type": "advancement",
                "priority": "medium",
                "domain": skill["topic"],
                "suggestion": f"Ready for advanced {skill['topic']} topics - "
                             "engagement is progressing well",
                "resources": [],
            })
        
        # Suggestions based on abandoned interests
        for interest in report.get("abandoned_interests", []):
            suggestions.append({
                "type": "re-engagement",
                "priority": "low",
                "domain": interest["topic"],
                "suggestion": f"Consider revisiting {interest['topic']} - "
                             f"no activity for {interest.get('abandoned_days', '?')} days",
                "resources": [],
            })
        
        return suggestions
    
    def _generate_summary(self, report: Dict[str, Any]) -> str:
        """Generate a human-readable summary.
        
        Args:
            report: Full report dict
            
        Returns:
            Summary string
        """
        lines = [
            f"## Operator Growth Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "",
            f"Analysis period: {report['period_days']} days",
            "",
        ]
        
        # Knowledge gaps
        gaps = report.get("knowledge_gaps", [])
        if gaps:
            lines.append("### Knowledge Gaps Identified")
            for gap in gaps[:3]:
                trend_emoji = "📈" if gap["trend"] == "increasing" else "📉" if gap["trend"] == "decreasing" else "➡️"
                lines.append(f"- **{gap['domain']}** — {gap['misconception_count']} misconceptions {trend_emoji}")
                if gap.get("suggested_resources"):
                    lines.append(f"  - Suggested: {', '.join(gap['suggested_resources'][:2])}")
            lines.append("")
        
        # Skills trending up
        trending = report.get("skills_trending_up", [])
        if trending:
            lines.append("### Skills Trending Up")
            for skill in trending[:3]:
                lines.append(f"- **{skill['topic']}** ({skill['engagement_count']} engagements)")
            lines.append("")
        
        # Abandoned interests
        abandoned = report.get("abandoned_interests", [])
        if abandoned:
            lines.append("### Abandoned Interests")
            for interest in abandoned[:3]:
                lines.append(f"- **{interest['topic']}** (last: {interest.get('abandoned_days', '?')} days ago)")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_misconception_report(self) -> str:
        """Generate a focused misconception report.
        
        Returns:
            Markdown-formatted misconception report
        """
        from memory.user_facts import FactCategory
        
        lines = ["# Misconception Report", ""]
        
        try:
            misconceptions = self.store.list_by_category(FactCategory.MISCONCEPTION)
            
            # Group by domain
            by_domain: Dict[str, List[Any]] = defaultdict(list)
            for misc in misconceptions:
                domain = misc.metadata.get("domain", "general")
                by_domain[domain].append(misc)
            
            for domain, miscs in sorted(by_domain.items()):
                lines.append(f"## {domain.title()}")
                lines.append("")
                
                for misc in miscs:
                    lines.append(f"### {misc.metadata.get('topic', 'Unknown')}")
                    lines.append(f"- **What they said:** {misc.metadata.get('what_they_said', 'N/A')}")
                    lines.append(f"- **Correct:** {misc.metadata.get('what_is_correct', 'N/A')}")
                    lines.append(f"- **Severity:** {misc.metadata.get('severity', 'minor')}")
                    lines.append(f"- **Recurrence:** {misc.metadata.get('recurrence_count', 1)}")
                    
                    resources = misc.metadata.get("suggested_resources", [])
                    if resources:
                        lines.append(f"- **Resources:** {', '.join(resources)}")
                    lines.append("")
                    
        except Exception as e:
            lines.append(f"Error generating report: {e}")
        
        return "\n".join(lines)
