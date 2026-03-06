
from __future__ import annotations
import os
import logging
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass

from config import SANDBOX_PATH, GOOGLE_SHEETS_CREDENTIALS, ALPHAVANTAGE_API_KEY

logger = logging.getLogger(__name__)



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
    }
}



PRESET_MCP_MAP: Dict[str, list] = {
    "__all__": ["time"],
    
    "architecture": ["aws_docs"],
    "code": [],
    "health": ["google_sheets"],
    "mental_health": [],
    "social": [],
    "finance": ["yahoo_finance", "alpha_vantage"],
    "pondering": [],
    
}



def resolve_mcp_config(preset_slug: str, conversation_id: str = "") -> Dict[str, Any]:

    server_keys: Set[str] = set(PRESET_MCP_MAP.get("__all__", []))
    
    server_keys.update(PRESET_MCP_MAP.get(preset_slug, []))
    
    mcp_servers = {}
    for key in server_keys:
        if key in MCP_SERVERS:
            server_def = dict(MCP_SERVERS[key])
            mcp_servers[key] = server_def
        else:
            logger.warning(f"Server '{key}' referenced but not defined in MCP_SERVERS")
    
    return {
        "mcpServers": mcp_servers
    }


def get_available_servers() -> Dict[str, Dict[str, Any]]:

    return MCP_SERVERS.copy()


def get_preset_servers(preset_slug: str) -> list:

    all_servers = set(PRESET_MCP_MAP.get("__all__", []))
    preset_servers = set(PRESET_MCP_MAP.get(preset_slug, []))
    return list(all_servers | preset_servers)


def has_sandbox_access(preset_slug: str) -> bool:

    return False



SANDBOX_INSTRUCTION = """DEPRECATED: Use terminal_execute for file operations instead.

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

    return None



def validate_mcp_config() -> bool:

    errors = []
    
    all_referenced_servers = set()
    for servers in PRESET_MCP_MAP.values():
        all_referenced_servers.update(servers)
    
    for server_name in all_referenced_servers:
        if server_name not in MCP_SERVERS:
            errors.append(f"Server '{server_name}' referenced in PRESET_MCP_MAP but not defined in MCP_SERVERS")
    
    if not os.path.exists(SANDBOX_PATH):
        try:
            os.makedirs(SANDBOX_PATH, exist_ok=True)
            logger.info(f"Created sandbox directory: {SANDBOX_PATH}")
        except Exception as e:
            errors.append(f"Cannot create SANDBOX_PATH '{SANDBOX_PATH}': {e}")
    
    if errors:
        raise ValueError("MCP configuration errors:\n" + "\n".join(errors))
    
    return True
