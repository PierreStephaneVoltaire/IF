"""External tool plugin registry.

Discovers and loads tool plugins from the tools/ directory at startup.
Each plugin is a subdirectory containing tool.yaml (metadata) and tool.py
(exports get_tools, get_schemas, execute).

Mirrors the specialist auto-discovery pattern in specialists.py.

Plugin contract:
    get_tools() -> List[Tool]:             SDK Tool objects (register_tool() as side effect)
    get_schemas() -> Dict[str, dict]:      snake_case name -> JSON schema
    async execute(name, args) -> str:      dispatcher for non-agentic specialist path

Paths:
    EXTERNAL_TOOLS_PATH (env) overrides all
    EXTERNAL_TOOLS_FALLBACK (env) used if primary path doesn't exist
    Default fallback: project_root/tools/

Hot reload:
    POST /admin/reload-tools calls registry.reload()
    Re-scans, re-installs deps, re-imports modules via importlib.reload()
    Per-tool status: "reloaded", "removed", "failed: <reason>"
"""
from __future__ import annotations

import importlib
import importlib.util
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openhands.sdk import Tool

from agent.prompts.yaml_loader import load_yaml
from config import EXTERNAL_TOOLS_PATH, EXTERNAL_TOOLS_FALLBACK

logger = logging.getLogger(__name__)

_registry: Optional["ToolRegistry"] = None


@dataclass
class ExternalToolConfig:
    """Metadata and runtime references for an external tool plugin."""

    slug: str
    name: str
    description: str
    version: str
    scope: str  # "main" | "specialist" | "both"
    path: Path
    module: Any = None
    sdk_tools: List[Tool] = field(default_factory=list)
    schemas: Dict[str, dict] = field(default_factory=dict)
    dispatcher: Optional[Callable] = None


