"""Plan file tools for shared context between main agent and subagents.

Minimal tools (append/read/list/grep) for collaborative plan markdown files
stored under `{sandbox}/plans/`. State is convention-based:

- `- [ ]` open
- `- [x]` done
- `- [!]` needs adjustment (subagent flagged it)
- `- [?]` blocked / clarification needed

The same `plans/` directory is used by `deep_think`, so plans produced by the
thinking subagent appear alongside plans written by the main agent and other
specialists.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Sequence

from pydantic import Field
from rich.text import Text

from openhands.sdk import (
    Action,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor

from agent.tools.base import TextObservation
from app_sandbox import get_local_sandbox

logger = logging.getLogger(__name__)

PLANS_SUBDIR = "plans"
DEFAULT_READ_MAX_LINES = 500
TRAVERSAL_RE = re.compile(r"(^|/)\.\.(/|$)")


# =============================================================================
# Path resolution
# =============================================================================

def _plans_dir(chat_id: str) -> Path:
    """Resolve {sandbox}/plans/ for a conversation, creating it if missing."""
    workdir = Path(get_local_sandbox().get_working_dir(chat_id))
    plans = workdir / PLANS_SUBDIR
    plans.mkdir(parents=True, exist_ok=True)
    return plans


def _resolve_plan_path(chat_id: str, path: str) -> Path:
    """Resolve a user-supplied plan path under the plans directory.

    - Strips leading slashes so absolute-looking paths stay inside plans/.
    - Rejects `..` traversal.
    - Auto-appends `.md` if no extension is present.
    """
    raw = (path or "").strip().lstrip("/")
    if not raw:
        raise ValueError("path is required")
    if TRAVERSAL_RE.search(raw):
        raise ValueError("path must not contain '..' traversal")
    if "." not in Path(raw).name:
        raw = f"{raw}.md"
    resolved = (_plans_dir(chat_id) / raw).resolve()
    plans_root = _plans_dir(chat_id).resolve()
    if plans_root not in resolved.parents and resolved != plans_root:
        raise ValueError("path escapes the plans directory")
    return resolved


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# plan_append
# =============================================================================

class PlanAppendAction(Action):
    path: str = Field(
        description="Plan file path relative to plans/ (e.g. 'supplement-bucket' or 'subtasks/step-2.md'). '.md' is auto-appended if missing."
    )
    content: str = Field(description="Markdown content to append.")
    prepend_timestamp: bool = Field(
        default=True,
        description="If true, prefix the appended block with a UTC timestamp line.",
    )


class PlanAppendObservation(TextObservation):
    path: str = Field(default="", description="Absolute path written to.")
    bytes_written: int = Field(default=0, description="Bytes written in this append.")

    @property
    def visualize(self) -> Text:
        t = Text()
        t.append("plan_append ", style="bold green")
        t.append(f"{self.path} ", style="cyan")
        t.append(f"(+{self.bytes_written} bytes)", style="dim")
        return t


class PlanAppendExecutor(ToolExecutor[PlanAppendAction, PlanAppendObservation]):
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(self, action: PlanAppendAction, conversation: Any = None) -> PlanAppendObservation:
        try:
            target = _resolve_plan_path(self.chat_id, action.path)
            target.parent.mkdir(parents=True, exist_ok=True)

            block = action.content
            if action.prepend_timestamp:
                block = f"\n<!-- {_timestamp()} -->\n{block}"
            if not block.endswith("\n"):
                block += "\n"

            existed = target.exists()
            with target.open("a", encoding="utf-8") as f:
                f.write(block)

            msg = f"{'Appended' if existed else 'Created'} {target} (+{len(block)} bytes)"
            return PlanAppendObservation.from_text(
                msg, path=str(target), bytes_written=len(block)
            )
        except Exception as e:
            logger.warning(f"[planfiles] append failed: {e}")
            return PlanAppendObservation.from_text(
                f"ERROR: {type(e).__name__}: {e}", is_error=True
            )


class PlanAppendTool(ToolDefinition[PlanAppendAction, PlanAppendObservation]):
    @classmethod
    def create(cls, conv_state=None, chat_id: str = "", **params) -> Sequence["PlanAppendTool"]:
        return [cls(
            description=(
                "Append markdown content to a plan file under {sandbox}/plans/. "
                "Creates the file if missing. Use checkbox state convention: "
                "'- [ ]' open, '- [x]' done, '- [!]' needs adjustment, '- [?]' blocked. "
                "Subagents should emit '- [!]' entries to signal the main agent that a "
                "step needs revisiting. Timestamps are added automatically by default."
            ),
            action_type=PlanAppendAction,
            observation_type=PlanAppendObservation,
            executor=PlanAppendExecutor(chat_id=chat_id),
        )]


# =============================================================================
# plan_read
# =============================================================================

class PlanReadAction(Action):
    path: str = Field(
        description="Plan file path relative to plans/. '.md' is auto-appended if missing."
    )
    max_lines: int = Field(
        default=DEFAULT_READ_MAX_LINES,
        description="Maximum lines to return before truncating with an ellipsis marker.",
    )


class PlanReadObservation(TextObservation):
    path: str = Field(default="", description="Absolute path read.")
    truncated: bool = Field(default=False, description="True if output was truncated.")

    @property
    def visualize(self) -> Text:
        text_str = "".join(
            item.text for item in self.content if hasattr(item, "text")
        )
        t = Text()
        t.append("plan_read ", style="bold blue")
        t.append(f"{self.path}", style="cyan")
        if self.truncated:
            t.append(" [truncated]", style="yellow")
        t.append("\n")
        t.append(text_str if text_str.strip() else "[empty]")
        return t


class PlanReadExecutor(ToolExecutor[PlanReadAction, PlanReadObservation]):
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(self, action: PlanReadAction, conversation: Any = None) -> PlanReadObservation:
        try:
            target = _resolve_plan_path(self.chat_id, action.path)
            if not target.exists():
                return PlanReadObservation.from_text(
                    f"ERROR: plan file not found: {target.name}",
                    path=str(target),
                    is_error=True,
                )
            lines = target.read_text(encoding="utf-8").splitlines()
            cap = max(1, int(action.max_lines or DEFAULT_READ_MAX_LINES))
            truncated = len(lines) > cap
            body = "\n".join(lines[:cap])
            if truncated:
                body += f"\n... [{len(lines) - cap} more lines truncated]"
            return PlanReadObservation.from_text(
                body, path=str(target), truncated=truncated
            )
        except Exception as e:
            logger.warning(f"[planfiles] read failed: {e}")
            return PlanReadObservation.from_text(
                f"ERROR: {type(e).__name__}: {e}", is_error=True
            )


class PlanReadTool(ToolDefinition[PlanReadAction, PlanReadObservation]):
    @classmethod
    def create(cls, conv_state=None, chat_id: str = "", **params) -> Sequence["PlanReadTool"]:
        return [cls(
            description=(
                "Read a plan file under {sandbox}/plans/. "
                "Returns full content up to max_lines; longer files are truncated with an ellipsis marker. "
                "Use to check the current state of an in-progress plan, including any '- [!]' entries "
                "flagged by subagents."
            ),
            action_type=PlanReadAction,
            observation_type=PlanReadObservation,
            executor=PlanReadExecutor(chat_id=chat_id),
        )]


# =============================================================================
# plan_list
# =============================================================================

class PlanListAction(Action):
    pass


class PlanListObservation(TextObservation):
    count: int = Field(default=0, description="Number of plan files found.")

    @property
    def visualize(self) -> Text:
        text_str = "".join(
            item.text for item in self.content if hasattr(item, "text")
        )
        t = Text()
        t.append(f"plan_list ({self.count} files)\n", style="bold magenta")
        t.append(text_str if text_str.strip() else "[empty]")
        return t


class PlanListExecutor(ToolExecutor[PlanListAction, PlanListObservation]):
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(self, action: PlanListAction, conversation: Any = None) -> PlanListObservation:
        try:
            root = _plans_dir(self.chat_id)
            entries = []
            for p in sorted(root.rglob("*.md")):
                if not p.is_file():
                    continue
                rel = p.relative_to(root).as_posix()
                try:
                    st = p.stat()
                except OSError:
                    continue
                mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                entries.append(f"{rel}\t{st.st_size} bytes\t{mtime}")

            if not entries:
                return PlanListObservation.from_text(
                    "(no plan files yet)", count=0
                )
            return PlanListObservation.from_text(
                "\n".join(entries), count=len(entries)
            )
        except Exception as e:
            logger.warning(f"[planfiles] list failed: {e}")
            return PlanListObservation.from_text(
                f"ERROR: {type(e).__name__}: {e}", is_error=True
            )


class PlanListTool(ToolDefinition[PlanListAction, PlanListObservation]):
    @classmethod
    def create(cls, conv_state=None, chat_id: str = "", **params) -> Sequence["PlanListTool"]:
        return [cls(
            description=(
                "List all plan files under {sandbox}/plans/ with size and last-modified time. "
                "Use to discover which plans exist before reading or grepping them."
            ),
            action_type=PlanListAction,
            observation_type=PlanListObservation,
            executor=PlanListExecutor(chat_id=chat_id),
        )]


# =============================================================================
# plan_grep
# =============================================================================

class PlanGrepAction(Action):
    pattern: str = Field(description="Regex pattern to search for across plan files.")
    path: str = Field(
        default="",
        description="Optional: limit search to a single plan file. Empty = search all plans.",
    )


class PlanGrepObservation(TextObservation):
    matches: int = Field(default=0, description="Total matching lines.")

    @property
    def visualize(self) -> Text:
        text_str = "".join(
            item.text for item in self.content if hasattr(item, "text")
        )
        t = Text()
        t.append(f"plan_grep ({self.matches} matches)\n", style="bold yellow")
        t.append(text_str if text_str.strip() else "[no matches]")
        return t


class PlanGrepExecutor(ToolExecutor[PlanGrepAction, PlanGrepObservation]):
    def __init__(self, chat_id: str):
        self.chat_id = chat_id

    def __call__(self, action: PlanGrepAction, conversation: Any = None) -> PlanGrepObservation:
        try:
            try:
                regex = re.compile(action.pattern)
            except re.error as e:
                return PlanGrepObservation.from_text(
                    f"ERROR: invalid regex: {e}", is_error=True
                )

            root = _plans_dir(self.chat_id)
            if action.path:
                targets = [_resolve_plan_path(self.chat_id, action.path)]
                if not targets[0].exists():
                    return PlanGrepObservation.from_text(
                        f"ERROR: plan file not found: {targets[0].name}", is_error=True
                    )
            else:
                targets = [p for p in sorted(root.rglob("*.md")) if p.is_file()]

            hits: List[str] = []
            for p in targets:
                try:
                    lines = p.read_text(encoding="utf-8").splitlines()
                except OSError:
                    continue
                rel = p.relative_to(root).as_posix()
                for i, line in enumerate(lines, start=1):
                    if regex.search(line):
                        hits.append(f"{rel}:{i}:{line}")

            if not hits:
                return PlanGrepObservation.from_text("(no matches)", matches=0)
            return PlanGrepObservation.from_text(
                "\n".join(hits), matches=len(hits)
            )
        except Exception as e:
            logger.warning(f"[planfiles] grep failed: {e}")
            return PlanGrepObservation.from_text(
                f"ERROR: {type(e).__name__}: {e}", is_error=True
            )


class PlanGrepTool(ToolDefinition[PlanGrepAction, PlanGrepObservation]):
    @classmethod
    def create(cls, conv_state=None, chat_id: str = "", **params) -> Sequence["PlanGrepTool"]:
        return [cls(
            description=(
                "Regex-search across plan files under {sandbox}/plans/. "
                "Returns matching lines as 'file:lineno:content'. "
                "Use to find outstanding work (e.g. pattern '- \\[!\\]' for adjustment flags, "
                "'- \\[ \\]' for open items) or cross-reference steps between plans."
            ),
            action_type=PlanGrepAction,
            observation_type=PlanGrepObservation,
            executor=PlanGrepExecutor(chat_id=chat_id),
        )]


# =============================================================================
# Registration
# =============================================================================

register_tool("PlanAppendTool", PlanAppendTool)
register_tool("PlanReadTool", PlanReadTool)
register_tool("PlanListTool", PlanListTool)
register_tool("PlanGrepTool", PlanGrepTool)


def get_planfile_tools(chat_id: str) -> List[Tool]:
    """Get plan-file tool specs for Agent initialization.

    Args:
        chat_id: Conversation ID for sandbox scoping.

    Returns:
        List of Tool specs bound to the conversation's plans directory.
    """
    return [
        Tool(name="PlanAppendTool", params={"chat_id": chat_id}),
        Tool(name="PlanReadTool", params={"chat_id": chat_id}),
        Tool(name="PlanListTool", params={"chat_id": chat_id}),
        Tool(name="PlanGrepTool", params={"chat_id": chat_id}),
    ]


# =============================================================================
# Non-agentic dispatch helpers
# =============================================================================

def _execute_plan_tool_sync(tool_name: str, chat_id: str, args: dict) -> str:
    """Dispatch a plan-file tool by snake_case name for non-agentic specialists.

    Used by the JSON-schema specialist loop in subagents._run_subagent.
    """
    try:
        if tool_name == "plan_append":
            action = PlanAppendAction(
                path=args.get("path", ""),
                content=args.get("content", ""),
                prepend_timestamp=bool(args.get("prepend_timestamp", True)),
            )
            obs = PlanAppendExecutor(chat_id=chat_id)(action)
        elif tool_name == "plan_read":
            action = PlanReadAction(
                path=args.get("path", ""),
                max_lines=int(args.get("max_lines", DEFAULT_READ_MAX_LINES)),
            )
            obs = PlanReadExecutor(chat_id=chat_id)(action)
        elif tool_name == "plan_list":
            obs = PlanListExecutor(chat_id=chat_id)(PlanListAction())
        elif tool_name == "plan_grep":
            action = PlanGrepAction(
                pattern=args.get("pattern", ""),
                path=args.get("path", ""),
            )
            obs = PlanGrepExecutor(chat_id=chat_id)(action)
        else:
            return f"Unknown plan tool: {tool_name}"
        return "".join(c.text for c in obs.content if hasattr(c, "text"))
    except Exception as e:
        logger.warning(f"[planfiles] sync dispatch failed for {tool_name}: {e}")
        return f"ERROR: {type(e).__name__}: {e}"


PLAN_TOOL_NAMES = {"plan_append", "plan_read", "plan_list", "plan_grep"}
