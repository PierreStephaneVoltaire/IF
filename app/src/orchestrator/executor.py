"""Orchestrator executor for sequential plan execution.

This module implements Part7 of plan.md - the execute_plan tool that allows
the main agent to delegate multi-step tasks to focused subagents.

Each subagent runs with terminal access to the same persistent workspace,
allowing sequential steps to build on each other's filesystem state.

Reference: plan.md Part7 - Orchestrator — Plan Execution (Sequential)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from openhands.sdk import Tool

from config import (
    LLM_BASE_URL,
    OPENROUTER_API_KEY,
    ORCHESTRATOR_SUBAGENT_MODEL,
    ORCHESTRATOR_MAX_TURNS,
)
from terminal import strip_files_line, FileRef, get_lifecycle_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class PlanStep:
    """A single step in an execution plan.
    
    Attributes:
        index: Step number (1-based)
        title: Short title for the step
        description: Detailed instructions for what to do
        expected_outputs: List of file paths this step should produce
    """
    index: int
    title: str
    description: str
    expected_outputs: List[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:
    """A complete execution plan with multiple steps.
    
    Attributes:
        goal: What the overall task achieves
        context: Shared context all steps need (repo URL, language, constraints)
        steps: List of PlanStep objects
    """
    goal: str
    context: str = ""
    steps: List[PlanStep] = field(default_factory=list)


@dataclass
class StepResult:
    """Result from executing a single plan step.
    
    Attributes:
        step_index: Index of the step that was executed
        success: Whether the step completed successfully
        summary: Brief summary of what was done
        files: List of files created or modified
        error: Error message if step failed
    """
    step_index: int
    success: bool
    summary: str = ""
    files: List[FileRef] = field(default_factory=list)
    error: Optional[str] = None


# ============================================================================
# LLM Response Parsing
# ============================================================================

@dataclass
class LLMResponse:
    """Parsed LLM response.
    
    Attributes:
        content: Text content of the response
        tool_calls: List of tool calls if any
    """
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_message(self) -> Dict[str, Any]:
        """Convert to OpenAI message format."""
        if self.tool_calls:
            return {
                "role": "assistant",
                "content": self.content,
                "tool_calls": self.tool_calls
            }
        return {"role": "assistant", "content": self.content}


def parse_llm_response(data: Dict[str, Any]) -> LLMResponse:
    """Parse OpenRouter/OpenAI response into LLMResponse.
    
    Args:
        data: Raw JSON response from API
        
    Returns:
        Parsed LLMResponse object
    """
    choices = data.get("choices", [])
    if not choices:
        return LLMResponse()
    
    choice = choices[0]
    message = choice.get("message", {})
    
    content = message.get("content", "") or ""
    tool_calls = []
    
    # Parse tool calls if present
    raw_tool_calls = message.get("tool_calls", [])
    for tc in raw_tool_calls:
        tool_calls.append({
            "id": tc.get("id", ""),
            "type": tc.get("type", "function"),
            "function": {
                "name": tc.get("function", {}).get("name", ""),
                "arguments": tc.get("function", {}).get("arguments", "{}")
            }
        })
    
    return LLMResponse(content=content, tool_calls=tool_calls)


# ============================================================================
# OpenRouter API Client
# ============================================================================

async def call_openrouter(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> LLMResponse:
    """Make a non-streaming chat completion call to OpenRouter.
    
    Args:
        model: Model identifier (e.g., "anthropic/claude-sonnet-4")
        messages: List of message dicts in OpenAI format
        tools: Optional list of tool schemas
        http_client: Optional httpx AsyncClient (creates one if not provided)
        
    Returns:
        Parsed LLMResponse
        
    Raises:
        httpx.HTTPStatusError: On API errors
        httpx.TimeoutException: On timeout
    """
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    if tools:
        body["tools"] = [{"type": "function", "function": t} for t in tools]
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    should_close = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=120.0)
        should_close = True
    
    try:
        resp = await http_client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=body,
            timeout=120.0,
        )
        resp.raise_for_status()
        return parse_llm_response(resp.json())
    finally:
        if should_close:
            await http_client.aclose()


# ============================================================================
# Subagent Execution
# ============================================================================

# Tool schema for terminal_execute (simplified for subagent use)
TERMINAL_EXECUTE_SCHEMA = {
    "name": "terminal_execute",
    "description": (
        "Run a shell command in the persistent terminal. "
        "The terminal preserves state across calls. "
        "Workspace is at /home/user/workspace."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute."
            },
            "workdir": {
                "type": "string",
                "description": "Working directory. Default: /home/user/workspace",
                "default": "/home/user/workspace"
            }
        },
        "required": ["command"]
    }
}


async def run_subagent(
    system_prompt: str,
    user_message: str,
    chat_id: str,
    model: str,
    max_turns: int = ORCHESTRATOR_MAX_TURNS,
    http_client: Optional[httpx.AsyncClient] = None,
) -> StepResult:
    """Run a subagent with terminal access.
    
    A subagent is a short-lived LLM conversation with tool access.
    It can execute terminal commands and returns a StepResult.
    
    Args:
        system_prompt: System prompt for the subagent
        user_message: User message to start the conversation
        chat_id: Chat ID for terminal container access
        model: Model to use for the subagent
        max_turns: Maximum number of turns before timeout
        http_client: Optional httpx AsyncClient
        
    Returns:
        StepResult with success status and any files created
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    tools = [TERMINAL_EXECUTE_SCHEMA]
    
    should_close = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=120.0)
        should_close = True
    
    try:
        for turn in range(max_turns):
            logger.debug(f"[Subagent] Turn {turn + 1}/{max_turns}")
            
            response = await call_openrouter(
                model=model,
                messages=messages,
                tools=tools,
                http_client=http_client,
            )
            
            if response.tool_calls:
                # Append assistant message with tool calls
                messages.append(response.to_message())
                
                for tc in response.tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    tool_id = tc.get("id", "")
                    
                    if tool_name == "terminal_execute":
                        try:
                            args = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            args = {}
                        
                        # Execute terminal command
                        output = await _execute_terminal_command(
                            command=args.get("command", ""),
                            workdir=args.get("workdir", "/home/user/workspace"),
                            chat_id=chat_id,
                            http_client=http_client,
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": output
                        })
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "content": f"Unknown tool: {tool_name}"
                        })
            else:
                # Agent finished - extract content and FILES:
                content = response.content or ""
                cleaned, files = strip_files_line(content)
                
                return StepResult(
                    step_index=0,  # Set by caller
                    success=True,
                    summary=cleaned[:500],  # Truncate summary
                    files=files,
                    error=None,
                )
        
        # Exceeded max turns
        return StepResult(
            step_index=0,
            success=False,
            summary="",
            files=[],
            error=f"Exceeded {max_turns} turns without completion"
        )
        
    except Exception as e:
        logger.error(f"[Subagent] Error: {e}")
        return StepResult(
            step_index=0,
            success=False,
            summary="",
            files=[],
            error=f"{type(e).__name__}: {e}"
        )
    finally:
        if should_close:
            await http_client.aclose()


