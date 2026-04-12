"""External tool plugin registry.

Discovers and loads tool plugins from the tools/ directory at startup.
Each plugin is a subdirectory containing tool.yaml (metadata) and either:
  - tool.py (in_process): imported directly, exports get_tools/get_schemas/execute
  - tool_meta.yaml (subprocess): schema metadata read statically; tools run via RemotePluginExecutor

Mirrors the specialist auto-discovery pattern in specialists.py.

Paths:
    EXTERNAL_TOOLS_PATH (env) overrides all
    EXTERNAL_TOOLS_FALLBACK (env) used if primary path doesn't exist
    Default fallback: project_root/tools/

Hot reload:
    POST /admin/reload-tools calls registry.reload()
    Re-scans, re-runs uv sync (subprocess), re-imports modules (in_process)
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

from agent.plugin_runner import make_remote_tool, RemotePluginExecutor, RemotePluginAction
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
    execution: str  # "in_process" | "subprocess"
    path: Path
    module: Any = None
    sdk_tools: List[Tool] = field(default_factory=list)
    schemas: Dict[str, dict] = field(default_factory=dict)
    dispatcher: Optional[Callable] = None


class ToolRegistry:
    """Discovers, loads, and indexes external tool plugins."""

    def __init__(self, tools_path: str = "", fallback_path: str = ""):
        self.tools_path = Path(tools_path) if tools_path else None
        self.fallback_path = Path(fallback_path) if fallback_path else None
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
            if not config_path.exists():
                continue

            try:
                self._load_plugin(subdir, config_path)
            except Exception as e:
                logger.error(f"Failed to load tool plugin {subdir.name}: {e}")
                continue

        self._resolved = True
        logger.info(
            f"Tool registry: {len(self._tools)} external tools loaded: {list(self._tools.keys())}"
        )

    def _load_plugin(self, subdir: Path, config_path: Path) -> None:
        """Load a single tool plugin from its directory."""
        data = load_yaml(config_path)
        slug = subdir.name

        scope = data.get("scope", "both")
        if scope not in ("main", "specialist", "both"):
            logger.warning(f"Tool {slug}: invalid scope '{scope}', defaulting to 'both'")
            scope = "both"

        execution = data.get("execution", "subprocess")

        if execution == "in_process":
            self._load_plugin_in_process(subdir, slug, data, scope)
        else:
            self._load_plugin_subprocess(subdir, slug, data, scope)

    def _load_plugin_in_process(
        self, subdir: Path, slug: str, data: dict, scope: str
    ) -> None:
        """Load plugin by importing tool.py directly into the process."""
        module_path = subdir / "tool.py"
        if not module_path.exists():
            logger.warning(f"Tool {slug} (in_process) missing tool.py, skipping")
            return

        spec = importlib.util.spec_from_file_location(f"tools.{slug}", module_path)
        if spec is None or spec.loader is None:
            logger.error(f"Tool {slug}: failed to create module spec")
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"tools.{slug}"] = module

        plugin_dir = str(subdir)
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Tool {slug}: import error: {e}")
            return

        sdk_tools: List[Tool] = []
        if hasattr(module, "get_tools"):
            try:
                sdk_tools = module.get_tools()
            except Exception as e:
                logger.warning(f"Tool {slug}: get_tools() error: {e}")

        schemas: Dict[str, dict] = {}
        if hasattr(module, "get_schemas"):
            try:
                schemas = module.get_schemas()
            except Exception as e:
                logger.warning(f"Tool {slug}: get_schemas() error: {e}")

        dispatcher = getattr(module, "execute", None)

        self._tools[slug] = ExternalToolConfig(
            slug=slug,
            name=data.get("name", slug),
            description=data.get("description", slug),
            version=data.get("version", "0.0.0"),
            scope=scope,
            execution="in_process",
            path=subdir,
            module=module,
            sdk_tools=sdk_tools,
            schemas=schemas,
            dispatcher=dispatcher,
        )

    def _load_plugin_subprocess(
        self, subdir: Path, slug: str, data: dict, scope: str
    ) -> None:
        """Load plugin as a subprocess-isolated tool via RemotePluginExecutor."""
        # Run uv sync to ensure plugin deps are installed
        try:
            result = subprocess.run(
                ["uv", "sync", "--project", str(subdir)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.warning(
                    f"Tool {slug}: uv sync failed (non-fatal): {result.stderr[:500]}"
                )
            else:
                logger.info(f"Tool {slug}: uv sync succeeded")
        except subprocess.TimeoutExpired:
            logger.warning(f"Tool {slug}: uv sync timed out")
        except Exception as e:
            logger.warning(f"Tool {slug}: uv sync error: {e}")

        # Read schema metadata from tool_meta.yaml
        meta_path = subdir / "tool_meta.yaml"
        if not meta_path.exists():
            logger.warning(f"Tool {slug} (subprocess) missing tool_meta.yaml, skipping")
            return

        try:
            meta = load_yaml(meta_path)
        except Exception as e:
            logger.warning(f"Tool {slug}: failed to load tool_meta.yaml: {e}")
            return

        raw_schemas = meta.get("tools", meta.get("schemas", {}))

        sdk_tools: List[Tool] = []
        schemas: Dict[str, dict] = {}

        for tool_name, schema in raw_schemas.items():
            try:
                remote_tool = make_remote_tool(slug, tool_name, schema, subdir)
                sdk_tools.append(remote_tool)
                schemas[tool_name] = schema
            except Exception as e:
                logger.warning(f"Tool {slug}.{tool_name}: make_remote_tool error: {e}")

        async def dispatcher(name: str, args: Dict[str, Any]) -> str:
            executor = RemotePluginExecutor(slug, name, subdir)
            obs = executor(RemotePluginAction(tool_name=name, args=args))
            return obs.result

        self._tools[slug] = ExternalToolConfig(
            slug=slug,
            name=data.get("name", slug),
            description=data.get("description", slug),
            version=data.get("version", "0.0.0"),
            scope=scope,
            execution="subprocess",
            path=subdir,
            module=None,
            sdk_tools=sdk_tools,
            schemas=schemas,
            dispatcher=dispatcher,
        )

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
                    try:
                        from channels.status import send_status, StatusType
                        await send_status(StatusType.TOOL_FAILED, f"Tool: {name}", str(e)[:200])
                    except Exception:
                        pass
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
                "execution": c.execution,
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

        for slug, old_config in list(self._tools.items()):
            subdir = base / slug
            config_path = subdir / "tool.yaml"

            if not config_path.exists():
                statuses[slug] = "removed"
                del self._tools[slug]
                continue

            try:
                data = load_yaml(config_path)
                execution = data.get("execution", "subprocess")

                if execution == "in_process":
                    module_path = subdir / "tool.py"
                    if not module_path.exists():
                        statuses[slug] = "failed: tool.py missing"
                        continue

                    if f"tools.{slug}" in sys.modules:
                        module = importlib.reload(sys.modules[f"tools.{slug}"])
                    else:
                        spec = importlib.util.spec_from_file_location(f"tools.{slug}", module_path)
                        if spec is None or spec.loader is None:
                            statuses[slug] = "failed: could not create module spec"
                            continue
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[f"tools.{slug}"] = module
                        spec.loader.exec_module(module)

                    sdk_tools: List[Tool] = []
                    if hasattr(module, "get_tools"):
                        sdk_tools = module.get_tools()

                    schemas: Dict[str, dict] = {}
                    if hasattr(module, "get_schemas"):
                        schemas = module.get_schemas()

                    dispatcher = getattr(module, "execute", None)
                    scope = data.get("scope", "both")

                    self._tools[slug] = ExternalToolConfig(
                        slug=slug,
                        name=data.get("name", slug),
                        description=data.get("description", slug),
                        version=data.get("version", "0.0.0"),
                        scope=scope,
                        execution="in_process",
                        path=subdir,
                        module=module,
                        sdk_tools=sdk_tools,
                        schemas=schemas,
                        dispatcher=dispatcher,
                    )
                else:
                    # subprocess: re-run uv sync and re-read tool_meta.yaml
                    try:
                        result = subprocess.run(
                            ["uv", "sync", "--project", str(subdir)],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        if result.returncode != 0:
                            logger.warning(
                                f"Tool {slug}: uv sync failed on reload: {result.stderr[:500]}"
                            )
                    except Exception as e:
                        logger.warning(f"Tool {slug}: uv sync error on reload: {e}")

                    meta_path = subdir / "tool_meta.yaml"
                    if not meta_path.exists():
                        statuses[slug] = "failed: tool_meta.yaml missing"
                        continue

                    meta = load_yaml(meta_path)
                    raw_schemas = meta.get("tools", meta.get("schemas", {}))
                    scope = data.get("scope", "both")

                    sdk_tools = []
                    schemas = {}
                    for tool_name, schema in raw_schemas.items():
                        try:
                            remote_tool = make_remote_tool(slug, tool_name, schema, subdir)
                            sdk_tools.append(remote_tool)
                            schemas[tool_name] = schema
                        except Exception as e:
                            logger.warning(f"Tool {slug}.{tool_name}: make_remote_tool error on reload: {e}")

                    async def dispatcher(name: str, args: Dict[str, Any], _slug: str = slug) -> str:
                        executor = RemotePluginExecutor(_slug, name, subdir)
                        obs = executor(RemotePluginAction(tool_name=name, args=args))
                        return obs.result

                    self._tools[slug] = ExternalToolConfig(
                        slug=slug,
                        name=data.get("name", slug),
                        description=data.get("description", slug),
                        version=data.get("version", "0.0.0"),
                        scope=scope,
                        execution="subprocess",
                        path=subdir,
                        module=None,
                        sdk_tools=sdk_tools,
                        schemas=schemas,
                        dispatcher=dispatcher,
                    )

                statuses[slug] = "reloaded"
            except Exception as e:
                logger.error(f"Reload failed for {slug}: {e}")
                statuses[slug] = f"failed: {type(e).__name__}: {e}"

        return statuses


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
