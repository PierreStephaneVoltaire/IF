"""Orchestrator analyzer for parallel code analysis.

This module implements Part8 of plan.md - the analyze_parallel tool that
spawns multiple subagents in parallel to analyze code from different
perspectives, then synthesizes the findings.

Reference: plan.md Part8 - Orchestrator — Parallel Analysis (Planning Mode)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

import httpx

from openhands.sdk import Tool

from config import (
    ORCHESTRATOR_ANALYSIS_MODEL,
    ORCHESTRATOR_SYNTHESIS_MODEL,
    ORCHESTRATOR_ANALYSIS_MAX_TURNS,
)
from terminal import get_lifecycle_manager

from .executor import run_subagent, StepResult

logger = logging.getLogger(__name__)


# ============================================================================
# Perspective Prompts
# ============================================================================

PERSPECTIVE_PROMPTS: Dict[str, str] = {
    "security": (
        "You are a security reviewer. Use the terminal to inspect the codebase. Focus on:\n"
        "- Input validation, injection vectors\n"
        "- Auth/authz gaps\n"
        "- Hardcoded secrets\n"
        "- Dependency vulnerabilities (check with pip audit, npm audit, etc.)\n"
        "- Data exposure, overly verbose errors\n\n"
        "Write findings to /home/user/workspace/findings/security.md\n"
        "Format: ## Critical / ## High / ## Medium / ## Low with file:line references."
    ),
    "performance": (
        "You are a performance engineer. Use the terminal to inspect the codebase. Focus on:\n"
        "- Algorithmic complexity (O(n²) loops, redundant work)\n"
        "- Database query patterns (N+1, unbounded selects)\n"
        "- Memory (large allocs, unbounded caches)\n"
        "- I/O (blocking in async paths, missing pooling)\n"
        "- Concurrency (lock contention, race conditions)\n\n"
        "Write findings to /home/user/workspace/findings/performance.md\n"
        "Format: ## Critical / ## High / ## Medium / ## Low with specific examples."
    ),
    "architecture": (
        "You are a software architect. Use the terminal to inspect the codebase. Focus on:\n"
        "- Coupling, circular dependencies\n"
        "- Leaky abstractions, god classes/modules\n"
        "- Error handling consistency\n"
        "- Testability, missing seams\n"
        "- Scalability bottlenecks\n\n"
        "Write findings to /home/user/workspace/findings/architecture.md\n"
        "Format: ## Critical / ## High / ## Medium / ## Low with recommendations."
    ),
    "testing": (
        "You are a QA engineer. Use the terminal to inspect the codebase. Focus on:\n"
        "- Test coverage gaps\n"
        "- Missing edge case tests\n"
        "- Test quality (are assertions meaningful?)\n"
        "- Integration vs unit test balance\n\n"
        "Write findings to /home/user/workspace/findings/testing.md\n"
        "Format: ## Critical / ## High / ## Medium / ## Low with specific test suggestions."
    ),
    "documentation": (
        "You are a documentation reviewer. Use the terminal to inspect the codebase. Focus on:\n"
        "- Missing or outdated docstrings\n"
        "- README accuracy\n"
        "- API documentation completeness\n"
        "- Confusing naming that needs explanation\n\n"
        "Write findings to /home/user/workspace/findings/documentation.md\n"
        "Format: ## Critical / ## High / ## Medium / ## Low with specific improvements."
    ),
}


# ============================================================================
# Tool Schema
# ============================================================================

ANALYZE_PARALLEL_SCHEMA = {
    "name": "analyze_parallel",
    "description": (
        "Spawn parallel analysis subagents that each review code/context from "
        "a different perspective. Results are written to /home/user/workspace/findings/, "
        "then a synthesizer combines them. Returns the synthesized report path. "
        "Perspectives: security, performance, architecture, testing, documentation. "
        "Subagents have terminal access to read and inspect the codebase."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "context": {
                "type": "string",
                "description": "What to analyze and any specific concerns."
            },
            "target_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Workspace paths to focus on. Subagents can also explore freely."
            },
            "perspectives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Which perspectives. Default: ['security', 'performance', 'architecture']."
            }
        },
        "required": ["context"]
    }
}


# ============================================================================
# Main Tool: analyze_parallel
# ============================================================================

async def analyze_parallel(
    context: str,
    target_paths: Optional[List[str]] = None,
    perspectives: Optional[List[str]] = None,
    *,
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Run parallel analysis from multiple perspectives.
    
    Spawns subagents for each perspective in parallel, then synthesizes
    results into a single prioritized report.
    
    Args:
        context: What to analyze and any specific concerns
        target_paths: Optional list of paths to focus on
        perspectives: List of perspectives (default: security, performance, architecture)
        chat_id: Chat ID for terminal container access
        http_client: Optional HTTP client for API calls
        
    Returns:
        Summary string with path to synthesized report
    """
    # Default perspectives
    if perspectives is None:
        perspectives = ["security", "performance", "architecture"]
    
    # Filter to valid perspectives
    valid_perspectives = [p for p in perspectives if p in PERSPECTIVE_PROMPTS]
    if not valid_perspectives:
        return "ERROR: No valid perspectives specified. Valid options: " + ", ".join(PERSPECTIVE_PROMPTS.keys())
    
    logger.info(f"[Analyzer] Starting parallel analysis with perspectives: {valid_perspectives}")
    
    should_close = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=120.0)
        should_close = True
    
    try:
        # Ensure findings directory exists
        await _ensure_findings_dir(chat_id, http_client)
        
        # Build full context with target paths
        full_context = context
        if target_paths:
            full_context += "\n\nTarget paths to focus on:\n" + "\n".join(f"- {p}" for p in target_paths)
        
        # Launch all perspectives concurrently
        tasks = []
        for p in valid_perspectives:
            prompt = PERSPECTIVE_PROMPTS[p] + f"\n\n## Context\n{full_context}"
            output_file = f"findings/{p}.md"
            
            tasks.append(
                run_subagent(
                    system_prompt=prompt,
                    user_message=f"Analyze from {p} perspective. Write to /home/user/workspace/{output_file}.",
                    chat_id=chat_id,
                    model=ORCHESTRATOR_ANALYSIS_MODEL,
                    max_turns=ORCHESTRATOR_ANALYSIS_MAX_TURNS,
                    http_client=http_client,
                )
            )
        
        # Wait for all perspectives to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes
        succeeded = 0
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"[Analyzer] Perspective {valid_perspectives[i]} failed: {r}")
            elif isinstance(r, StepResult) and r.success:
                succeeded += 1
                logger.info(f"[Analyzer] Perspective {valid_perspectives[i]} completed")
            else:
                error = r.error if isinstance(r, StepResult) else "Unknown error"
                logger.warning(f"[Analyzer] Perspective {valid_perspectives[i]} failed: {error}")
        
        # Run synthesizer
        logger.info("[Analyzer] Running synthesizer...")
        synth_result = await run_subagent(
            system_prompt=(
                "You are a technical lead. Read all files in /home/user/workspace/findings/. "
                "Synthesize into a single prioritized report. Deduplicate. Note which perspectives "
                "flagged each issue. Add a Recommended Action Plan. "
                "Write to /home/user/workspace/findings/synthesized.md\n\n"
                "Format:\n"
                "## Executive Summary\n"
                "Brief overview of findings.\n\n"
                "## Critical Issues\n"
                "Issues that need immediate attention.\n\n"
                "## High Priority\n"
                "Important issues to address soon.\n\n"
                "## Medium Priority\n"
                "Issues to address in upcoming iterations.\n\n"
                "## Low Priority / Nice to Have\n"
                "Minor improvements.\n\n"
                "## Recommended Action Plan\n"
                "Ordered list of steps to address the findings."
            ),
            user_message="Synthesize all analysis findings from /home/user/workspace/findings/.",
            chat_id=chat_id,
            model=ORCHESTRATOR_SYNTHESIS_MODEL,
            max_turns=10,
            http_client=http_client,
        )
        
        # Build result message
        lines = [
            f"Parallel analysis complete. {succeeded}/{len(valid_perspectives)} perspectives succeeded.",
            f"Synthesized report: /home/user/workspace/findings/synthesized.md",
        ]
        
        if synth_result.success:
            lines.append("Read the synthesized report for prioritized findings and action plan.")
        else:
            lines.append(f"Synthesis failed: {synth_result.error}. Read individual findings/ files.")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"[Analyzer] Parallel analysis error: {e}")
        return f"Parallel analysis failed: {type(e).__name__}: {e}"
    finally:
        if should_close:
            await http_client.aclose()


