"""Command handlers for reflection engine and memory system.

Implements Part8 of plan.md - New Commands:

Commands:
- /reflect - Trigger manual reflection cycle, output summary
- /gaps - List capability gaps ranked by priority
- /patterns - Show detected patterns
- /opinions - Show opinion pairs (agent vs operator positions)
- /growth - Show operator growth report
- /meta - Show store health metrics and category suggestions
- /tools - Show tool suggestions derived from capability gaps
"""
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from memory.user_facts import UserFactStore
    from agent.reflection.engine import ReflectionEngine

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handles slash commands for the reflection and memory system.

    Example:
        >>> handler = CommandHandler(store, reflection_engine, context_id="openwebui_chat123")
        >>> result = handler.handle("/gaps")
        >>> print(result)
    """

    def __init__(
        self,
        store: "UserFactStore",
        reflection_engine: Optional["ReflectionEngine"] = None,
        context_id: str = "",
    ):
        """Initialize command handler.

        Args:
            store: UserFactStore for reading facts
            reflection_engine: Optional ReflectionEngine for /reflect command
            context_id: The context ID for LanceDB storage
        """
        self.store = store
        self.reflection_engine = reflection_engine
        self.context_id = context_id
        
        # Register command handlers
        self._handlers = {
            "/reflect": self._handle_reflect,
            "/gaps": self._handle_gaps,
            "/patterns": self._handle_patterns,
            "/opinions": self._handle_opinions,
            "/growth": self._handle_growth,
            "/meta": self._handle_meta,
            "/tools": self._handle_tools,
        }
    
    def handle(self, command: str, args: str = "") -> str:
        """Handle a slash command.
        
        Args:
            command: The command string (e.g., "/gaps")
            args: Optional arguments after the command
            
        Returns:
            Command result as formatted string
        """
        # Normalize command
        command = command.lower().strip()
        
        handler = self._handlers.get(command)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                logger.error(f"[CommandHandler] Error handling {command}: {e}")
                return f"Error executing {command}: {str(e)}"
        
        return f"Unknown command: {command}. Available: {', '.join(self._handlers.keys())}"
    
    def _handle_reflect(self, args: str) -> str:
        """Handle /reflect command.
        
        Triggers a manual reflection cycle.
        """
        if not self.reflection_engine:
            return "Reflection engine not available."
        
        import asyncio
        
        # Run reflection cycle
        try:
            # Try to run in existing event loop
            loop = asyncio.get_running_loop()
            task = loop.create_task(
                self.reflection_engine.run_reflection_cycle(reason="on_demand")
            )
            # We can't await here, so return status
            return "Reflection cycle initiated. Check logs for results."
        except RuntimeError:
            # No running loop, try to run in new loop
            try:
                result = asyncio.run(
                    self.reflection_engine.run_reflection_cycle(reason="on_demand")
                )
                return self._format_reflection_result(result)
            except Exception as e:
                return f"Failed to run reflection: {e}"
    
    def _format_reflection_result(self, result: Dict[str, Any]) -> str:
        """Format reflection result for display."""
        lines = [
            "# Reflection Cycle Complete",
            "",
            f"**Reason:** {result.get('reason', 'unknown')}",
            f"**Timestamp:** {result.get('timestamp', 'unknown')}",
            "",
            "## Results",
            "",
            f"- **Patterns Detected:** {result.get('patterns_detected', 0)}",
            f"- **Opinions Formed:** {result.get('opinions_formed', 0)}",
            f"- **Gaps Promoted:** {result.get('gaps_promoted', 0)}",
            f"- **Meta Observations:** {result.get('meta_observations', 0)}",
            f"- **Growth Suggestions:** {result.get('growth_suggestions', 0)}",
        ]
        
        if result.get("error"):
            lines.extend(["", f"**Error:** {result['error']}"])
        
        return "\n".join(lines)
    
    def _handle_gaps(self, args: str) -> str:
        """Handle /gaps command.

        Lists capability gaps ranked by priority.
        """
        from memory.user_facts import FactCategory

        if not self.context_id:
            return "Error: No context ID set for this session."

        # Parse min_triggers from args
        min_triggers = 1
        if args.strip().isdigit():
            min_triggers = int(args.strip())

        gaps = self.store.list_capability_gaps(
            context_id=self.context_id,
            min_triggers=min_triggers
        )
        
        if not gaps:
            return f"No capability gaps with at least {min_triggers} trigger(s)."
        
        lines = [
            f"# Capability Gaps ({len(gaps)} total)",
            "",
            "| Priority | Status | Triggers | Description |",
            "|----------|--------|----------|-------------|",
        ]
        
        for gap in gaps[:20]:  # Limit to top20
            lines.append(
                f"| {gap.priority_score:.2f} | {gap.status} | {gap.trigger_count} | {gap.content[:60]}... |"
            )
        
        if gaps[0].workaround:
            lines.extend([
                "",
                "## Top Gap Workaround",
                f"**{gaps[0].content[:80]}:** {gaps[0].workaround}",
            ])
        
        return "\n".join(lines)
    
    def _handle_patterns(self, args: str) -> str:
        """Handle /patterns command.

        Shows detected patterns.
        """
        from memory.user_facts import FactCategory

        if not self.context_id:
            return "Error: No context ID set for this session."

        # Get patterns from session reflections
        reflections = self.store.list_by_category(
            context_id=self.context_id,
            category=FactCategory.SESSION_REFLECTION
        )
        
        patterns = []
        for ref in reflections:
            metadata = ref.metadata or {}
            if metadata.get("pattern_type"):
                patterns.append({
                    "description": ref.content,
                    "type": metadata.get("pattern_type", "unknown"),
                    "frequency": metadata.get("frequency", 1),
                    "confidence": metadata.get("confidence", 0.5),
                    "trend": metadata.get("trend_direction", "stable"),
                    "actionable": metadata.get("actionable", False),
                    "suggested_action": metadata.get("suggested_action"),
                })
        
        if not patterns:
            return "No patterns detected yet. Run /reflect to detect patterns."
        
        lines = [
            f"# Detected Patterns ({len(patterns)} total)",
            "",
        ]
        
        for p in patterns[:15]:
            emoji = "📈" if p["trend"] == "increasing" else "📉" if p["trend"] == "decreasing" else "➡️"
            action = "✅" if p["actionable"] else ""
            lines.append(f"## {p['type'].title()} Pattern {emoji} {action}")
            lines.append(f"**Description:** {p['description']}")
            lines.append(f"**Frequency:** {p['frequency']} | **Confidence:** {p['confidence']:.0%}")
            if p["suggested_action"]:
                lines.append(f"**Suggested Action:** {p['suggested_action']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _handle_opinions(self, args: str) -> str:
        """Handle /opinions command.

        Shows opinion pairs (user position vs agent response).
        """
        from memory.user_facts import FactCategory

        if not self.context_id:
            return "Error: No context ID set for this session."

        pairs = self.store.list_by_category(
            context_id=self.context_id,
            category=FactCategory.OPINION_PAIR
        )
        
        if not pairs:
            return "No opinion pairs logged yet."
        
        lines = [
            f"# Opinion Pairs ({len(pairs)} total)",
            "",
        ]
        
        for pair in pairs[:15]:
            metadata = pair.metadata or {}
            agreement = metadata.get("agreement_level", "partial")
            emoji = "🟢" if agreement == "agree" else "🟡" if agreement == "partial" else "🔴" if agreement == "disagree" else "⚪"
            
            lines.append(f"## {metadata.get('topic', pair.content[:50])} {emoji}")
            lines.append(f"**Operator Position:** {metadata.get('user_position', 'N/A')}")
            lines.append(f"**Agent Position:** {metadata.get('agent_position', 'N/A')}")
            lines.append(f"**Reasoning:** {metadata.get('agent_reasoning', 'N/A')}")
            lines.append(f"**Confidence:** {metadata.get('agent_confidence', 0):.0%}")
            
            evolution = metadata.get("evolution", [])
            if evolution:
                lines.append(f"**Evolution:** {len(evolution)} changes")
            lines.append("")
        
        return "\n".join(lines)
    
    def _handle_growth(self, args: str) -> str:
        """Handle /growth command.

        Shows operator growth report.
        """
        from agent.reflection.growth_tracker import GrowthTracker

        if not self.context_id:
            return "Error: No context ID set for this session."

        # Parse days from args
        days = 30
        if args.strip().isdigit():
            days = int(args.strip())

        tracker = GrowthTracker(self.store, self.context_id)
        report = tracker.generate_growth_report(days_back=days)

        return report.get("summary", "No growth report generated.")
    
    def _handle_meta(self, args: str) -> str:
        """Handle /meta command.

        Shows store health metrics and category suggestions.
        """
        from agent.reflection.meta_analysis import MetaAnalyzer

        if not self.context_id:
            return "Error: No context ID set for this session."

        analyzer = MetaAnalyzer(self.store)
        return analyzer.get_category_report()
    
    def _handle_tools(self, args: str) -> str:
        """Handle /tools command.

        Shows tool suggestions derived from capability gaps.
        """
        from memory.user_facts import FactCategory

        if not self.context_id:
            return "Error: No context ID set for this session."

        suggestions = self.store.list_by_category(
            context_id=self.context_id,
            category=FactCategory.TOOL_SUGGESTION
        )
        
        if not suggestions:
            return "No tool suggestions yet. Capability gaps need 3+ triggers to be promoted."
        
        lines = [
            f"# Tool Suggestions ({len(suggestions)} total)",
            "",
        ]
        
        for suggestion in suggestions:
            metadata = suggestion.metadata or {}
            priority = metadata.get("priority_score", 0)
            triggers = metadata.get("trigger_count", 0)
            criteria = metadata.get("acceptance_criteria", [])
            contexts = metadata.get("example_contexts", [])
            
            lines.append(f"## {suggestion.content}")
            lines.append(f"**Priority:** {priority:.2f} | **Triggers:** {triggers}")
            
            if criteria:
                lines.append("**Acceptance Criteria:**")
                for c in criteria:
                    lines.append(f"- ☐ {c}")
            
            if contexts:
                lines.append("**Example Triggers:**")
                for ctx in contexts[:3]:
                    lines.append(f"- {ctx[:80]}...")
            
            lines.append("")
        
        return "\n".join(lines)


def get_command_handler(
    store: Optional["UserFactStore"] = None,
    reflection_engine: Optional["ReflectionEngine"] = None,
    context_id: str = "",
) -> CommandHandler:
    """Get a CommandHandler instance.

    Args:
        store: Optional UserFactStore (will get global if not provided)
        reflection_engine: Optional ReflectionEngine
        context_id: The context ID for LanceDB storage

    Returns:
        CommandHandler instance
    """
    if store is None:
        from memory.user_facts import get_user_fact_store
        store = get_user_fact_store()

    return CommandHandler(store, reflection_engine, context_id)