class ToolRegistry:
    """Discovers, loads, and indexes external tool plugins."""

    def __init__(self, tools_path: str = "", fallback_path: str = ""):
        self.tools_path = Path(tools_path) if tools_path else Path()
        self.fallback_path = Path(fallback_path) if fallback_path else Path()
        self._tools: Dict[str, ExternalToolConfig] = {}
        self._resolved = False

    def _resolve_path(self) -> Optional[Path]:
        """Determine which tools directory to use."""
        if self.tools_path and self.tools_path.is_dir():
            return self.tools_path
        if self.fallback_path and self.fallback_path.is_dir():
            return self.fallback_path
        return None

    def scan(self) -> None:
        """Scan the tools directory and load all plugins."""
        base = self._resolve_path()
        if not base:
            logger.info("No external tools directory found — skipping plugin scan")
            return

        if not base.is_dir():
            logger.error(f"Tools directory not found: {base}")
            return

        for subdir in sorted(base.iterdir()):
            if not subdir.is_dir():
                continue

            config_path = subdir / "tool.yaml"
            module_path = subdir / "tool.py"

            if not config_path.exists():
                continue
            if not module_path.exists():
                logger.warning(f"Tool plugin {subdir.name} missing tool.py, skipping")
                continue

            try:
                self._load_plugin(subdir, config_path, module_path)
            except Exception as e:
                logger.error(f"Failed to load tool plugin {subdir.name}: {e}")
                continue

        self._resolved = True
        logger.info(
            f"Tool registry: {len(self._tools)} external tools loaded: {list(self._tools.keys())}"
        )

    def _load_plugin(self, subdir: Path, config_path: Path, module_path: Path) -> None:
        """Load a single tool plugin from its directory."""
        data = load_yaml(config_path)
        slug = subdir.name

        scope = data.get("scope", "both")
        if scope not in ("main", "specialist", "both"):
            logger.warning(f"Tool {slug}: invalid scope '{scope}', defaulting to 'both'")
            scope = "both"

        # Import the module
        spec = importlib.util.spec_from_file_location(f"tools.{slug}", module_path)
        if spec is None or spec.loader is None:
            logger.error(f"Tool {slug}: failed to create module spec")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"tools.{slug}"] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Tool {slug}: import error: {e}")
            return

        # Collect SDK tools
        sdk_tools: List[Tool] = []
        if hasattr(module, "get_tools"):
            try:
                sdk_tools = module.get_tools()
            except Exception as e:
                logger.warning(f"Tool {slug}: get_tools() error: {e}")

        # Collect JSON schemas
        schemas: Dict[str, dict] = {}
        if hasattr(module, "get_schemas"):
            try:
                schemas = module.get_schemas()
            except Exception as e:
                logger.warning(f"Tool {slug}: get_schemas() error: {e}")

        # Collect dispatcher
        dispatcher = getattr(module, "execute", None)

        config = ExternalToolConfig(
            slug=slug,
            name=data.get("name", slug),
            description=data.get("description", slug),
            version=data.get("version", "0.0.0"),
            scope=scope,
            path=subdir,
            module=module,
            sdk_tools=sdk_tools,
            schemas=schemas,
            dispatcher=dispatcher,
        )
        self._tools[slug] = config

    def get_sdk_tools(self, scope: str = "main") -> List[Tool]:
        """Get SDK Tool objects for the given scope."""
        tools: List[Tool] = []
        for config in self._tools.values():
            if scope in (config.scope, "both") or config.scope == "both":
                tools.extend(config.sdk_tools)
        return tools

    def get_schema(self, name: str) -> Optional[dict]:
        """Get a JSON schema by snake_case tool name."""
        for config in self._tools.values():
            if name in config.schemas:
                return config.schemas[name]
        return None

    def get_schemas_for_names(self, names: List[str]) -> List[dict]:
        """Get JSON schemas for a list of tool names."""
        schemas: List[dict] = []
        for name in names:
            schema = self.get_schema(name)
            if schema:
                schemas.append(schema)
        return schemas

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool by snake_case name via its dispatcher."""
        for config in self._tools.values():
            if name in config.schemas and config.dispatcher:
                try:
                    return await config.dispatcher(name, args)
                except Exception as e:
                    logger.error(f"Tool {name} execution error: {e}")
                    return f"ERROR: {type(e).__name__}: {e}"
        return f"Unknown external tool: {name}"

    def has_tool(self, name: str) -> bool:
        """Check if a tool name is registered."""
        return any(name in config.schemas for config in self._tools.values())

    def list_tools(self) -> List[Dict[str, str]]:
        """List all registered tools as summary dicts."""
        return [
            {
                "slug": c.slug,
                "name": c.name,
                "description": c.description,
                "version": c.version,
                "scope": c.scope,
                "tool_count": str(len(c.schemas)),
            }
            for c in self._tools.values()
        ]

    def reload(self) -> Dict[str, str]:
        """Reload all tool plugins. Returns status per tool."""
        statuses: Dict[str, str] = {}
        base = self._resolve_path()
        if not base:
            return {"error": "No tools directory found"}

        # Re-scan requirements first
        self._install_deps(base)

        for slug, old_config in list(self._tools.items()):
            subdir = base / slug
            config_path = subdir / "tool.yaml"
            module_path = subdir / "tool.py"

            if not config_path.exists() or not module_path.exists():
                statuses[slug] = "removed"
                del self._tools[slug]
                continue

            try:
                # Re-import the module
                if f"tools.{slug}" in sys.modules:
                    module = importlib.reload(sys.modules[f"tools.{slug}"])
                else:
                    spec = importlib.util.spec_from_file_location(f"tools.{slug}", module_path)
                    if spec is None or spec.loader is None:
                        statuses[slug] = f"failed: could not create module spec"
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"tools.{slug}"] = module
                    spec.loader.exec_module(module)

                # Re-collect
                sdk_tools: List[Tool] = []
                if hasattr(module, "get_tools"):
                    sdk_tools = module.get_tools()

                schemas: Dict[str, dict] = {}
                if hasattr(module, "get_schemas"):
                    schemas = module.get_schemas()

                dispatcher = getattr(module, "execute", None)
                data = load_yaml(config_path)

                self._tools[slug] = ExternalToolConfig(
                    slug=slug,
                    name=data.get("name", slug),
                    description=data.get("description", slug),
                    version=data.get("version", "0.0.0"),
                    scope=data.get("scope", "both"),
                    path=subdir,
                    module=module,
                    sdk_tools=sdk_tools,
                    schemas=schemas,
                    dispatcher=dispatcher,
                )
                statuses[slug] = "reloaded"
            except Exception as e:
                logger.error(f"Reload failed for {slug}: {e}")
                statuses[slug] = f"failed: {type(e).__name__}: {e}"

        return statuses

    def _install_deps(self, base: Path) -> None:
        """Install requirements.txt from each tool directory."""
        for subdir in base.iterdir():
            if not subdir.is_dir():
                continue
            req_file = subdir / "requirements.txt"
            if not req_file.exists():
                continue
            try:
                logger.info(f"Installing dependencies for {subdir.name}...")
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    logger.warning(
                        f"pip install failed for {subdir.name}: {result.stderr[:500]}"
                    )
                else:
                    logger.info(f"Dependencies installed for {subdir.name}")
            except subprocess.TimeoutExpired:
                logger.warning(f"pip install timed out for {subdir.name}")
            except Exception as e:
                logger.warning(f"Failed to install deps for {subdir.name}: {e}")


def install_external_deps() -> None:
    """Install dependencies for all external tool plugins."""
    if _registry is None:
        logger.warning("Tool registry not initialized, cannot install deps")
        return
    base = _registry._resolve_path()
    if base:
        _registry._install_deps(base)


def init_tool_registry() -> ToolRegistry:
    """Initialize and scan the tool registry. Returns the registry."""
    global _registry
    _registry = ToolRegistry(
        tools_path=EXTERNAL_TOOLS_PATH,
        fallback_path=EXTERNAL_TOOLS_FALLBACK,
    )
    _registry.scan()
    return _registry


def get_tool_registry() -> ToolRegistry:
    """Get the current tool registry instance."""
    if _registry is None:
        raise RuntimeError("Tool registry not initialized — call init_tool_registry() first")
    return _registry