async def _execute_terminal_command(
    command: str,
    workdir: str,
    chat_id: str,
    http_client: httpx.AsyncClient,
) -> str:
    """Execute a terminal command for a subagent.
    
    Args:
        command: Shell command to execute
        workdir: Working directory
        chat_id: Chat ID for container access
        http_client: HTTP client for API calls
        
    Returns:
        Command output or error message
    """
    from agent.tools.terminal_tools import terminal_execute
    
    try:
        return await terminal_execute(
            command=command,
            workdir=workdir,
            chat_id=chat_id,
        )
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"


# ============================================================================
# Subagent Prompt Builder
# ============================================================================

def build_subagent_prompt(
    plan: ExecutionPlan,
    step: PlanStep,
    previous: List[StepResult],
) -> str:
    """Build the system prompt for a subagent.
    
    Args:
        plan: The overall execution plan
        step: The specific step this subagent should execute
        previous: Results from previous steps
        
    Returns:
        System prompt string
    """
    parts = [
        "You are an autonomous execution agent. Complete the assigned task using the terminal.",
        "",
        f"## Overall Goal\n{plan.goal}",
    ]
    
    if plan.context:
        parts.append(f"\n## Context\n{plan.context}")
    
    if previous:
        parts.append("\n## Previous Steps")
        for r in previous:
            status = "completed" if r.success else "FAILED"
            parts.append(f"- Step {r.step_index} ({status}): {r.summary[:200]}")
            for f in r.files:
                parts.append(f"  Created: {f.path}")
    
    parts.append(f"\n## Your Task — Step {step.index}: {step.title}")
    parts.append(step.description)
    
    if step.expected_outputs:
        parts.append("\n## Expected Outputs")
        for o in step.expected_outputs:
            parts.append(f"- {o}")
    
    parts.append(
        "\n## Rules\n"
        "1. Use terminal_execute for all commands.\n"
        "2. Work in /home/user/workspace/.\n"
        "3. Verify outputs exist before finishing (ls, cat, test -f).\n"
        "4. If something fails, try to fix it. After 3 failed attempts at the same thing, stop and explain.\n"
        "5. End with a FILES: line listing files you created or modified.\n"
        "   Format: FILES: /path/to/file (description), /path/to/another (description)"
    )
    
    return "\n".join(parts)


# ============================================================================
# Plan Parsing
# ============================================================================

def parse_plan(goal: str, context: str, steps: List[Dict[str, Any]]) -> ExecutionPlan:
    """Parse plan data into ExecutionPlan object.
    
    Args:
        goal: Overall goal string
        context: Shared context string
        steps: List of step dictionaries
        
    Returns:
        ExecutionPlan object
    """
    plan_steps = []
    for i, step_data in enumerate(steps, start=1):
        plan_steps.append(PlanStep(
            index=i,
            title=step_data.get("title", f"Step {i}"),
            description=step_data.get("description", ""),
            expected_outputs=step_data.get("expected_outputs", []),
        ))
    
    return ExecutionPlan(
        goal=goal,
        context=context,
        steps=plan_steps,
    )


