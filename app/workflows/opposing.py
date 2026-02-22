"""Opposing perspective workflow for dual-viewpoint analysis.

This workflow handles the 'opposing_perspective' reasoning pattern where two
agents with opposing viewpoints analyze the same question in parallel, then
present both perspectives to the user for selection or synthesis.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from models import WorkflowResult
from .base import WorkflowBase, WorkflowContext, AgentInvocation


# Opposing perspective prompts
PERSPECTIVE_A_PROMPT = """You are arguing FOR the following position. Present the strongest possible case.

Be persuasive but honest. Acknowledge weaknesses only briefly if they're critical.
Focus on benefits, advantages, and reasons why this is the better choice.

Position to argue FOR: {position_a}

Task context: {context}

Present your argument clearly and compellingly."""

PERSPECTIVE_B_PROMPT = """You are arguing AGAINST the following position (or FOR the alternative). Present the strongest possible case.

Be persuasive but honest. Acknowledge weaknesses only briefly if they're critical.
Focus on benefits of the alternative, risks of the first option, and reasons why the alternative is better.

Position to argue AGAINST: {position_a}
Alternative position: {position_b}

Task context: {context}

Present your argument clearly and compellingly."""

SYNTHESIS_PROMPT = """You are synthesizing two opposing perspectives into a balanced analysis.

## Perspective A (FOR {position_a}):
{perspective_a_response}

## Perspective B (FOR {position_b}):
{perspective_b_response}

## Task
Create a balanced synthesis that:
1. Acknowledges the strongest points from each perspective
2. Identifies where they agree and disagree
3. Highlights key trade-offs
4. If appropriate, suggests which perspective has stronger support given the context

