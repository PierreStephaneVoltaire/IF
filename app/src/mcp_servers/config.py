"""MCP server configuration and preset mapping.

This module defines the MCP servers available to the agent and maps them
to specific presets. MCP servers are configured using the standard MCP config
format and passed to the OpenHands Agent constructor.

All MCP servers use uvx-based command execution for isolation and simplicity.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass

from config import SANDBOX_PATH, GOOGLE_SHEETS_CREDENTIALS, ALPHAVANTAGE_API_KEY


# ============================================================================
# MCP Server Definitions
# ============================================================================

MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "time": {
        "command": "uvx",
        "args": ["mcp-server-time@latest"],
        "env": {
            "FASTMCP_LOG_LEVEL": "ERROR"
        }
    },
    "aws_docs": {
        "command": "uvx",
        "args": ["awslabs.aws-documentation-mcp-server@latest"],
        "env": {
            "FASTMCP_LOG_LEVEL": "ERROR",
            "AWS_DOCUMENTATION_PARTITION": "aws",
            "MCP_USER_AGENT": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        }
    },
    "google_sheets": {
        "command": "uvx",
        "args": ["mcp-server-google-sheets@latest"],
        "env": {
            "FASTMCP_LOG_LEVEL": "ERROR",
            "CREDENTIALS_CONFIG": GOOGLE_SHEETS_CREDENTIALS,
        }
    },
    "yahoo_finance": {
        "command": "uvx",
        "args": ["mcp-yahoo-finance"],
        "env": {
            "FASTMCP_LOG_LEVEL": "ERROR"
        }
    },
    "alpha_vantage": {
        "command": "uvx",
        "args": ["alphavantage-mcp"],
        "env": {
            "ALPHAVANTAGE_API_KEY": ALPHAVANTAGE_API_KEY,
            "FASTMCP_LOG_LEVEL": "ERROR"
        }
    },
    "sandbox": {
        "command": "uvx",
        "args": [
            "mcp-server-filesystem@latest",
            "--root",
            SANDBOX_PATH
        ],
        "env": {
            "FASTMCP_LOG_LEVEL": "ERROR"
        }
    }
}


# ============================================================================
# Preset-to-MCP Mapping
# ============================================================================

PRESET_MCP_MAP: Dict[str, list] = {
    # Servers available to ALL presets
    "__all__": ["time"],  # Note: memory tools are registered separately, not via MCP
    
    # Preset-specific servers
    "architecture": ["aws_docs", "sandbox"],
    "coding": ["sandbox"],
    "health": ["google_sheets"],
    "mental_health": [],  # No MCP servers for mental health
    "social": [],  # No MCP servers for social
    "finance": ["yahoo_finance", "alpha_vantage"],  # Finance preset gets stock data servers
    "pondering": [],  # Only gets time via __all__ - no other MCP servers
    
    # Other presets receive only __all__ servers
    # Add more mappings as needed
}


# ============================================================================
# MCP Config Resolution
# ============================================================================

def resolve_mcp_config(preset_slug: str, conversation_id: str = "") -> Dict[str, Any]:
    """Resolve the MCP configuration for a given preset.
    
    Merges __all__ servers with preset-specific servers and formats
    into the structure OpenHands expects.
    
    Sandbox server root is scoped to the conversation's directory when
    conversation_id is provided.
    
    Args:
        preset_slug: The preset identifier (e.g., "coding", "architecture")
        conversation_id: Unique conversation identifier for sandbox scoping
        
    Returns:
        MCP config dict with "mcpServers" key containing server definitions
        
    Example:
        >>> config = resolve_mcp_config("coding", "conv_abc123")
        >>> print(config["mcpServers"].keys())
        dict_keys(['time', 'sandbox'])
    """
    # Start with __all__ servers
    server_keys: Set[str] = set(PRESET_MCP_MAP.get("__all__", []))
    
    # Add preset-specific servers
    server_keys.update(PRESET_MCP_MAP.get(preset_slug, []))
    
    # Build the mcpServers dict
    mcp_servers = {}
    for key in server_keys:
        if key in MCP_SERVERS:
            server_def = dict(MCP_SERVERS[key])  # shallow copy
            
            # Scope sandbox to conversation directory
            if key == "sandbox" and conversation_id:
                from agent.sandbox import sandbox_path_for
                scoped_path = sandbox_path_for(conversation_id)
                server_def["args"] = [
                    "mcp-server-filesystem@latest",
                    "--root",
                    scoped_path,
                ]
            
            mcp_servers[key] = server_def
        else:
            # Log warning for undefined servers
            print(f"[MCP] Warning: Server '{key}' referenced but not defined in MCP_SERVERS")
    
    # Return in the format expected by OpenHands SDK
    return {
        "mcpServers": mcp_servers
    }


def get_available_servers() -> Dict[str, Dict[str, Any]]:
    """Get all available MCP server definitions.
    
    Returns:
        Dict of server name -> server configuration
    """
    return MCP_SERVERS.copy()


def get_preset_servers(preset_slug: str) -> list:
    """Get the list of servers for a specific preset.
    
    Args:
        preset_slug: The preset identifier
        
    Returns:
        List of server names for this preset
    """
    all_servers = set(PRESET_MCP_MAP.get("__all__", []))
    preset_servers = set(PRESET_MCP_MAP.get(preset_slug, []))
    return list(all_servers | preset_servers)


def has_sandbox_access(preset_slug: str) -> bool:
    """Check if a preset has sandbox access.
    
    Args:
        preset_slug: The preset identifier
        
    Returns:
        True if the preset has sandbox MCP server access
    """
    servers = get_preset_servers(preset_slug)
    return "sandbox" in servers


# ============================================================================
# Sandbox Behavior Instructions
# ============================================================================

SANDBOX_INSTRUCTION = """If your response includes code exceeding 5 lines, do not embed it in the message body. Write it to a file in the sandbox and reference the file path. The file will be delivered as an attachment.

