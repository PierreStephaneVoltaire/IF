"""Remote plugin executor — runs plugin tools out-of-process in per-plugin uv venvs.

Used by tool_registry.py for plugins with execution: subprocess in their tool.yaml.
Communication is JSON over stdin/stdout via tools/_plugin_runner.py copied into each plugin dir.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from pathlib import Path
from typing import Any, Dict

from openhands.sdk import Action, Observation, ToolDefinition
from openhands.sdk.tool import ToolExecutor

from agent.tools.base import TextObservation

logger = logging.getLogger(__name__)


class RemotePluginAction(Action):
    tool_name: str = ""
    args: Dict[str, Any] = {}


class RemotePluginObservation(TextObservation):
    result: str = ""

    @property
    def visualize(self):
        from openhands.sdk import TextContent
        from rich.text import Text
        t = Text()
        t.append(self.result[:500])
        return t

    def to_llm_content(self):
        return [{"type": "text", "text": self.result}]


class RemotePluginExecutor(ToolExecutor[RemotePluginAction, RemotePluginObservation]):
    """Executes a plugin tool out-of-process via uv run + JSON IPC."""

    def __init__(self, slug: str, tool_name: str, plugin_dir: Path) -> None:
        self.slug = slug
        self.tool_name = tool_name
        self.plugin_dir = plugin_dir

    def __call__(self, action: RemotePluginAction, conversation=None) -> RemotePluginObservation:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, self._execute(action))
            return future.result()

    async def _execute(self, action: RemotePluginAction) -> RemotePluginObservation:
        runner_path = self.plugin_dir / "_plugin_runner.py"
        payload = json.dumps({"name": self.tool_name, "args": action.args}) + "\n"

        try:
            proc = await asyncio.create_subprocess_exec(
                "uv", "run",
                "--project", str(self.plugin_dir),
                "python", str(runner_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(payload.encode()),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            return RemotePluginObservation(result=f"ERROR: Plugin {self.slug} timed out after 30s")
        except Exception as e:
            return RemotePluginObservation(result=f"ERROR: Failed to spawn plugin {self.slug}: {e}")

        if proc.returncode != 0:
            err = stderr.decode(errors="replace")[:500]
            return RemotePluginObservation(result=f"ERROR: Plugin {self.slug} exit={proc.returncode}\n{err}")

        try:
            resp = json.loads(stdout.decode())
        except json.JSONDecodeError as e:
            return RemotePluginObservation(result=f"ERROR: Plugin {self.slug} bad JSON response: {e}")

        if not resp.get("ok"):
            return RemotePluginObservation(result=f"ERROR: {resp.get('error', 'unknown error')}")

        return RemotePluginObservation(result=resp["result"])


def make_remote_tool(slug: str, tool_name: str, schema: dict, plugin_dir: Path) -> ToolDefinition:
    """Build a ToolDefinition wrapping RemotePluginExecutor for a subprocess plugin tool."""
    description = schema.get("description", tool_name)
    executor = RemotePluginExecutor(slug=slug, tool_name=tool_name, plugin_dir=plugin_dir)

    return ToolDefinition(
        description=description,
        action_type=RemotePluginAction,
        observation_type=RemotePluginObservation,
        executor=executor,
    )
