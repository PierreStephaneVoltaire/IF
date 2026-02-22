"""Workflows module for reasoning pattern execution.

This module provides workflow implementations for different reasoning patterns:
- simple: Direct agent execution
- sequential_refinement: Iterative improvement (planner-executor-evaluator)
- opposing_perspective: Two parallel agents with opposing views
- multi_perspective: Multiple agents with aggregation
- research: Research-first approach with domain synthesis
"""
from .base import WorkflowBase, WorkflowContext, AgentInvocation
from .simple import SimpleWorkflow, SequentialRefinementWorkflow
from .opposing import OpposingPerspectiveWorkflow
from .multi_perspective import MultiPerspectiveWorkflow
from .research import ResearchWorkflow
from .factory import (
    get_workflow,
    get_available_patterns,
    register_workflow,
    WORKFLOW_REGISTRY,
)
from .agent_executor import AgentExecutor, AgentResult, run_agent_with_tools

__all__ = [
    # Base classes
    "WorkflowBase",
    "WorkflowContext",
    "AgentInvocation",
    
    # Workflow implementations
    "SimpleWorkflow",
    "SequentialRefinementWorkflow",
    "OpposingPerspectiveWorkflow",
    "MultiPerspectiveWorkflow",
    "ResearchWorkflow",
    
    # Factory functions
    "get_workflow",
    "get_available_patterns",
    "register_workflow",
    "WORKFLOW_REGISTRY",
    
    # Agent execution
    "AgentExecutor",
    "AgentResult",
    "run_agent_with_tools",
]
