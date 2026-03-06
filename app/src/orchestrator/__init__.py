"""Orchestrator module for multi-step task execution and parallel analysis.

This module provides tools for the main agent to delegate complex work:
- execute_plan: Sequential multi-step plan execution with subagents
- analyze_parallel: Parallel code analysis from multiple perspectives

Key Components:
- PlanStep, ExecutionPlan, StepResult: Data models for plan execution
- execute_plan: Tool for sequential task delegation
- analyze_parallel: Tool for parallel code review/analysis
- PERSPECTIVE_PROMPTS: Pre-defined analysis perspectives

Reference: plan.md Parts7-9

Example:
    from orchestrator import get_orchestrator_tools, get_analyzer_tools
    
    # Get tools bound to a chat
    tools = get_orchestrator_tools(chat_id)
    tools.extend(get_analyzer_tools(chat_id))
    
    # Register with OpenHands agent
    agent = Agent(llm=llm, tools=tools, mcp_config=mcp_config)
"""
from .executor import (
    execute_plan,
    EXECUTE_PLAN_SCHEMA,
    PlanStep,
    ExecutionPlan,
    StepResult,
    get_orchestrator_tools,
    call_openrouter,
    run_subagent,
    build_subagent_prompt,
    parse_plan,
)
from .analyzer import (
    analyze_parallel,
    ANALYZE_PARALLEL_SCHEMA,
    PERSPECTIVE_PROMPTS,
    get_analyzer_tools,
)


__all__ = [
    # Executor
    "execute_plan",
    "EXECUTE_PLAN_SCHEMA",
    "PlanStep",
    "ExecutionPlan",
    "StepResult",
    "get_orchestrator_tools",
    "call_openrouter",
    "run_subagent",
    "build_subagent_prompt",
    "parse_plan",
    # Analyzer
    "analyze_parallel",
    "ANALYZE_PARALLEL_SCHEMA",
    "PERSPECTIVE_PROMPTS",
    "get_analyzer_tools",
]
