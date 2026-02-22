"""Agent factory module for creating agents from JSON configurations.

This module provides utilities to load agent configurations from JSON files
and create OpenHands SDK Agent instances with MCP server support.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from openhands.sdk import LLM, Agent, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool


# Base path for agent configurations
CONFIGS_PATH = Path(__file__).parent / "configs"
SUB_AGENTS_PATH = CONFIGS_PATH / "sub_agents"


def load_agent_config(agent_name: str) -> Dict[str, Any]:
    """Load agent configuration from JSON file.
    
    Args:
        agent_name: Name of the agent (e.g., 'coding', 'orchestrator')
        
    Returns:
        Dictionary containing agent configuration
    """
    config_path = CONFIGS_PATH / f"{agent_name}.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")
    
    with open(config_path, "r") as f:
        return json.load(f)


def load_sub_agent_config(sub_agent_name: str) -> Dict[str, Any]:
    """Load sub-agent configuration from JSON file.
    
    Args:
        sub_agent_name: Name of the sub-agent (e.g., 'planner', 'executor')
        
    Returns:
        Dictionary containing sub-agent configuration
    """
    config_path = SUB_AGENTS_PATH / f"{sub_agent_name}.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Sub-agent config not found: {config_path}")
    
    with open(config_path, "r") as f:
        return json.load(f)


def get_tool_instance(tool_name: str, **kwargs) -> Tool:
    """Get a tool instance by name.
    
    Args:
        tool_name: Name of the tool
        **kwargs: Additional arguments for tool initialization
        
    Returns:
        Tool instance
    """
    tools_map = {
        "file_editor": FileEditorTool,
        "terminal": TerminalTool,
    }
    
    tool_class = tools_map.get(tool_name)
    if not tool_class:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    return tool_class(**kwargs)


def create_agent_from_config(
    config: Dict[str, Any],
    sandbox_dir: Optional[str] = None,
    api_key: Optional[str] = None
) -> Agent:
    """Create an Agent instance from configuration dictionary.
    
    Args:
        config: Agent configuration dictionary
        sandbox_dir: Directory for sandbox operations
        api_key: API key for the LLM provider
        
    Returns:
        Configured Agent instance
    """
    # Create LLM
    llm = LLM(
        model=config.get("model", "google/gemini-3-flash-preview"),
        temperature=config.get("temperature", 0.7),
        api_key=api_key,
    )
    
    # Create tools
    tools: List[Tool] = []
    for tool_name in config.get("tools", []):
        tool_kwargs = {}
        if tool_name == "file_editor" and sandbox_dir:
            tool_kwargs["base_path"] = sandbox_dir
        tools.append(get_tool_instance(tool_name, **tool_kwargs))
    
    # Get MCP config (passed directly to Agent)
    mcp_config = config.get("mcp_config")
    
    # Create agent
    agent = Agent(
        name=config.get("name", "agent"),
        llm=llm,
        system_prompt=config.get("system_prompt", ""),
        tools=tools,
        max_iterations=config.get("max_iterations", 10),
        mcp_config=mcp_config,
        filter_tools_regex=config.get("filter_tools_regex"),
    )
    
    return agent


def create_agent(
    agent_name: str,
    sandbox_dir: Optional[str] = None,
    api_key: Optional[str] = None
) -> Agent:
    """Create an Agent instance by name.
    
    Args:
        agent_name: Name of the agent
        sandbox_dir: Directory for sandbox operations
        api_key: API key for the LLM provider
        
    Returns:
        Configured Agent instance
    """
    config = load_agent_config(agent_name)
    return create_agent_from_config(config, sandbox_dir, api_key)


def create_sub_agent(
    sub_agent_name: str,
    sandbox_dir: Optional[str] = None,
    api_key: Optional[str] = None
) -> Agent:
    """Create a sub-agent instance by name.
    
    Args:
        sub_agent_name: Name of the sub-agent
        sandbox_dir: Directory for sandbox operations
        api_key: API key for the LLM provider
        
    Returns:
        Configured Agent instance
    """
    config = load_sub_agent_config(sub_agent_name)
    return create_agent_from_config(config, sandbox_dir, api_key)


class AgentWrapper:
    """Wrapper class for agents with additional utilities."""
    
    def __init__(
        self,
        agent_name: str,
        sandbox_dir: Optional[str] = None,
        api_key: Optional[str] = None,
        is_sub_agent: bool = False,
    ):
        self.agent_name = agent_name
        self.sandbox_dir = sandbox_dir
        
        # Load config
        if is_sub_agent:
            self.config = load_sub_agent_config(agent_name)
        else:
            self.config = load_agent_config(agent_name)
        
        # Create agent (MCP config is passed directly from config)
        self.agent = create_agent_from_config(self.config, sandbox_dir, api_key)
    
    @property
    def name(self) -> str:
        return self.config.get("name", self.agent_name)
    
    @property
    def model(self) -> str:
        return self.config.get("model", "")
    
    @property
    def system_prompt(self) -> str:
        return self.config.get("system_prompt", "")
    
    @property
    def temperature(self) -> float:
        return self.config.get("temperature", 0.7)
    
    @property
    def skills(self) -> List[str]:
        return self.config.get("skills", [])
    
    @property
    def mcp_config(self) -> Optional[Dict[str, Any]]:
        """Get MCP config passed to this agent."""
        return self.config.get("mcp_config")
    
    @property
    def output_dir(self) -> Optional[str]:
        return self.config.get("output_dir")
    
    def get_system_prompt(self) -> str:
        """Return the system prompt."""
        return self.system_prompt
    
    def get_model(self) -> str:
        """Return the model identifier."""
        return self.model


# Agent registry for quick access
AGENT_NAMES = [
    "orchestrator",
    "coding",
    "architecture",
    "social",
    "financial",
    "health",
    "general",
    "shell",
]

SUB_AGENT_NAMES = [
    "planner",
    "executor",
    "evaluator",
    "websearch",
    "linter",
    "security",
    "proofreader",
    "aws_architect",
    "azure_architect",
]


def get_agent_factory(agent_name: str) -> callable:
    """Get a factory function for creating an agent by name.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        Factory function that creates the agent
    """
    def factory(sandbox_dir: Optional[str] = None, api_key: Optional[str] = None) -> AgentWrapper:
        return AgentWrapper(agent_name, sandbox_dir, api_key)
    
    return factory


def get_sub_agent_factory(sub_agent_name: str) -> callable:
    """Get a factory function for creating a sub-agent by name.
    
    Args:
        sub_agent_name: Name of the sub-agent
        
    Returns:
        Factory function that creates the sub-agent
    """
    def factory(sandbox_dir: Optional[str] = None, api_key: Optional[str] = None) -> AgentWrapper:
        return AgentWrapper(sub_agent_name, sandbox_dir, api_key, is_sub_agent=True)
    
    return factory


# Create factory registry
AGENT_FACTORY_REGISTRY = {
    name: get_agent_factory(name) for name in AGENT_NAMES
}

SUB_AGENT_FACTORY_REGISTRY = {
    name: get_sub_agent_factory(name) for name in SUB_AGENT_NAMES
}
