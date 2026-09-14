import asyncio
import json
import os
from pathlib import Path

from openai_codex import ApprovalMode, AsyncCodex, Sandbox, TextInput, ImageInput, LocalImageInput
from openai_codex.generated.v2_all import ThreadInjectItemsResponse

from flow.codex_llm import CodexInferenceError, _config, _preflight, _trust_worker_policy
from .codex_worker import _download_inputs, _tool_config, _upload_artifacts, _worker_messages, _write_agent_config


def text_content(content):
    if isinstance(content, str):
        return content
    return "\n".join(str(item.get("text", "")) for item in content or [] if isinstance(item, dict))


def turn_input(message, payload, workspace):
    inputs = [TextInput(text_content(message.get("content")))]
    for item in message.get("content", []) if isinstance(message.get("content"), list) else []:
        if item.get("type") == "image_url":
            url = item.get("image_url", {})
            url = url if isinstance(url, str) else url.get("url", "")
            if url.startswith(("data:image/", "https://", "http://")):
                inputs.append(ImageInput(url))
    for item in payload.get("uploaded_files", []):
        path = Path(workspace) / "uploads" / item["name"]
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"} and path.is_file():
            inputs.append(LocalImageInput(str(path)))
    return inputs


def history_items(messages):
    return [{"type": "message", "role": message["role"], "content": [{"type": "output_text" if message["role"] == "assistant" else "input_text", "text": text_content(message.get("content"))}]}
            for message in messages if message.get("role") in {"user", "assistant", "system", "developer"} and text_content(message.get("content"))]


def failure(exc):
    message = str(exc)
    lower = message.lower()
    code = getattr(exc, "code", None)
    if not code:
        code = "usage_limit" if any(word in lower for word in ("usage", "rate limit", "quota")) else "auth_unavailable" if any(word in lower for word in ("unauthorized", "authentication", "token expired")) else "execution_failed"
    return {"code": code, "message": message, "retryable": False}


