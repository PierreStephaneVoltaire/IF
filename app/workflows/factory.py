"""Workflow factory for creating workflow instances by reasoning pattern."""
from __future__ import annotations
from typing import Dict, Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from .base import WorkflowBase
from .simple import SimpleWorkflow, SequentialRefinementWorkflow
from .opposing import OpposingPerspectiveWorkflow
from .multi_perspective import MultiPerspectiveWorkflow
from .research import ResearchWorkflow


# Registry of workflow classes by pattern
WORKFLOW_REGISTRY: Dict[str, Type[WorkflowBase]] = {
    "simple": SimpleWorkflow,
    "sequential_refinement": SequentialRefinementWorkflow,
    "opposing_perspective": OpposingPerspectiveWorkflow,
    "multi_perspective": MultiPerspectiveWorkflow,
    "research": ResearchWorkflow,
}


def get_workflow(
    reasoning_pattern: str,
    stream: Optional["ConversationStream"] = None,
) -> WorkflowBase:
    """Get a workflow instance for the given reasoning pattern.
    
    Args:
        reasoning_pattern: The reasoning pattern name
        stream: Optional conversation stream for interactive workflows
        
    Returns:
        Workflow instance for the pattern
        
    Raises:
        ValueError: If the pattern is not recognized
    """
    workflow_class = WORKFLOW_REGISTRY.get(reasoning_pattern)
    
    if workflow_class is None:
        # Default to simple workflow for unknown patterns
        workflow_class = SimpleWorkflow
    
    return workflow_class(stream)


def get_available_patterns() -> list:
    """Get list of available reasoning patterns."""
    return list(WORKFLOW_REGISTRY.keys())


def register_workflow(pattern: str, workflow_class: Type[WorkflowBase]) -> None:
    """Register a custom workflow class for a pattern.
    
    Args:
        pattern: The reasoning pattern name
        workflow_class: The workflow class to register
    """
    WORKFLOW_REGISTRY[pattern] = workflow_class
