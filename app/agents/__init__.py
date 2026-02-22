"""Agent definitions using OpenHands SDK.

This module provides a unified interface for creating and managing agents
using the OpenHands SDK. Agents are configured via JSON files in the configs/ directory.

Main Agents:
- orchestrator: Routes requests to appropriate sub-agents
- coding: Multi-agent system for code implementation
- architecture: System design and planning
- social: Casual conversation
- financial: Market analysis and financial guidance
- health: Fitness and nutrition coaching
- general: General knowledge and advice
- shell: CLI commands and one-liners

Sub-Agents (used by main agents):
- planner: Creates step-by-step plans
- executor: Implements code according to plans
- evaluator: Reviews and validates implementations
- websearch: Searches for current information
- linter: Code quality analysis
- security: Security vulnerability scanning
- proofreader: Text proofreading and improvement
- aws_architect: AWS cloud architecture specialist
- azure_architect: Azure cloud architecture specialist
"""
from openhands.sdk import LLM, Agent, Conversation, Tool
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.terminal import TerminalTool

from .factory import (
    # Core factory functions
    load_agent_config,
    load_sub_agent_config,
    create_agent,
    create_sub_agent,
    create_agent_from_config,
    AgentWrapper,
    
    # Factory registries
    AGENT_FACTORY_REGISTRY,
    SUB_AGENT_FACTORY_REGISTRY,
    AGENT_NAMES,
    SUB_AGENT_NAMES,
    
    # Utility functions
    get_agent_factory,
    get_sub_agent_factory,
    get_tool_instance,
)

# Convenience exports for creating specific agents
def get_orchestrator_agent(**kwargs):
    """Create an orchestrator agent."""
    return AGENT_FACTORY_REGISTRY["orchestrator"](**kwargs)

def get_coding_agent(**kwargs):
    """Create a coding agent."""
    return AGENT_FACTORY_REGISTRY["coding"](**kwargs)

def get_architecture_agent(**kwargs):
    """Create an architecture agent."""
    return AGENT_FACTORY_REGISTRY["architecture"](**kwargs)

def get_social_agent(**kwargs):
    """Create a social agent."""
    return AGENT_FACTORY_REGISTRY["social"](**kwargs)

def get_financial_agent(**kwargs):
    """Create a financial agent."""
    return AGENT_FACTORY_REGISTRY["financial"](**kwargs)

def get_health_agent(**kwargs):
    """Create a health agent."""
    return AGENT_FACTORY_REGISTRY["health"](**kwargs)

def get_general_agent(**kwargs):
    """Create a general agent."""
    return AGENT_FACTORY_REGISTRY["general"](**kwargs)

def get_shell_agent(**kwargs):
    """Create a shell agent."""
    return AGENT_FACTORY_REGISTRY["shell"](**kwargs)


# Sub-agent convenience functions
def get_planner_agent(**kwargs):
    """Create a planner sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["planner"](**kwargs)

def get_executor_agent(**kwargs):
    """Create an executor sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["executor"](**kwargs)

def get_evaluator_agent(**kwargs):
    """Create an evaluator sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["evaluator"](**kwargs)

def get_websearch_agent(**kwargs):
    """Create a websearch sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["websearch"](**kwargs)

def get_linter_agent(**kwargs):
    """Create a linter sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["linter"](**kwargs)

def get_security_agent(**kwargs):
    """Create a security sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["security"](**kwargs)

def get_proofreader_agent(**kwargs):
    """Create a proofreader sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["proofreader"](**kwargs)

def get_aws_architect_agent(**kwargs):
    """Create an AWS architect sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["aws_architect"](**kwargs)

def get_azure_architect_agent(**kwargs):
    """Create an Azure architect sub-agent."""
    return SUB_AGENT_FACTORY_REGISTRY["azure_architect"](**kwargs)


# Agent registry mapping category names to factory functions
AGENT_REGISTRY = {
    "coding": get_coding_agent,
    "architecture": get_architecture_agent,
    "social": get_social_agent,
    "financial": get_financial_agent,
    "health": get_health_agent,
    "general": get_general_agent,
    "shell": get_shell_agent,
}


__all__ = [
    # OpenHands SDK
    "LLM",
    "Agent",
    "Conversation",
    "Tool",
    "FileEditorTool",
    "TerminalTool",
    
    # Factory functions
    "load_agent_config",
    "load_sub_agent_config",
    "create_agent",
    "create_sub_agent",
    "create_agent_from_config",
    "AgentWrapper",
    
    # Registries
    "AGENT_FACTORY_REGISTRY",
    "SUB_AGENT_FACTORY_REGISTRY",
    "AGENT_REGISTRY",
    "AGENT_NAMES",
    "SUB_AGENT_NAMES",
    
    # Utility
    "get_agent_factory",
    "get_sub_agent_factory",
    "get_tool_instance",
    
    # Main agent factories
    "get_orchestrator_agent",
    "get_coding_agent",
    "get_architecture_agent",
    "get_social_agent",
    "get_financial_agent",
    "get_health_agent",
    "get_general_agent",
    "get_shell_agent",
    
    # Sub-agent factories
    "get_planner_agent",
    "get_executor_agent",
    "get_evaluator_agent",
    "get_websearch_agent",
    "get_linter_agent",
    "get_security_agent",
    "get_proofreader_agent",
    "get_aws_architect_agent",
    "get_azure_architect_agent",
]
