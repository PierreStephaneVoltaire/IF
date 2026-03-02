"""Reflection engine for metacognitive analysis.

The reflection engine runs periodically and post-session to:
- Detect patterns in operator behavior
- Form agent opinions on user-stated positions
- Analyze capability gaps for tool suggestions
- Track operator growth and learning

Based on plan.md Parts4,5,6:
- Part4: Reflection Engine with periodic/post-session triggers
- Part5: Capability Gap → Tool Pipeline
- Part6: Misconception Tracking & Growth Suggestions
"""
from .engine import ReflectionEngine, get_reflection_engine
from .pattern_detector import PatternDetector
from .opinion_formation import OpinionFormer
from .meta_analysis import MetaAnalyzer, StoreHealthMetrics
from .growth_tracker import GrowthTracker

__all__ = [
    "ReflectionEngine",
    "get_reflection_engine",
    "PatternDetector",
    "OpinionFormer",
    "MetaAnalyzer",
    "StoreHealthMetrics",
    "GrowthTracker",
]
