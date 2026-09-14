from __future__ import annotations

import asyncio
import logging
import uuid
import os
import json
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

ToolDispatcher = Callable[[str, dict[str, Any]], Awaitable[str]]


class CodexInferenceError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


def _config(overrides: tuple[str, ...] = (), cwd: str | None = None) -> CodexConfig:
    from openai_codex import CodexConfig

    return CodexConfig(
        cwd=cwd,
        env={key: "" if key.startswith(("AWS_", "OPENAI_", "OPENROUTER_", "LLM_")) or key in {"INTERNAL_API_TOKEN", "CODEX_API_KEY"} else value for key, value in os.environ.items()},
        config_overrides=overrides + (('projects={' + json.dumps(cwd) + '={trust_level="trusted"}}',) if cwd else ()) + (
            "forced_login_method=\"chatgpt\"",
            "agents.enabled=true",
            "features.multi_agent=true",
            "features.hooks=true",
            "features.shell_tool=false",
            "features.apps=false",
            "features.plugins=false",
            "features.memory_tool=false",
            "features.request_permissions_tool=false",
            "features.use_legacy_landlock=true",
            "sandbox_workspace_write.exclude_tmpdir_env_var=true",
            "sandbox_workspace_write.exclude_slash_tmp=true",
            'project_root_markers=[".codex"]',
            "features.multi_agent_v2=true",
            "agents.max_concurrent_threads_per_session=2",
        )
    )


async def _preflight(codex: AsyncCodex, model: str, effort: str | None = None) -> dict[str, list[str]]:
    try:
        account = await codex.account()
    except Exception as exc:
        raise CodexInferenceError("auth_unavailable", "Codex authentication is unavailable") from exc
    account_type = getattr(getattr(getattr(account, "account", None), "root", None), "type", None)
    if getattr(account_type, "value", account_type) != "chatgpt":
        raise CodexInferenceError("subscription_required", "Codex requires ChatGPT subscription authentication")
    try:
        models = await codex.models()
    except Exception as exc:
        raise CodexInferenceError("models_unavailable", "Codex model catalog is unavailable") from exc
    available = {entry.model: [getattr(option.reasoning_effort, "value", option.reasoning_effort) for option in entry.supported_reasoning_efforts] for entry in models.data if not entry.hidden}
    if model not in available:
        raise CodexInferenceError("model_unavailable", f"Codex model is unavailable: {model}")
    if effort is not None:
        entry = next(entry for entry in models.data if entry.model == model)
        supported = {getattr(option.reasoning_effort, "value", option.reasoning_effort) for option in entry.supported_reasoning_efforts}
        if effort not in supported:
            raise CodexInferenceError("reasoning_unavailable", f"{model} does not support {effort} reasoning")
    return available


async def call_codex_chat(
    *,
    http_client: Any = None,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_dispatcher: ToolDispatcher | None = None,
    max_tool_rounds: int = 8,
    cwd: str | None = None,
    developer_instructions: str | None = None,
    sandbox: Any = None,
    approval_mode: Any = None,
    owner: str = "operator",
    conversation_id: str | None = None,
    emit: Callable[[str, dict[str, Any]], Awaitable[None] | None] | None = None,
    job_payload: dict[str, Any] | None = None,
    result_out: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    priority: int = 0,
    output_schema: dict[str, Any] | None = None,
    config_overrides: tuple[str, ...] = (),
) -> str:
    del http_client
    if tools or tool_dispatcher:
        raise CodexInferenceError("tools_unavailable", "Tools must be configured on the scoped worker runtime")
    from execution.schemas import JobRequest
    from execution.service import get_execution_service

    from flow.runner import instruction_payload
    instructions = await asyncio.to_thread(instruction_payload, owner)
    result = await get_execution_service().submit_and_wait(
        owner,
        JobRequest(
            conversation_id="inference:" + (conversation_id or uuid.uuid4().hex),
            kind="inference",
            payload={**instructions, "model": model, "messages": messages, "output_schema": output_schema, "cwd": cwd, "developer_instructions": developer_instructions, "sandbox": getattr(sandbox, "value", sandbox), "approval_mode": getattr(approval_mode, "value", approval_mode), **(job_payload or {})},
            priority=priority,
            idempotency_key=idempotency_key or uuid.uuid4().hex,
        ),
        emit=emit,
    )
    if result_out is not None:
        result_out.update(result)
    return str(result.get("content") or "")


async def _trust_worker_policy(codex, cwd):
    from pathlib import Path
    from openai_codex.generated.v2_all import HooksListResponse
    from execution.tool_policy import scope_path

    if not cwd or not scope_path(cwd).exists():
        return None
    from execution.tool_policy import __file__ as policy_path
    import shlex
    import sys

    expected = shlex.join([sys.executable, policy_path])
    response = await codex._client.request("hooks/list", {"cwds": [cwd]}, response_model=HooksListResponse)
    matches = [hook.root for entry in response.data for hook in entry.hooks if getattr(hook.root, "command", None) == expected and str(hook.root.source_path.root) == str(Path(cwd) / ".codex/hooks.json")]
    if len(matches) != 1:
        raise CodexInferenceError("scope_unavailable", "Worker tool policy was not loaded")
    hook = matches[0]
    return {"hooks": {"state": {hook.key: {"trusted_hash": hook.current_hash, "enabled": True}}}}