# ============================================================================
# Main Tool: execute_plan
# ============================================================================

EXECUTE_PLAN_SCHEMA = {
    "name": "execute_plan",
    "description": (
        "Submit a structured multi-step plan for autonomous execution. "
        "Each step is executed sequentially by a focused subagent with "
        "terminal access to the same persistent workspace. Use this for "
        "tasks requiring multiple distinct phases: clone→install→test→fix, "
        "scaffold→implement→validate, etc. Each step sees the filesystem "
        "state left by previous steps."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "What the overall task achieves."
            },
            "context": {
                "type": "string",
                "description": "Shared context all steps need (repo URL, language, constraints)."
            },
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {
                            "type": "string",
                            "description": "Detailed instructions. Be specific about what to do, what commands to run, what files to produce."
                        },
                        "expected_outputs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File paths this step should produce."
                        }
                    },
                    "required": ["title", "description"]
                }
            }
        },
        "required": ["goal", "steps"]
    }
}


async def execute_plan(
    goal: str,
    steps: List[Dict[str, Any]],
    context: str = "",
    *,
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:
    """Execute a multi-step plan with sequential subagents.
    
    Args:
        goal: What the overall task achieves
        steps: List of step dictionaries with title, description, expected_outputs
        context: Shared context for all steps
        chat_id: Chat ID for terminal container access
        http_client: Optional HTTP client for API calls
        
    Returns:
        Summary string of plan execution results
    """
    logger.info(f"[Orchestrator] Starting plan execution: {goal}")
    
    plan = parse_plan(goal, context, steps)
    results: List[StepResult] = []
    
    should_close = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=120.0)
        should_close = True
    
    try:
        for step in plan.steps:
            logger.info(f"[Orchestrator] Executing step {step.index}: {step.title}")
            
            prompt = build_subagent_prompt(plan, step, results)
            result = await run_subagent(
                system_prompt=prompt,
                user_message=f"Execute: {step.title}\n\n{step.description}",
                chat_id=chat_id,
                model=ORCHESTRATOR_SUBAGENT_MODEL,
                max_turns=ORCHESTRATOR_MAX_TURNS,
                http_client=http_client,
            )
            
            # Set step index
            result.step_index = step.index
            results.append(result)
            
            if not result.success:
                logger.warning(f"[Orchestrator] Step {step.index} failed: {result.error}")
                break
            
            logger.info(f"[Orchestrator] Step {step.index} completed: {result.summary[:100]}")
        
        # Format summary for main agent
        lines = [
            f"Plan execution: {len([r for r in results if r.success])}/{len(plan.steps)} steps completed."
        ]
        
        for r in results:
            mark = "✓" if r.success else "✗"
            lines.append(f"  [{mark}] Step {r.step_index}: {r.summary[:200]}")
            if r.files:
                for f in r.files:
                    lines.append(f"      → {f.path} ({f.description})")
            if r.error:
                lines.append(f"      ERROR: {r.error}")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"[Orchestrator] Plan execution error: {e}")
        return f"Plan execution failed: {type(e).__name__}: {e}"
    finally:
        if should_close:
            await http_client.aclose()


# ============================================================================
# Tool Registration
# ============================================================================

def get_orchestrator_tools(
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> List[Tool]:
    """Get orchestrator tools bound to a chat.
    
    This function creates tool instances with the chat_id
    pre-bound for use in the OpenHands agent.
    
    Args:
        chat_id: Unique chat identifier
        http_client: Optional shared HTTP client for connection pooling
        
    Returns:
        List of Tool instances for orchestrator operations
    """
    from functools import partial
    
    tools = []
    
    # execute_plan tool
    tools.append(Tool(
        name="execute_plan",
        description="""Submit a structured multi-step plan for autonomous execution.

Each step is executed sequentially by a focused subagent with terminal access to the same persistent workspace. Use this for tasks requiring multiple distinct phases: clone→install→test→fix, scaffold→implement→validate, etc.

Each step sees the filesystem state left by previous steps. Steps are executed until one fails or all complete.""",
        parameters={
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "What the overall task achieves."
                },
                "context": {
                    "type": "string",
                    "description": "Shared context all steps need (repo URL, language, constraints)."
                },
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {
                                "type": "string",
                                "description": "Detailed instructions. Be specific about what to do, what commands to run, what files to produce."
                            },
                            "expected_outputs": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "File paths this step should produce."
                            }
                        },
                        "required": ["title", "description"]
                    }
                }
            },
            "required": ["goal", "steps"]
        },
        function=partial(execute_plan, chat_id=chat_id, http_client=http_client),
    ))
    
    return tools
