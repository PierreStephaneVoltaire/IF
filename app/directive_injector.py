"""Directive Injector for subagent context.

This module handles the parsing and injection of directives from the main
IF Prototype A1 system prompt into subagent contexts. Directives are NOT
part of subagent system prompts - they are dynamically injected by the
main orchestrator based on the task category and reasoning pattern.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Load main system prompt
MAIN_SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "main_system_prompt.txt")
with open(MAIN_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
    MAIN_SYSTEM_PROMPT = f.read()


@dataclass
class Directive:
    """A single directive from the IF Prototype A1 system."""
    id: str  # e.g., "0-1", "1-2"
    alpha: int  # Priority tier (0-5)
    beta: int  # Order within alpha tier
    title: str
    content: str
    categories: Set[str] = field(default_factory=set)  # Applicable categories
    
    @property
    def priority(self) -> tuple:
        """Get priority tuple for sorting (lower is higher priority)."""
        return (self.alpha, self.beta)
    
    def __str__(self) -> str:
        return f"Directive {self.id} ({self.title}): {self.content[:100]}..."


class DirectiveParser:
    """Parses directives from the main system prompt."""
    
    def __init__(self, system_prompt: str = MAIN_SYSTEM_PROMPT):
        self.system_prompt = system_prompt
        self._directives: Optional[Dict[str, Directive]] = None
    
    def parse(self) -> Dict[str, Directive]:
        """Parse all directives from the system prompt.
        
        Returns:
            Dictionary mapping directive IDs to Directive objects
        """
        if self._directives is not None:
            return self._directives
        
        self._directives = {}
        
        # Find the DIRECTIVES section
        section_match = re.search(
            r'═+\s*\nDIRECTIVES\s*\n═+\s*\n(.+?)(?=═|$)',
            self.system_prompt,
            re.DOTALL
        )
        
        if not section_match:
            return self._directives
        
        section = section_match.group(1)
        
        # Parse individual directives
        # Format: "X-Y  TITLE\nContent..."
        directive_pattern = re.compile(
            r'(\d+)-(\d+)\s+([A-Z][A-Z\s/()\-]+?)(?:\n|\s{2,})(.+?)(?=\d+-\d+\s+[A-Z]|\Z)',
            re.DOTALL
        )
        
        for match in directive_pattern.finditer(section):
            alpha = int(match.group(1))
            beta = int(match.group(2))
            title = match.group(3).strip()
            content = match.group(4).strip()
            directive_id = f"{alpha}-{beta}"
            
            directive = Directive(
                id=directive_id,
                alpha=alpha,
                beta=beta,
                title=title,
                content=content,
            )
            
            self._directives[directive_id] = directive
        
        return self._directives
    
    def get_directive(self, directive_id: str) -> Optional[Directive]:
        """Get a specific directive by ID."""
        directives = self.parse()
        return directives.get(directive_id)
    
    def get_by_alpha(self, alpha: int) -> List[Directive]:
        """Get all directives with a specific alpha (priority tier)."""
        directives = self.parse()
        return [d for d in directives.values() if d.alpha == alpha]
    
    def get_fundamental(self) -> List[Directive]:
        """Get all FUNDAMENTAL (alpha=0) directives."""
        return self.get_by_alpha(0)
    
    def get_critical(self) -> List[Directive]:
        """Get all CRITICAL (alpha=1) directives."""
        return self.get_by_alpha(1)


class DirectiveInjector:
    """Injects relevant directives into subagent context.
    
    The injector determines which directives apply based on:
    - Category of the task (coding, architecture, etc.)
    - Reasoning pattern being used
    - Specific requirements of the subagent
    """
    
    # Mapping of categories to applicable directive IDs
    CATEGORY_DIRECTIVES = {
        "coding": {
            "0-2",  # NO FABRICATION
            "0-3",  # NO HARM BY OMISSION
            "1-1",  # SECURITY FIRST
            "1-2",  # PRODUCTION-GRADE CODE
            "1-3",  # COMPLETE CODE OUTPUT
            "2-1",  # CHALLENGE BAD ARCHITECTURE
            "2-4",  # CODE MINIMALISM
            "2-5",  # FRONTEND/BACKEND BEST PRACTICES
        },
        "architecture": {
            "0-2",  # NO FABRICATION
            "0-3",  # NO HARM BY OMISSION
            "1-1",  # SECURITY FIRST
            "2-1",  # CHALLENGE BAD ARCHITECTURE
            "2-2",  # SHOW YOUR REASONING
            "2-3",  # DEVOPS: IaC PREFERRED
            "4-1",  # MULTI-STEP PLANS
            "4-2",  # ALTERNATIVES
        },
        "social": {
            "0-2",  # NO FABRICATION
            "2-7",  # OPERATOR DISTRESS PROTOCOL
            "3-3",  # RESPONSE LENGTH
            "3-4",  # HUMOR CALIBRATION
        },
        "financial": {
            "0-2",  # NO FABRICATION
            "0-3",  # NO HARM BY OMISSION
            "0-4",  # SCOPE HONESTY
            "1-5",  # FINANCIAL RISK DISCLOSURE
            "2-2",  # SHOW YOUR REASONING
        },
        "health": {
            "0-2",  # NO FABRICATION
            "0-3",  # NO HARM BY OMISSION
            "0-4",  # SCOPE HONESTY
            "1-4",  # EVIDENCE-BASED HEALTH GUIDANCE
            "2-8",  # POWERLIFTING PROGRAMMING
        },
        "general": {
            "0-2",  # NO FABRICATION
            "0-3",  # NO HARM BY OMISSION
            "0-4",  # SCOPE HONESTY
            "2-2",  # SHOW YOUR REASONING
            "2-7",  # OPERATOR DISTRESS PROTOCOL
            "4-3",  # CONTEXT GATHERING
        },
        "shell": {
            "0-2",  # NO FABRICATION
            "1-1",  # SECURITY FIRST
            "3-2",  # SHELL OUTPUT
        },
    }
    
    # Additional directives based on reasoning pattern
    PATTERN_DIRECTIVES = {
        "simple": set(),
        "opposing_perspective": {"2-2", "4-2"},  # Show reasoning, alternatives
        "multi_perspective": {"2-2", "4-2"},
        "sequential_refinement": {"1-2", "1-3", "4-1"},  # Production code, complete output, plans
        "research": {"0-2", "2-2"},  # No fabrication, show reasoning
    }
    
    def __init__(self, parser: Optional[DirectiveParser] = None):
        self.parser = parser or DirectiveParser()
    
    def get_directives_for_context(
        self,
        category: str,
        reasoning_pattern: str,
        additional_ids: Optional[Set[str]] = None,
    ) -> List[Directive]:
        """Get all applicable directives for a given context.
        
        Args:
            category: The task category
            reasoning_pattern: The reasoning pattern being used
            additional_ids: Additional directive IDs to include
            
        Returns:
            List of Directive objects, sorted by priority
        """
        # Collect applicable directive IDs
        directive_ids: Set[str] = set()
        
        # Add category-specific directives
        if category in self.CATEGORY_DIRECTIVES:
            directive_ids.update(self.CATEGORY_DIRECTIVES[category])
        
        # Add pattern-specific directives
        if reasoning_pattern in self.PATTERN_DIRECTIVES:
            directive_ids.update(self.PATTERN_DIRECTIVES[reasoning_pattern])
        
        # Add any additional requested directives
        if additional_ids:
            directive_ids.update(additional_ids)
        
        # Always include fundamental directives (alpha=0)
        for directive in self.parser.get_fundamental():
            directive_ids.add(directive.id)
        
        # Get actual directive objects
        directives = []
        for directive_id in directive_ids:
            directive = self.parser.get_directive(directive_id)
            if directive:
                directives.append(directive)
        
        # Sort by priority
        directives.sort(key=lambda d: d.priority)
        
        return directives
    
    def format_for_injection(
        self,
        directives: List[Directive],
        include_priority: bool = False,
    ) -> str:
        """Format directives for injection into subagent prompt.
        
        Args:
            directives: List of directives to format
            include_priority: Whether to include priority information
            
        Returns:
            Formatted string ready for injection
        """
        if not directives:
            return ""
        
        lines = [
            "## DIRECTIVES (from IF Prototype A1 Orchestrator)",
            "These directives must be followed. Priority decreases from top to bottom.",
            ""
        ]
        
        current_alpha = -1
        alpha_labels = {
            0: "### FUNDAMENTAL (Never break)",
            1: "### CRITICAL (Ask before bypassing)",
            2: "### STANDARD (Follow unless it degrades quality)",
            3: "### PREFERENCE (Encouraged but optional)",
            4: "### ADVISORY (Consider, may ignore if conflicts)",
            5: "### NOTES (Background context)",
        }
        
        for directive in directives:
            if include_priority and directive.alpha != current_alpha:
                current_alpha = directive.alpha
                if current_alpha in alpha_labels:
                    lines.append(alpha_labels[current_alpha])
                    lines.append("")
            
            lines.append(f"**Directive {directive.id} - {directive.title}**")
            lines.append(directive.content)
            lines.append("")
        
        return "\n".join(lines)
    
    def inject(
        self,
        category: str,
        reasoning_pattern: str,
        subagent_prompt: str,
        additional_ids: Optional[Set[str]] = None,
    ) -> str:
        """Inject directives into a subagent prompt.
        
        Args:
            category: The task category
            reasoning_pattern: The reasoning pattern
            subagent_prompt: The original subagent prompt
            additional_ids: Additional directive IDs to include
            
        Returns:
            Subagent prompt with directives injected
        """
        directives = self.get_directives_for_context(
            category,
            reasoning_pattern,
            additional_ids,
        )
        
        directive_block = self.format_for_injection(directives, include_priority=True)
        
        if not directive_block:
            return subagent_prompt
        
        # Inject at the beginning of the prompt
        return f"{directive_block}\n\n---\n\n{subagent_prompt}"


# Global instances
_parser: Optional[DirectiveParser] = None
_injector: Optional[DirectiveInjector] = None


def get_directive_parser() -> DirectiveParser:
    """Get the global directive parser instance."""
    global _parser
    if _parser is None:
        _parser = DirectiveParser()
    return _parser


def get_directive_injector() -> DirectiveInjector:
    """Get the global directive injector instance."""
    global _injector
    if _injector is None:
        _injector = DirectiveInjector(get_directive_parser())
    return _injector


def inject_directives(
    category: str,
    reasoning_pattern: str,
    subagent_prompt: str,
    additional_ids: Optional[Set[str]] = None,
) -> str:
    """Convenience function to inject directives.
    
    Args:
        category: The task category
        reasoning_pattern: The reasoning pattern
        subagent_prompt: The original subagent prompt
        additional_ids: Additional directive IDs to include
        
    Returns:
        Subagent prompt with directives injected
    """
    injector = get_directive_injector()
    return injector.inject(category, reasoning_pattern, subagent_prompt, additional_ids)
