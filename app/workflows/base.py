"""Base workflow class for reasoning patterns.

This module provides the abstract base class for all workflow implementations.
Each workflow handles a specific reasoning pattern (simple, opposing, multi-perspective, research).
"""
from __future__ import annotations
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from models import WorkflowResult
from directive_injector import inject_directives
from categorization import call_openrouter, normalize_message


@dataclass
class WorkflowContext:
    """Context for workflow execution."""
    messages: List[Dict[str, Any]]
    category: str
    reasoning_pattern: str
    condensed_intent: str
    applicable_directives: List[str]
    chat_id: str  # Required - moved before optional fields
    sandbox_dir: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentInvocation:
    """Represents an agent invocation with its configuration."""
    agent_name: str
    model: str
    system_prompt: str
    user_prompt: str
    perspective: Optional[str] = None  # For multi-perspective workflows
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowBase(ABC):
    """Abstract base class for reasoning pattern workflows.
    
    Each workflow implementation handles a specific reasoning pattern:
    - SimpleWorkflow: Direct execution with single agent
    - OpposingWorkflow: Two parallel agents with opposing viewpoints
    - MultiPerspectiveWorkflow: Multiple agents with aggregation
    - ResearchWorkflow: Research-first approach with domain agent
    """
    
    def __init__(self, stream: Optional["ConversationStream"] = None):
        self.stream = stream
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of this workflow."""
        pass
    
    @property
    @abstractmethod
    def pattern(self) -> str:
        """The reasoning pattern this workflow handles."""
        pass
    
    @abstractmethod
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute the workflow.
        
        Args:
            context: The workflow context with all necessary information
            
        Returns:
            WorkflowResult with the final response
        """
        pass
    
    async def emit_progress(self, message: str, metadata: Optional[Dict] = None) -> None:
        """Emit a progress update to the stream."""
        if self.stream:
            await self.stream.emit_progress(message, metadata)
    
    async def emit_options(
        self,
        prompt: str,
        options: List[Dict[str, str]],
    ) -> Optional[Any]:
        """Present options to the user and wait for selection."""
        if self.stream:
            from streaming import AgentOption
            agent_options = [
                AgentOption(
                    id=opt["id"],
                    label=opt["label"],
                    description=opt.get("description", ""),
                )
                for opt in options
            ]
            return await self.stream.emit_options(prompt, agent_options)
        return None
    
    async def call_agent(
        self,
        invocation: AgentInvocation,
        inject_directives_for: Optional[tuple] = None,
    ) -> str:
        """Call an agent with the given configuration.
        
        Args:
            invocation: The agent invocation details
            inject_directives_for: Optional (category, pattern) tuple to inject directives
            
        Returns:
            The agent's response content
        """
        system_prompt = invocation.system_prompt
        
        # Inject directives if requested
        if inject_directives_for:
            category, pattern = inject_directives_for
            system_prompt = inject_directives(category, pattern, system_prompt)
        
        messages = [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": invocation.user_prompt},
        ]
        
        result = await call_openrouter(invocation.model, messages)
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        return content
    
    async def call_agent_with_tools(
        self,
        invocation: AgentInvocation,
        sandbox_dir: str,
        inject_directives_for: Optional[tuple] = None,
    ) -> "AgentResult":
        """Call an agent with actual tool execution via OpenHands SDK.
        
        This method creates an AgentExecutor that uses real tools
        (file_editor, terminal) instead of just text completions.
        
        Args:
            invocation: The agent invocation details
            sandbox_dir: Directory for file operations
            inject_directives_for: Optional (category, pattern) tuple to inject directives
            
        Returns:
            AgentResult with content, tool calls, files modified, etc.
        """
        from .agent_executor import AgentExecutor
        
        system_prompt = invocation.system_prompt
        
        # Inject directives if requested
        if inject_directives_for:
            category, pattern = inject_directives_for
            system_prompt = inject_directives(category, pattern, system_prompt)
        
        # Get full agent config
        config = self.get_agent_config(invocation.agent_name)
        
        # Override model and system prompt from invocation if provided
        if invocation.model:
            config["model"] = invocation.model
        config["system_prompt"] = system_prompt
        
        # Create executor with tools
        executor = AgentExecutor(
            config=config,
            sandbox_dir=sandbox_dir,
            stream=self.stream,
        )
        
        # Execute with tool support
        result = await executor.execute(invocation.user_prompt)
        
        return result
    
    async def call_agents_parallel(
        self,
        invocations: List[AgentInvocation],
        inject_directives_for: Optional[tuple] = None,
    ) -> List[str]:
        """Call multiple agents in parallel.
        
        Args:
            invocations: List of agent invocations
            inject_directives_for: Optional (category, pattern) tuple to inject directives
            
        Returns:
            List of agent response contents
        """
        tasks = [
            self.call_agent(invocation, inject_directives_for)
            for invocation in invocations
        ]
        return await asyncio.gather(*tasks)
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Load agent configuration by name.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Agent configuration dictionary
        """
        from agents import load_agent_config, load_sub_agent_config
        
        try:
            return load_agent_config(agent_name)
        except FileNotFoundError:
            return load_sub_agent_config(agent_name)
    
    def build_user_prompt(
        self,
        context: WorkflowContext,
        additional_context: str = "",
    ) -> str:
        """Build the user prompt for an agent.
        
        Args:
            context: The workflow context
            additional_context: Any additional context to include
            
        Returns:
            Formatted user prompt
        """
        prompt = f"""## Task
{context.condensed_intent}

## Category
{context.category}

## Reasoning Pattern
{context.reasoning_pattern}
"""
        
        if additional_context:
            prompt += f"\n## Additional Context\n{additional_context}\n"
        
        # Add recent messages for context
        prompt += "\n## Recent Conversation\n"
        for msg in context.messages[-5:]:
            # Normalize message (handles both dict and LangChain message objects)
            normalized_msg = normalize_message(msg)
            role = normalized_msg.get("role", "unknown").upper()
            content = normalized_msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
            prompt += f"**{role}**: {content[:500]}\n"
        
        return prompt
