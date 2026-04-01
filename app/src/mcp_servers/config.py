
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Set

from agent.prompts.yaml_loader import load_yaml

logger = logging.getLogger(__name__)

_MCP_SERVERS_PATH = Path(__file__).parent.parent / "agent" / "prompts" / "specialists" / "mcp_servers.yaml"


def _load_mcp_servers() -> Dict[str, Dict[str, Any]]:
    """Load MCP server definitions from YAML with env var interpolation."""
    try:
        return load_yaml(_MCP_SERVERS_PATH)
    except FileNotFoundError:
        logger.error(f"MCP servers config not found: {_MCP_SERVERS_PATH}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load MCP servers config: {e}")
        return {}


MCP_SERVERS: Dict[str, Dict[str, Any]] = _load_mcp_servers()


PRESET_MCP_MAP: Dict[str, list] = {
    "__all__": ["time"],

    "architecture": ["aws_docs"],
    "code": [],
    "health": [],
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


def validate_mcp_config() -> bool:

    errors = []

    all_referenced_servers = set()
    for servers in PRESET_MCP_MAP.values():
        all_referenced_servers.update(servers)

    for server_name in all_referenced_servers:
        if server_name not in MCP_SERVERS:
            errors.append(f"Server '{server_name}' referenced in PRESET_MCP_MAP but not defined in MCP_SERVERS")

    if errors:
        raise ValueError("MCP configuration errors:\n" + "\n".join(errors))

    return True
