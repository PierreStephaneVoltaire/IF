"""Agent Executor with OpenHands SDK tool support.

This module provides the AgentExecutor class that wraps OpenHands SDK
to execute agents with actual tool support (file_editor, terminal).
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from streaming import ConversationStream

from openhands.sdk import LLM, Agent
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


@dataclass
class AgentResult:
    """Result from agent execution."""
    content: str
    success: bool
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentExecutor:
    """Execute agents with real tool support via OpenHands SDK.
    
    This class wraps the OpenHands SDK Agent to provide:
    - File editing capabilities via FileEditorTool
    - Terminal/command execution via TerminalTool
    - Progress streaming to the conversation stream
    - Result aggregation with file/command tracking
    
    Usage:
        executor = AgentExecutor(config, sandbox_dir, stream)
        result = await executor.execute(task_prompt)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        sandbox_dir: str,
        stream: Optional["ConversationStream"] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize the AgentExecutor.
        
        Args:
            config: Agent configuration dictionary (from JSON config)
            sandbox_dir: Directory for file operations
            stream: Optional ConversationStream for progress updates
            api_key: Optional API key (defaults to OPENROUTER_API_KEY env var)
        """
        self.config = config
        self.sandbox_dir = sandbox_dir
        self.stream = stream
        self.api_key = api_key or OPENROUTER_API_KEY
        
        # Build components
        self.llm = self._build_llm()
        self.tools = self._build_tools()
        self.agent = self._build_agent()
        
        # Tracking
        self._tool_calls: List[Dict[str, Any]] = []
        self._files_modified: List[str] = []
        self._commands_run: List[str] = []
    
    def _build_llm(self) -> LLM:
        """Build LLM instance from config."""
        model = self.config.get("model", "google/gemini-3-flash-preview")
        temperature = self.config.get("temperature", 0.7)
        
        # OpenRouter uses different API format
        # The OpenHands SDK should handle this via the model string
        return LLM(
            model=model,
            temperature=temperature,
            api_key=self.api_key,
        )
    
    def _build_tools(self) -> List:
        """Build tool instances from config.
        
        Supports:
        - file_editor: FileEditorTool for read/write/create/delete files
        - terminal: TerminalTool for command execution
        """
        tools = []
        tool_names = self.config.get("tools", [])
        
        for tool_name in tool_names:
            if tool_name == "file_editor":
                tools.append(FileEditorTool(base_path=self.sandbox_dir))
            elif tool_name == "terminal":
                tools.append(TerminalTool(cwd=self.sandbox_dir))
        
        return tools
    
    def _build_agent(self) -> Agent:
        """Build Agent instance from config."""
        return Agent(
            name=self.config.get("name", "agent"),
            llm=self.llm,
            system_prompt=self.config.get("system_prompt", ""),
            tools=self.tools,
            max_iterations=self.config.get("max_iterations", 10),
        )
    
    async def execute(
        self,
        task: str,
        system_prompt_override: Optional[str] = None,
    ) -> AgentResult:
        """Execute the agent with the given task.
        
        This runs the agent with tool support, streaming progress
        updates to the conversation stream if available.
        
        Args:
            task: The task prompt for the agent
            system_prompt_override: Optional override for system prompt
            
        Returns:
            AgentResult with content, tool calls, files modified, etc.
        """
        # Reset tracking
        self._tool_calls = []
        self._files_modified = []
        self._commands_run = []
        
        # Build messages
        system_prompt = system_prompt_override or self.config.get("system_prompt", "")
        messages = [
            {"role": "developer", "content": system_prompt},
            {"role": "user", "content": task},
        ]
        
        # Run agent and capture events
        content = ""
        success = True
        
        try:
            # Use the agent's run method
            # OpenHands SDK Agent.run() returns a generator of events
            async for event in self.agent.run(messages):
                await self._handle_event(event)
                
                # Capture final content
                if hasattr(event, "content") and event.content:
                    content = event.content
                elif hasattr(event, "message") and event.message:
                    content = event.message
            
        except Exception as e:
            success = False
            content = f"Agent execution failed: {str(e)}"
            if self.stream:
                await self.stream.emit_error(content, recoverable=False)
        
        return AgentResult(
            content=content,
            success=success,
            tool_calls=self._tool_calls,
            files_modified=self._files_modified,
            commands_run=self._commands_run,
            metadata={
                "model": self.config.get("model"),
                "agent_name": self.config.get("name"),
            },
        )
    
    async def _handle_event(self, event: Any) -> None:
        """Handle an event from the agent execution.
        
        Streams progress updates and tracks tool calls, file changes,
        and command executions.
        
        Args:
            event: Event from OpenHands Agent.run()
        """
        event_type = getattr(event, "type", None) or type(event).__name__
        
        # Tool call event
        if event_type in ("tool_call", "ToolCall"):
            tool_name = getattr(event, "tool_name", "unknown")
            tool_args = getattr(event, "args", {})
            
            self._tool_calls.append({
                "tool": tool_name,
                "args": tool_args,
            })
            
            if self.stream:
                await self.stream.emit_progress(
                    f"Using tool: {tool_name}",
                    metadata={"args": tool_args}
                )
        
        # File change event (from file_editor tool)
        elif event_type in ("file_change", "FileChange"):
            file_path = getattr(event, "file_path", "unknown")
            action = getattr(event, "action", "unknown")
            
            self._files_modified.append(file_path)
            
            if self.stream:
                await self.stream.emit_progress(
                    f"File {action}: {file_path}",
                    metadata={"action": action, "file": file_path}
                )
        
        # Command execution event (from terminal tool)
        elif event_type in ("command", "Command", "terminal"):
            command = getattr(event, "command", "unknown")
            
            self._commands_run.append(command)
            
            if self.stream:
                await self.stream.emit_progress(
                    f"Running: {command[:50]}..." if len(command) > 50 else f"Running: {command}",
                    metadata={"command": command}
                )
        
        # Action/thought event
        elif event_type in ("action", "Action"):
            action_content = getattr(event, "content", "") or getattr(event, "thought", "")
            if action_content and self.stream:
                # Don't emit every thought, just track
                pass
        
        # Error event
        elif event_type in ("error", "Error"):
            error_msg = getattr(event, "message", str(event))
            if self.stream:
                await self.stream.emit_progress(
                    f"Error: {error_msg}",
                    metadata={"error": True}
                )
    
    async def execute_simple(
        self,
        task: str,
        system_prompt: str = "",
    ) -> str:
        """Execute agent and return just the content string.
        
        Simplified interface for cases where you just need the response.
        
        Args:
            task: The task prompt
            system_prompt: System prompt to use
            
        Returns:
            The agent's response content
        """
        result = await self.execute(
            task,
            system_prompt_override=system_prompt or None,
        )
        return result.content


# Convenience function for quick agent execution
async def run_agent_with_tools(
    config: Dict[str, Any],
    task: str,
    sandbox_dir: str,
    stream: Optional["ConversationStream"] = None,
) -> AgentResult:
    """Run an agent with tool support.
    
    Args:
        config: Agent configuration
        task: Task prompt
        sandbox_dir: Directory for file operations
        stream: Optional stream for progress updates
        
    Returns:
        AgentResult from execution
    """
    executor = AgentExecutor(config, sandbox_dir, stream)
    return await executor.execute(task)