Be objective and analytical. Do not pick a side unless the evidence clearly favors one."""


class OpposingPerspectiveWorkflow(WorkflowBase):
    """Opposing perspective workflow for dual-viewpoint analysis.
    
    Flow:
    1. Identify the two opposing positions from the query
    2. Spawn two agents in parallel with opposing viewpoints
    3. Present both perspectives to the user
    4. Optionally synthesize or let user choose
    """
    
    @property
    def name(self) -> str:
        return "opposing_perspective"
    
    @property
    def pattern(self) -> str:
        return "opposing_perspective"
    
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute opposing perspective workflow.
        
        Args:
            context: The workflow context
            
        Returns:
            WorkflowResult with perspectives and optional synthesis
        """
        await self.emit_progress("Analyzing query for opposing perspectives...")
        
        # Extract the two positions from the intent
        positions = await self._extract_positions(context)
        position_a = positions.get("position_a", "the proposed approach")
        position_b = positions.get("position_b", "the alternative approach")
        
        await self.emit_progress(
            f"Identified positions: '{position_a}' vs '{position_b}'",
            metadata={"positions": positions}
        )
        
        # Get agent config (use architecture for technical, general otherwise)
        agent_config = self.get_agent_config(context.category)
        model = agent_config.get("model", "google/gemini-3-flash-preview")
        system_prompt = agent_config.get("system_prompt", "")
        
        await self.emit_progress("Generating opposing perspectives in parallel...")
        
        # Build prompts for each perspective
        task_context = self.build_user_prompt(context)
        
        prompt_a = PERSPECTIVE_A_PROMPT.format(
            position_a=position_a,
            context=task_context,
        )
        
        prompt_b = PERSPECTIVE_B_PROMPT.format(
            position_a=position_a,
            position_b=position_b,
            context=task_context,
        )
        
        # Create invocations
        invocation_a = AgentInvocation(
            agent_name=f"{context.category}_perspective_a",
            model=model,
            system_prompt=system_prompt,
            user_prompt=prompt_a,
            perspective="for",
        )
        
        invocation_b = AgentInvocation(
            agent_name=f"{context.category}_perspective_b",
            model=model,
            system_prompt=system_prompt,
            user_prompt=prompt_b,
            perspective="against",
        )
        
        # Execute in parallel
        responses = await self.call_agents_parallel(
            [invocation_a, invocation_b],
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        perspective_a_response = responses[0]
        perspective_b_response = responses[1]
        
        await self.emit_progress("Both perspectives generated.")
        
        # Present perspectives to user for choice
        perspectives = [
            {
                "label": f"For: {position_a}",
                "summary": perspective_a_response[:200] + "...",
                "response": perspective_a_response,
            },
            {
                "label": f"For: {position_b}",
                "summary": perspective_b_response[:200] + "...",
                "response": perspective_b_response,
            },
        ]
        
        # Emit perspectives for user selection
        user_response = None
        if self.stream:
            user_response = await self.stream.emit_perspectives(
                perspectives,
                prompt="Two perspectives have been generated. How would you like to proceed?",
            )
        
        # Handle user selection
        if user_response:
            if user_response.selected_option_id == "perspective_0":
                return WorkflowResult(
                    success=True,
                    content=perspective_a_response,
                    raw_response=perspective_a_response,
                    agent_name=context.category,
                    model=model,
                    metadata={
                        "workflow": self.name,
                        "selected_perspective": "a",
                        "position": position_a,
                    },
                )
            elif user_response.selected_option_id == "perspective_1":
                return WorkflowResult(
                    success=True,
                    content=perspective_b_response,
                    raw_response=perspective_b_response,
                    agent_name=context.category,
                    model=model,
                    metadata={
                        "workflow": self.name,
                        "selected_perspective": "b",
                        "position": position_b,
                    },
                )
            # "both" selected - synthesize
        
        # Generate synthesis
        await self.emit_progress("Synthesizing perspectives...")
        
        synthesis_prompt = SYNTHESIS_PROMPT.format(
            position_a=position_a,
            position_b=position_b,
            perspective_a_response=perspective_a_response,
            perspective_b_response=perspective_b_response,
        )
        
        synthesis_invocation = AgentInvocation(
            agent_name=f"{context.category}_synthesizer",
            model=model,
            system_prompt=system_prompt,
            user_prompt=synthesis_prompt,
        )
        
        synthesis_response = await self.call_agent(
            synthesis_invocation,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Build final response with all perspectives
        final_content = f"""## Opposing Perspectives Analysis

### Position A: {position_a}
{perspective_a_response}

---

### Position B: {position_b}
{perspective_b_response}

---

### Synthesis
{synthesis_response}"""
        
        return WorkflowResult(
            success=True,
            content=final_content,
            raw_response=synthesis_response,
            agent_name=context.category,
            model=model,
            metadata={
                "workflow": self.name,
                "positions": positions,
                "perspective_a": perspective_a_response,
                "perspective_b": perspective_b_response,
                "synthesis": synthesis_response,
            },
        )
    
    async def _extract_positions(self, context: WorkflowContext) -> Dict[str, str]:
        """Extract the two opposing positions from the query.
        
        Uses a small model call to identify the positions if not obvious.
        """
        from categorization import call_openrouter
        
        extraction_prompt = f"""Analyze this query and identify the two opposing positions or options being considered.

Query: {context.condensed_intent}

Recent context:
{self.build_user_prompt(context)}

Return a JSON object with:
- "position_a": The first position/option (the one being proposed or asked about)
- "position_b": The opposing position/alternative

Example output:
{{"position_a": "using microservices architecture", "position_b": "using monolithic architecture"}}

Output ONLY the JSON object."""
        
        messages = [{"role": "user", "content": extraction_prompt}]
        result = await call_openrouter("google/gemini-3-flash-preview", messages)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Try to parse JSON
        import json
        try:
            # Clean the response
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            positions = json.loads(content)
            return positions
        except (json.JSONDecodeError, KeyError):
            # Fallback to generic positions
            return {
                "position_a": "the proposed approach",
                "position_b": "the alternative approach",
            }