Sandbox path: {sandbox_path}

Supported file types:
- Code: .py, .ts, .js, .jsx, .tsx, .go, .rs, .rb, .java, .c, .cpp, .cs, .swift, .kt
- IaC/DevOps: .tf, .hcl, .yaml, .yml, .json, .toml, .Dockerfile, .helmfile, .tfvars
- Config: .env.example, .ini, .cfg, .conf, .properties, .xml
- Shell: .sh, .bash, .zsh, .ps1, .bat
- Documents: .md, .txt, .pdf, .rst, .adoc
- Images: .png, .svg, .jpg, .webp, .drawio
- Data: .csv, .parquet, .sql"""


def get_sandbox_instruction(preset_slug: str, conversation_id: str = "") -> Optional[str]:
    """Get sandbox instruction for presets with sandbox access.
    
    Args:
        preset_slug: The preset identifier
        conversation_id: Unique conversation identifier for scoped sandbox path
        
    Returns:
        Sandbox instruction string if preset has access, None otherwise
    """
    if has_sandbox_access(preset_slug):
        if conversation_id:
            from agent.sandbox import sandbox_path_for
            scoped_path = sandbox_path_for(conversation_id)
            return SANDBOX_INSTRUCTION.format(sandbox_path=scoped_path)
        return SANDBOX_INSTRUCTION.format(sandbox_path=SANDBOX_PATH)
    return None


# ============================================================================
# Validation
# ============================================================================

def validate_mcp_config() -> bool:
    """Validate MCP configuration at startup.
    
    Checks that:
    - All servers referenced in PRESET_MCP_MAP are defined in MCP_SERVERS
    - SANDBOX_PATH exists or can be created
    
    Returns:
        True if configuration is valid
        
    Raises:
        ValueError: If configuration is invalid
    """
    errors = []
    
    # Check all referenced servers are defined
    all_referenced_servers = set()
    for servers in PRESET_MCP_MAP.values():
        all_referenced_servers.update(servers)
    
    for server_name in all_referenced_servers:
        if server_name not in MCP_SERVERS:
            errors.append(f"Server '{server_name}' referenced in PRESET_MCP_MAP but not defined in MCP_SERVERS")
    
    # Check sandbox path
    if not os.path.exists(SANDBOX_PATH):
        try:
            os.makedirs(SANDBOX_PATH, exist_ok=True)
            print(f"[MCP] Created sandbox directory: {SANDBOX_PATH}")
        except Exception as e:
            errors.append(f"Cannot create SANDBOX_PATH '{SANDBOX_PATH}': {e}")
    
    if errors:
        raise ValueError("MCP configuration errors:\n" + "\n".join(errors))
    
    return True
