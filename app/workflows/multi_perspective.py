"""Multi-perspective workflow for comprehensive analysis.

This workflow handles the 'multi_perspective' reasoning pattern where multiple
agents with different perspectives analyze the same question in parallel,
then aggregate the results into a multifaceted response.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from models import WorkflowResult
from .base import WorkflowBase, WorkflowContext, AgentInvocation


# Default perspectives for different categories
DEFAULT_PERSPECTIVES = {
    "architecture": [
        {"name": "security", "focus": "security implications, vulnerabilities, and hardening"},
        {"name": "scalability", "focus": "scalability, performance, and capacity planning"},
        {"name": "cost", "focus": "cost implications, FinOps, and resource optimization"},
        {"name": "maintainability", "focus": "maintainability, technical debt, and long-term sustainability"},
    ],
    "coding": [
        {"name": "correctness", "focus": "correctness, edge cases, and error handling"},
        {"name": "performance", "focus": "performance, efficiency, and optimization"},
        {"name": "readability", "focus": "readability, maintainability, and code quality"},
    ],
    "financial": [
        {"name": "risk", "focus": "risk assessment and downside protection"},
        {"name": "growth", "focus": "growth potential and upside opportunities"},
        {"name": "tax", "focus": "tax implications and efficiency"},
    ],
    "health": [
        {"name": "evidence", "focus": "evidence-based recommendations and research"},
        {"name": "practical", "focus": "practical implementation and adherence"},
        {"name": "safety", "focus": "safety, contraindications, and risk factors"},
    ],
    "general": [
        {"name": "analytical", "focus": "logical analysis and objective evaluation"},
        {"name": "practical", "focus": "practical considerations and feasibility"},
        {"name": "long_term", "focus": "long-term implications and consequences"},
    ],
}

PERSPECTIVE_PROMPT = """You are analyzing this question from the perspective of {perspective_name}.

Your focus: {perspective_focus}

Analyze ONLY from this perspective. Be thorough but stay focused on your assigned angle.
Other perspectives will be covered by other analysts.

Task: {task}

Context:
{context}

Provide your {perspective_name}-focused analysis."""

AGGREGATION_PROMPT = """You are synthesizing multiple expert perspectives into a comprehensive analysis.

## Perspectives Received:

{perspectives_content}

## Task
Create a unified analysis that:
1. Presents each perspective's key insights clearly
2. Identifies areas of agreement and tension between perspectives
3. Highlights trade-offs that emerge from the multi-faceted analysis
4. Provides a balanced recommendation that considers all perspectives

Do not favor any single perspective. Present a genuinely multifaceted view."""


class MultiPerspectiveWorkflow(WorkflowBase):
    """Multi-perspective workflow for comprehensive analysis.
    
    Flow:
    1. Determine relevant perspectives for the category
    2. Spawn multiple agents in parallel, each with a different perspective
    3. Aggregate results using a synthesizer agent
    4. Optionally let user weight or select perspectives
    """
    
    @property
    def name(self) -> str:
        return "multi_perspective"
    
    @property
    def pattern(self) -> str:
        return "multi_perspective"
    
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute multi-perspective workflow.
        
        Args:
            context: The workflow context
            
        Returns:
            WorkflowResult with aggregated perspectives
        """
        await self.emit_progress("Determining relevant perspectives...")
        
        # Get perspectives for this category
        perspectives = self._get_perspectives_for_category(context.category)
        perspective_names = [p["name"] for p in perspectives]
        
        await self.emit_progress(
            f"Analyzing from {len(perspectives)} perspectives: {', '.join(perspective_names)}",
            metadata={"perspectives": perspectives}
        )
        
        # Get agent config
        agent_config = self.get_agent_config(context.category)
        model = agent_config.get("model", "google/gemini-3-flash-preview")
        system_prompt = agent_config.get("system_prompt", "")
        
        # Build task context
        task_context = self.build_user_prompt(context)
        
        # Create invocations for each perspective
        invocations = []
        for perspective in perspectives:
            prompt = PERSPECTIVE_PROMPT.format(
                perspective_name=perspective["name"],
                perspective_focus=perspective["focus"],
                task=context.condensed_intent,
                context=task_context,
            )
            
            invocations.append(AgentInvocation(
                agent_name=f"{context.category}_{perspective['name']}",
                model=model,
                system_prompt=system_prompt,
                user_prompt=prompt,
                perspective=perspective["name"],
                metadata={"focus": perspective["focus"]},
            ))
        
        await self.emit_progress("Generating perspectives in parallel...")
        
        # Execute all perspectives in parallel
        responses = await self.call_agents_parallel(
            invocations,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Build perspectives content for aggregation
        perspective_results = []
        perspectives_content = ""
        for i, (perspective, response) in enumerate(zip(perspectives, responses)):
            perspectives_content += f"""### {perspective['name'].title()} Perspective
Focus: {perspective['focus']}

{response}

---

"""
            perspective_results.append({
                "name": perspective["name"],
                "focus": perspective["focus"],
                "response": response,
            })
        
        await self.emit_progress("All perspectives generated. Aggregating...")
        
        # Present perspectives for user review (optional)
        if self.stream:
            perspective_options = [
                {
                    "label": p["name"].title(),
                    "summary": p["response"][:150] + "...",
                    "response": p["response"],
                }
                for p in perspective_results
            ]
            
            await self.stream.emit_progress(
                "Multiple perspectives generated. Proceeding with synthesis...",
                metadata={"perspectives": perspective_options}
            )
        
        # Aggregate perspectives
        aggregation_prompt = AGGREGATION_PROMPT.format(
            perspectives_content=perspectives_content
        )
        
        aggregation_invocation = AgentInvocation(
            agent_name=f"{context.category}_aggregator",
            model=model,
            system_prompt=system_prompt,
            user_prompt=aggregation_prompt,
        )
        
        aggregated_response = await self.call_agent(
            aggregation_invocation,
            inject_directives_for=(context.category, context.reasoning_pattern),
        )
        
        # Build final response
        final_content = f"""## Multi-Perspective Analysis

{perspectives_content}

## Synthesis

{aggregated_response}"""
        
        return WorkflowResult(
            success=True,
            content=final_content,
            raw_response=aggregated_response,
            agent_name=context.category,
            model=model,
            metadata={
                "workflow": self.name,
                "perspectives": perspective_results,
                "aggregation": aggregated_response,
            },
        )
    
    def _get_perspectives_for_category(self, category: str) -> List[Dict[str, str]]:
        """Get the relevant perspectives for a category.
        
        Args:
            category: The task category
            
        Returns:
            List of perspective configurations
        """
        return DEFAULT_PERSPECTIVES.get(category, DEFAULT_PERSPECTIVES["general"])
    
    async def execute_with_custom_perspectives(
        self,
        context: WorkflowContext,
        perspectives: List[Dict[str, str]],
    ) -> WorkflowResult:
        """Execute with custom perspectives.
        
        Args:
            context: The workflow context
            perspectives: Custom perspectives to use
            
        Returns:
            WorkflowResult with aggregated perspectives
        """
        # Store original perspectives and use custom ones
        original_perspectives = DEFAULT_PERSPECTIVES.get(context.category, [])
        DEFAULT_PERSPECTIVES[context.category] = perspectives
        
        try:
            return await self.execute(context)
        finally:
            # Restore original perspectives
            DEFAULT_PERSPECTIVES[context.category] = original_perspectives
