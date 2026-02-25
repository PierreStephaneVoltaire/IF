"""Simple workflow for direct agent execution.

This workflow handles the 'simple' reasoning pattern where a single agent
directly handles the request, optionally spawning sub-agents or using tools.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from models import WorkflowResult
from .base import WorkflowBase, WorkflowContext, AgentInvocation
from persistence import (
    PersistenceManager,
    ExecutionPlan as PersistedPlan,
    PlanStep as PersistedStep,
    StepEvaluation,
)


# Maximum refinement iterations before accepting
MAX_REFINEMENT_ITERATIONS = 3


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    step_number: int
    description: str
    files_to_create: List[str] = field(default_factory=list)
    files_to_modify: List[str] = field(default_factory=list)
    acceptance_criteria: List[str] = field(default_factory=list)
    dependencies: List[int] = field(default_factory=list)
    estimated_complexity: str = "medium"
    status: str = "pending"


@dataclass
class ExecutionPlan:
    """Full execution plan for a coding task."""
    task_summary: str
    steps: List[PlanStep]
    estimated_total_steps: int
    potential_challenges: List[str] = field(default_factory=list)


@dataclass
class StepResult:
    """Result from executing a plan step."""
    step_number: int
    approved: bool
    content: str
    files_modified: List[str] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    evaluation: Optional[Dict[str, Any]] = None


class WorkflowStoppedException(Exception):
    """Raised when user stops the workflow."""
    pass


class SimpleWorkflow(WorkflowBase):
    """Simple workflow for direct agent execution.
    
    Flow:
    1. Select appropriate agent based on category
    2. Build prompt with context and directives
    3. Execute agent
    4. Return response (to be personalized by main orchestrator)
    """
    
    @property
    def name(self) -> str:
        return "simple"
    
    @property
    def pattern(self) -> str:
        return "simple"
    
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute simple workflow.
        
        Args:
            context: The workflow context
            
        Returns:
            WorkflowResult with the agent's response
        """
        await self.emit_progress("Selecting appropriate agent...")
        
        # Get agent config for the category
        agent_config = self.get_agent_config(context.category)
        agent_name = agent_config.get("name", context.category)
        model = agent_config.get("model", "google/gemini-3-flash-preview")
        system_prompt = agent_config.get("system_prompt", "")
        
        await self.emit_progress(f"Executing {agent_name} agent...")
        
        # Build the user prompt
        user_prompt = self.build_user_prompt(context)
        
        # Create invocation
        invocation = AgentInvocation(
            agent_name=agent_name,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        
        # Execute with directive injection
        response = await self.call_agent(
            invocation,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        await self.emit_progress("Agent execution complete.")
        
        return WorkflowResult(
            success=True,
            content=response,
            raw_response=response,
            agent_name=agent_name,
            model=model,
            metadata={
                "workflow": self.name,
                "category": context.category,
            },
        )


class SequentialRefinementWorkflow(WorkflowBase):
    """Sequential refinement workflow for iterative tasks.
    
    This implements a true agentic loop with:
    1. Planner creates step-by-step JSON plan
    2. User checkpoint to approve/reject plan
    3. For each step:
       a. Executor implements with real tools (file_editor, terminal)
       b. Evaluator reviews against acceptance criteria
       c. User checkpoint to approve/request changes/stop
       d. Refinement loop if issues found
    4. Combined response with files modified
    """
    
    @property
    def name(self) -> str:
        return "sequential_refinement"
    
    @property
    def pattern(self) -> str:
        return "sequential_refinement"
    
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute sequential refinement workflow.
        
        For coding tasks, this uses the planner-executor-evaluator loop.
        For other tasks, it behaves like simple workflow.
        """
        if context.category == "coding":
            return await self._execute_coding_workflow(context)
        else:
            # Fall back to simple execution
            simple = SimpleWorkflow(self.stream)
            return await simple.execute(context)
    
    async def _execute_coding_workflow(
        self,
        context: WorkflowContext,
    ) -> WorkflowResult:
        """Execute the full coding agentic workflow."""
        
        if not context.sandbox_dir:
            raise ValueError("Sandbox directory required for coding workflow")
        
        await self.emit_progress("Starting coding workflow with agentic loop...")
        
        # Initialize persistence manager
        persistence = PersistenceManager(context.sandbox_dir)
        persistence.initialize()
        
        # Phase 1: Create plan
        plan = await self._create_plan(context)
        
        # Save plan to persistence
        self._save_plan_to_persistence(plan, persistence)
        
        # Phase 2: Plan checkpoint
        plan_approved = await self._checkpoint_plan(plan, context)
        if not plan_approved:
            return await self._handle_plan_rejection(plan, context)
        
        # Phase 3: Execute steps with refinement loops
        step_results: List[StepResult] = []
        all_files_modified: List[str] = []
        step_statuses: Dict[int, str] = {}
        
        for step in plan.steps:
            # Update current step in persistence
            persistence.save_current_step(step.step_number)
            step_statuses[step.step_number] = "in_progress"
            persistence.save_step_status(step_statuses)
            
            try:
                step_result = await self._execute_step_with_refinement(
                    step, plan, context
                )
                step_results.append(step_result)
                all_files_modified.extend(step_result.files_modified)
                
                # Update step status
                step_statuses[step.step_number] = "approved" if step_result.approved else "completed_with_issues"
                persistence.save_step_status(step_statuses)
                
                # Save evaluation if present
                if step_result.evaluation:
                    self._save_evaluation_to_persistence(
                        step.step_number, step_result.evaluation, persistence
                    )
                    
            except WorkflowStoppedException:
                step_statuses[step.step_number] = "stopped"
                persistence.save_step_status(step_statuses)
                await self.emit_progress("Workflow stopped by user.")
                break
        
        # Phase 4: Generate combined response
        return await self._build_final_response(
            plan, step_results, all_files_modified, context
        )
    
    async def _create_plan(self, context: WorkflowContext) -> ExecutionPlan:
        """Create execution plan using planner agent."""
        await self.emit_progress("Creating execution plan...")
        
        planner_config = self.get_agent_config("planner")
        
        planner_prompt = f"""Create a detailed step-by-step plan for this coding task.

Task: {context.condensed_intent}

Requirements:
1. Break down into atomic, testable steps
2. Each step should have clear acceptance criteria
3. Identify file dependencies
4. Estimate complexity (low/medium/high)

Output a JSON plan with this structure:
{{
  "task_summary": "Brief description",
  "steps": [
    {{
      "step_number": 1,
      "description": "What this step accomplishes",
      "files_to_create": ["list of files"],
      "files_to_modify": ["list of files"],
      "acceptance_criteria": ["criteria list"],
      "dependencies": [],
      "estimated_complexity": "low|medium|high"
    }}
  ],
  "estimated_total_steps": N,
  "potential_challenges": ["list"]
}}

Output ONLY valid JSON, no markdown code blocks."""
        
        invocation = AgentInvocation(
            agent_name="planner",
            model=planner_config.get("model", "anthropic/claude-sonnet-4.6"),
            system_prompt=planner_config.get("system_prompt", ""),
            user_prompt=planner_prompt,
        )
        
        plan_response = await self.call_agent(
            invocation,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Parse plan JSON
        try:
            plan_data = self._extract_json(plan_response)
            steps = [
                PlanStep(
                    step_number=s.get("step_number", i+1),
                    description=s.get("description", ""),
                    files_to_create=s.get("files_to_create", []),
                    files_to_modify=s.get("files_to_modify", []),
                    acceptance_criteria=s.get("acceptance_criteria", []),
                    dependencies=s.get("dependencies", []),
                    estimated_complexity=s.get("estimated_complexity", "medium"),
                )
                for i, s in enumerate(plan_data.get("steps", []))
            ]
            
            plan = ExecutionPlan(
                task_summary=plan_data.get("task_summary", context.condensed_intent),
                steps=steps,
                estimated_total_steps=plan_data.get("estimated_total_steps", len(steps)),
                potential_challenges=plan_data.get("potential_challenges", []),
            )
            
            await self.emit_progress(
                f"Plan created with {len(steps)} steps",
                metadata={"steps": [s.description for s in steps]}
            )
            
            return plan
            
        except (json.JSONDecodeError, KeyError) as e:
            await self.emit_progress(f"Plan parsing failed, using default plan: {e}")
            # Fallback to single-step plan
            return ExecutionPlan(
                task_summary=context.condensed_intent,
                steps=[PlanStep(
                    step_number=1,
                    description=context.condensed_intent,
                    acceptance_criteria=["Complete implementation"],
                )],
                estimated_total_steps=1,
            )
    
    async def _checkpoint_plan(
        self,
        plan: ExecutionPlan,
        context: WorkflowContext,
    ) -> bool:
        """Present plan to user for approval."""
        
        if not self.stream:
            # Non-streaming mode: auto-approve
            return True
        
        plan_summary = f"Plan: {plan.task_summary}\n\nSteps:\n"
        for step in plan.steps:
            plan_summary += f"  {step.step_number}. {step.description}\n"
            if step.files_to_create:
                plan_summary += f"     Create: {', '.join(step.files_to_create)}\n"
            if step.files_to_modify:
                plan_summary += f"     Modify: {', '.join(step.files_to_modify)}\n"
        
        user_response = await self.emit_options(
            prompt=plan_summary,
            options=[
                {
                    "id": "approve",
                    "label": "Approve Plan",
                    "description": "Start executing the plan step by step",
                },
                {
                    "id": "modify",
                    "label": "Request Changes",
                    "description": "Ask for plan modifications before proceeding",
                },
                {
                    "id": "reject",
                    "label": "Cancel Workflow",
                    "description": "Stop the workflow entirely",
                },
            ],
        )
        
        if not user_response:
            return True  # No stream, auto-approve
        
        if user_response.selected_option_id == "approve":
            return True
        elif user_response.selected_option_id == "modify":
            # TODO: Handle plan modification
            return True
        else:
            return False
    
    async def _handle_plan_rejection(
        self,
        plan: ExecutionPlan,
        context: WorkflowContext,
    ) -> WorkflowResult:
        """Handle when user rejects the plan."""
        return WorkflowResult(
            success=False,
            content="Workflow cancelled by user during plan review.",
            raw_response="",
            agent_name="planner",
            model="",
            metadata={"cancelled": True, "plan": plan.task_summary},
        )
    
    async def _execute_step_with_refinement(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        context: WorkflowContext,
    ) -> StepResult:
        """Execute a step with refinement loop."""
        
        await self.emit_progress(
            f"Step {step.step_number}/{len(plan.steps)}: {step.description}"
        )
        
        # First execution
        result = await self._execute_step(step, plan, context)
        
        # Refinement loop if not approved
        iterations = 0
        while not result.approved and iterations < MAX_REFINEMENT_ITERATIONS:
            iterations += 1
            await self.emit_progress(
                f"Refining step {step.step_number} (iteration {iterations})...",
                metadata={"issues": result.issues}
            )
            result = await self._refine_step(step, plan, result.issues, context)
        
        return result
    
    async def _execute_step(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        context: WorkflowContext,
    ) -> StepResult:
        """Execute a single step with tools and evaluation."""
        
        # Execute with tools
        executor_config = self.get_agent_config("executor")
        
        step_prompt = f"""Execute step {step.step_number} of the plan.

## Step Description
{step.description}

## Files to Create
{json.dumps(step.files_to_create, indent=2) if step.files_to_create else 'None specified'}

## Files to Modify
{json.dumps(step.files_to_modify, indent=2) if step.files_to_modify else 'None specified'}

## Acceptance Criteria
{chr(10).join(f'- {c}' for c in step.acceptance_criteria)}

## Overall Task Context
{plan.task_summary}

## Instructions
1. Implement this step completely
2. Write files to the sandbox directory
3. Ensure all acceptance criteria are met
4. Do NOT include code in response - write to files
"""
        
        invocation = AgentInvocation(
            agent_name="executor",
            model=executor_config.get("model", "openai/gpt-5.3-codex"),
            system_prompt=executor_config.get("system_prompt", ""),
            user_prompt=step_prompt,
        )
        
        # Execute with real tools
        execution_result = await self.call_agent_with_tools(
            invocation,
            sandbox_dir=context.sandbox_dir,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Evaluate the implementation
        evaluation = await self._evaluate_step(step, execution_result, context)
        
        # Checkpoint: Present to user
        user_response = await self._step_checkpoint(step, evaluation, execution_result)
        
        if user_response == "approve":
            return StepResult(
                step_number=step.step_number,
                approved=True,
                content=execution_result.content,
                files_modified=execution_result.files_modified,
                evaluation=evaluation,
            )
        elif user_response == "stop":
            raise WorkflowStoppedException()
        else:
            return StepResult(
                step_number=step.step_number,
                approved=False,
                content=execution_result.content,
                files_modified=execution_result.files_modified,
                issues=evaluation.get("issues_found", []),
                evaluation=evaluation,
            )
    
    async def _evaluate_step(
        self,
        step: PlanStep,
        execution_result: Any,
        context: WorkflowContext,
    ) -> Dict[str, Any]:
        """Evaluate step implementation against acceptance criteria."""
        
        await self.emit_progress(f"Evaluating step {step.step_number}...")
        
        evaluator_config = self.get_agent_config("evaluator")
        
        eval_prompt = f"""Evaluate the implementation for step {step.step_number}.

## Step Description
{step.description}

## Acceptance Criteria
{chr(10).join(f'- {c}' for c in step.acceptance_criteria)}

## Files Modified
{json.dumps(execution_result.files_modified, indent=2)}

## Tool Calls Made
{json.dumps(execution_result.tool_calls, indent=2)}

## Executor Response
{execution_result.content[:2000]}

## Instructions
1. Check each acceptance criterion
2. Identify any issues or missing requirements
3. Provide actionable feedback if changes needed

Output JSON:
{{
  "status": "approved" | "needs_revision",
  "criteria_results": [{{"criterion": "...", "passed": true/false}}],
  "issues_found": [{{"severity": "critical|major|minor", "description": "...", "suggested_fix": "..."}}],
  "overall_assessment": "...",
  "recommendations": ["..."]
}}

Output ONLY valid JSON."""
        
        invocation = AgentInvocation(
            agent_name="evaluator",
            model=evaluator_config.get("model", "anthropic/claude-sonnet-4.6"),
            system_prompt=evaluator_config.get("system_prompt", ""),
            user_prompt=eval_prompt,
        )
        
        eval_response = await self.call_agent(
            invocation,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        try:
            return self._extract_json(eval_response)
        except json.JSONDecodeError:
            return {
                "status": "approved",
                "overall_assessment": "Could not parse evaluation, proceeding.",
                "issues_found": [],
            }
    
    async def _step_checkpoint(
        self,
        step: PlanStep,
        evaluation: Dict[str, Any],
        execution_result: Any,
    ) -> str:
        """Present step result to user for decision."""
        
        if not self.stream:
            # Non-streaming: auto-approve if no critical issues
            issues = evaluation.get("issues_found", [])
            critical = [i for i in issues if i.get("severity") == "critical"]
            return "stop" if critical else "approve"
        
        status = evaluation.get("status", "approved")
        assessment = evaluation.get("overall_assessment", "Step completed.")
        files = execution_result.files_modified
        
        prompt = f"""Step {step.step_number}: {step.description}

Status: {status.upper()}

{assessment}

Files modified: {len(files)}
{chr(10).join(f'  - {f}' for f in files[:5])}

How would you like to proceed?"""
        
        user_response = await self.emit_options(
            prompt=prompt,
            options=[
                {
                    "id": "approve",
                    "label": "Approve & Continue",
                    "description": "Proceed to next step",
                },
                {
                    "id": "refine",
                    "label": "Request Changes",
                    "description": "Ask for improvements on this step",
                },
                {
                    "id": "stop",
                    "label": "Stop Workflow",
                    "description": "End the workflow here",
                },
            ],
        )
        
        if not user_response:
            return "approve"  # Auto-approve if no stream
        
        return user_response.selected_option_id
    
    async def _refine_step(
        self,
        step: PlanStep,
        plan: ExecutionPlan,
        issues: List[Dict[str, Any]],
        context: WorkflowContext,
    ) -> StepResult:
        """Refine step based on identified issues."""
        
        executor_config = self.get_agent_config("executor")
        
        refinement_prompt = f"""Refine the implementation for step {step.step_number}.

## Previous Issues Found
{json.dumps(issues, indent=2)}

## Original Step Description
{step.description}

## Acceptance Criteria
{chr(10).join(f'- {c}' for c in step.acceptance_criteria)}

## Instructions
1. Address each issue identified
2. Maintain any correct parts of the implementation
3. Ensure all acceptance criteria are now met
4. Write updated files to sandbox
"""
        
        invocation = AgentInvocation(
            agent_name="executor",
            model=executor_config.get("model", "openai/gpt-5.3-codex"),
            system_prompt=executor_config.get("system_prompt", ""),
            user_prompt=refinement_prompt,
        )
        
        execution_result = await self.call_agent_with_tools(
            invocation,
            sandbox_dir=context.sandbox_dir,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Re-evaluate
        evaluation = await self._evaluate_step(step, execution_result, context)
        
        # Checkpoint
        user_response = await self._step_checkpoint(step, evaluation, execution_result)
        
        if user_response == "approve":
            return StepResult(
                step_number=step.step_number,
                approved=True,
                content=execution_result.content,
                files_modified=execution_result.files_modified,
                evaluation=evaluation,
            )
        elif user_response == "stop":
            raise WorkflowStoppedException()
        else:
            return StepResult(
                step_number=step.step_number,
                approved=False,
                content=execution_result.content,
                files_modified=execution_result.files_modified,
                issues=evaluation.get("issues_found", []),
                evaluation=evaluation,
            )
    
    async def _build_final_response(
        self,
        plan: ExecutionPlan,
        step_results: List[StepResult],
        all_files_modified: List[str],
        context: WorkflowContext,
    ) -> WorkflowResult:
        """Build the final combined response."""
        
        await self.emit_progress("Building final response...")
        
        # Build summary
        summary = f"## Task: {plan.task_summary}\n\n"
        summary += f"### Completed Steps: {len(step_results)}/{len(plan.steps)}\n\n"
        
        for result in step_results:
            status = "[DONE]" if result.approved else "[PARTIAL]"
            summary += f"{status} Step {result.step_number}: {result.evaluation.get('overall_assessment', 'Completed') if result.evaluation else 'Completed'}\n"
        
        summary += f"\n### Files Modified\n"
        for f in all_files_modified:
            summary += f"- {f}\n"
        
        # Build attachments
        attachments = []
        if context.sandbox_dir:
            for file_path in all_files_modified:
                import os
                full_path = os.path.join(context.sandbox_dir, file_path)
                if os.path.exists(full_path):
                    try:
                        with open(full_path, "r") as f:
                            content = f.read()
                        attachments.append({
                            "path": file_path,
                            "content": content,
                            "size": len(content),
                        })
                    except Exception:
                        pass
        
        return WorkflowResult(
            success=True,
            content=summary,
            raw_response=summary,
            agent_name="coding",
            model="multi-agent",
            attachments=attachments,
            metadata={
                "workflow": self.name,
                "plan": plan.task_summary,
                "steps_completed": len(step_results),
                "steps_total": len(plan.steps),
                "files_modified": all_files_modified,
            },
        )
    
    def _save_plan_to_persistence(
        self,
        plan: ExecutionPlan,
        persistence: PersistenceManager,
    ) -> None:
        """Save execution plan to persistence."""
        now = datetime.utcnow().isoformat()
        
        persisted_steps = [
            PersistedStep(
                step_number=s.step_number,
                description=s.description,
                files_to_create=s.files_to_create,
                files_to_modify=s.files_to_modify,
                acceptance_criteria=s.acceptance_criteria,
                dependencies=s.dependencies,
                estimated_complexity=s.estimated_complexity,
                status=s.status,
            )
            for s in plan.steps
        ]
        
        persisted_plan = PersistedPlan(
            task_summary=plan.task_summary,
            steps=persisted_steps,
            estimated_total_steps=plan.estimated_total_steps,
            potential_challenges=plan.potential_challenges,
            created_at=now,
            updated_at=now,
        )
        
        persistence.save_plan(persisted_plan)
    
    def _save_evaluation_to_persistence(
        self,
        step_number: int,
        evaluation: Dict[str, Any],
        persistence: PersistenceManager,
    ) -> None:
        """Save step evaluation to persistence."""
        step_eval = StepEvaluation(
            step_number=step_number,
            status=evaluation.get("status", "unknown"),
            criteria_results=evaluation.get("criteria_results", []),
            issues_found=evaluation.get("issues_found", []),
            overall_assessment=evaluation.get("overall_assessment", ""),
            recommendations=evaluation.get("recommendations", []),
            evaluated_at=datetime.utcnow().isoformat(),
        )
        
        persistence.save_evaluation(step_eval)
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text that may have markdown code blocks."""
        text = text.strip()
        
        # Remove markdown code blocks
        if "```" in text:
            lines = text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            text = "\n".join(json_lines)
        
        # Find JSON object
        start = text.find("{")
        if start == -1:
            raise json.JSONDecodeError("No JSON object found", text, 0)
        
        # Find matching closing brace
        depth = 0
        end = start
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        
        json_str = text[start:end]
        return json.loads(json_str)
