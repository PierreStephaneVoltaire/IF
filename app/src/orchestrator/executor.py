
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



@dataclass
class PlanStep:

    index: int
    title: str
    description: str
    expected_outputs: List[str] = field(default_factory=list)


@dataclass
class ExecutionPlan:

    goal: str
    context: str = ""
    steps: List[PlanStep] = field(default_factory=list)


@dataclass
class StepResult:

    step_index: int
    success: bool
    summary: str = ""
    files: List[FileRef] = field(default_factory=list)
    error: Optional[str] = None



@dataclass
class LLMResponse:

    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_message(self) -> Dict[str, Any]:

        if self.tool_calls:
            return {
                "role": "assistant",
                "content": self.content,
                "tool_calls": self.tool_calls
            }
        return {"role": "assistant", "content": self.content}


def parse_llm_response(data: Dict[str, Any]) -> LLMResponse:

    choices = data.get("choices", [])
    if not choices:
        return LLMResponse()
    
    choice = choices[0]
    message = choice.get("message", {})
    
    content = message.get("content", "") or ""
    tool_calls = []
    
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



async def call_openrouter(
    model: str,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    http_client: Optional[httpx.AsyncClient] = None,
) -> LLMResponse:

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
                content = response.content or ""
                cleaned, files = strip_files_line(content)
                
                return StepResult(
                    step_index=0,
                    success=True,
                    summary=cleaned[:500],
                    files=files,
                    error=None,
                )
        
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

    from agent.tools.terminal_tools import terminal_execute
    
    try:
        return await terminal_execute(
            command=command,
            workdir=workdir,
            chat_id=chat_id,
        )
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

def build_subagent_prompt(
    plan: ExecutionPlan,
    step: PlanStep,
    previous: List[StepResult],
) -> str:

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

def parse_plan(goal: str, context: str, steps: List[Dict[str, Any]]) -> ExecutionPlan:

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
            
            result.step_index = step.index
            results.append(result)
            
            if not result.success:
                logger.warning(f"[Orchestrator] Step {step.index} failed: {result.error}")
                break
            
            logger.info(f"[Orchestrator] Step {step.index} completed: {result.summary[:100]}")
        
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



def get_orchestrator_tools(
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> List[Tool]:

    from functools import partial
    
    tools = []
    
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