async def _ensure_findings_dir(chat_id: str, http_client: httpx.AsyncClient) -> None:
    """Ensure the findings directory exists.
    
    Args:
        chat_id: Chat ID for terminal container access
        http_client: HTTP client for API calls
    """
    from agent.tools.terminal_tools import terminal_execute
    
    try:
        await terminal_execute(
            command="mkdir -p /home/user/workspace/findings",
            workdir="/home/user/workspace",
            chat_id=chat_id,
        )
    except Exception as e:
        logger.warning(f"[Analyzer] Failed to create findings dir: {e}")


# ============================================================================
# Tool Registration
# ============================================================================

def get_analyzer_tools(
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> List[Tool]:
    """Get analyzer tools bound to a chat.
    
    This function creates tool instances with the chat_id
    pre-bound for use in the OpenHands agent.
    
    Args:
        chat_id: Unique chat identifier
        http_client: Optional shared HTTP client for connection pooling
        
    Returns:
        List of Tool instances for analyzer operations
    """
    from functools import partial
    
    tools = []
    
    # analyze_parallel tool
    tools.append(Tool(
        name="analyze_parallel",
        description="""Spawn parallel analysis subagents that each review code/context from different perspectives.

Results are written to /home/user/workspace/findings/, then a synthesizer combines them.

Available perspectives:
- security: Input validation, injection vectors, auth/authz gaps, hardcoded secrets
- performance: Algorithmic complexity, database patterns, memory usage, I/O issues
- architecture: Coupling, abstractions, error handling, testability, scalability
- testing: Test coverage gaps, edge cases, test quality, integration vs unit balance
- documentation: Docstrings, README accuracy, API docs, naming clarity

The synthesizer creates a prioritized report with recommended action plan.""",
        parameters={
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "What to analyze and any specific concerns."
                },
                "target_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Workspace paths to focus on. Subagents can also explore freely."
                },
                "perspectives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Which perspectives. Default: ['security', 'performance', 'architecture']."
                }
            },
            "required": ["context"]
        },
        function=partial(analyze_parallel, chat_id=chat_id, http_client=http_client),
    ))
    
    return tools