class NativeSession:
    def __init__(self, job, workspace):
        self.job = job
        self.workspace = workspace
        self.codex = None
        self.turn = None

    async def start(self, bind):
        payload = {**self.job.request.payload, "kind": self.job.request.kind, "job_id": self.job.job_id,
                   "owner": self.job.owner, "conversation_id": self.job.request.conversation_id,
                   "worker_id": "native", "if_api_url": os.environ["IF_API_URL"], "native": True}
        self.payload = payload
        Path(self.workspace).mkdir(parents=True, exist_ok=True)
        config = await _tool_config(payload)
        _write_agent_config(payload, self.workspace, "coordinator", config)
        await _download_inputs(payload, self.workspace)
        self.codex = AsyncCodex(_config(cwd=self.workspace))
        await self.codex.__aenter__()
        model = payload.get("model") or "gpt-5.6-sol"
        effort = payload.get("reasoning_effort", "medium")
        available = await _preflight(self.codex, model, effort)
        from .tool_policy import scope_path
        scopes = json.loads(scope_path(self.workspace).read_text())
        scopes["_models"] = available
        scope_path(self.workspace).write_text(json.dumps(scopes))
        options = dict(model=model, cwd=self.workspace, sandbox=Sandbox.workspace_write, approval_mode=ApprovalMode.deny_all,
                       config=await _trust_worker_policy(self.codex, self.workspace),
                       developer_instructions="\n\n".join(str(payload.get(key) or "") for key in ("persona", "directives", "developer_instructions")) +
                       "\nYou are Sol, IF's coordinator. Answer ordinary conversation directly. Delegate when useful to fresh named Specialists. Prefer Luna for straightforward work and Terra for analysis and review. Select a supported reasoning effort. At most two children may run concurrently. Ambient shell and filesystem tools are unavailable. Use attachment_read, import_attachment and artifact_write for scoped files, and skill_read for thinking workflows. Never submit another top-level execution from an active turn. Use domain_resume for domain continuations. Never replay a mutation after an ambiguous tool failure; surface uncertainty and require explicit retry. Available models: " + json.dumps(available))
        messages = _worker_messages({**payload, "persona": "", "directives": "", "runtime_context": ""}, payload.get("source_messages") or payload.get("messages") or [{"role": "user", "content": payload.get("prompt", "")}])
        if self.job.thread_id:
            thread = await self.codex.thread_resume(self.job.thread_id, **options)
        else:
            thread = await self.codex.thread_start(**options)
            self.job.thread_id = thread.id
            bind(self.job)
            bootstrap = payload.get("history", messages[:-1])
            items = history_items(bootstrap[-100:])
            if items:
                await self.codex._client.request("thread/inject_items", {"threadId": thread.id, "items": items}, response_model=ThreadInjectItemsResponse)
        updates = [message for message in messages if message.get("role") in {"system", "developer"}]
        if updates:
            await self.codex._client.request("thread/inject_items", {"threadId": thread.id, "items": history_items(updates)}, response_model=ThreadInjectItemsResponse)
        context = str(payload.get("runtime_context") or "")
        if context:
            await self.codex._client.request("thread/inject_items", {"threadId": thread.id, "items": history_items([{"role": "developer", "content": "Current scoped context (refresh for this turn):\n" + context}])}, response_model=ThreadInjectItemsResponse)
        latest = next((message for message in reversed(messages) if message.get("role") == "user"), {"content": ""})
        self.turn = await thread.turn(turn_input(latest, payload, self.workspace), model=model, effort=effort, output_schema=payload.get("output_schema"))
        self.job.turn_id = self.turn.id
        self.job.status = "running"
        bind(self.job)

    async def consume(self, emit):
        final = ""
        completed = None
        async for event in self.turn.stream():
            if event.method == "item/agentMessage/delta":
                emit("delta", {"delta": event.payload.delta})
            elif event.method == "item/completed":
                item = getattr(event.payload.item, "root", None)
                if getattr(item, "type", None) == "agentMessage" and getattr(getattr(item, "phase", None), "value", None) == "final_answer":
                    final = item.text
                elif getattr(item, "type", None) == "subAgentActivity":
                    emit("delegation", {"children": [item.agent_thread_id], "agent_path": item.agent_path, "kind": item.kind.value})
            elif event.method == "turn/completed":
                completed = event.payload.turn
        if completed is None:
            raise CodexInferenceError("uncertain", "Native turn disconnected; reconcile before retrying")
        if completed.error:
            raise RuntimeError(completed.error.message)
        if getattr(completed.status, "value", completed.status) != "completed":
            raise CodexInferenceError("interrupted", "Native turn interrupted; check side effects before retrying")
        if not final:
            final = final_response(completed)
        return {"content": final, "model": self.payload.get("model", "gpt-5.6-sol"), "artifacts": await _upload_artifacts(self.payload, self.workspace)}

    async def steer(self, request):
        messages = request.payload.get("source_messages") or request.payload.get("messages") or []
        latest = next((m for m in reversed(messages) if m.get("role") == "user"), {"content": request.payload.get("prompt", "")})
        await _download_inputs({**self.payload, "uploaded_files": request.payload.get("uploaded_files", [])}, self.workspace)
        return await self.turn.steer(turn_input(latest, request.payload, self.workspace))

    async def interrupt(self):
        if self.turn:
            await self.turn.interrupt()

    async def close(self):
        if self.codex:
            await self.codex.__aexit__(None, None, None)


def final_response(turn):
    for wrapped in reversed(turn.items):
        item = getattr(wrapped, "root", wrapped)
        if getattr(item, "type", None) == "agentMessage":
            return item.text
    return ""


async def recover(job, workspace):
    if not job.thread_id or not job.turn_id:
        return None
    async with AsyncCodex(_config(cwd=workspace)) as codex:
        thread = await codex._client.thread_read(job.thread_id, include_turns=True)
        turn = next((turn for turn in thread.thread.turns if turn.id == job.turn_id), None)
        if turn and getattr(turn.status, "value", turn.status) == "completed" and not turn.error:
            return {"content": final_response(turn), "model": job.request.payload.get("model", "gpt-5.6-sol"), "artifacts": [item.model_dump() for item in job.artifacts], "recovered": True}
    return None
