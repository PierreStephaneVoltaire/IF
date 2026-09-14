from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from files import FileRef, strip_files_line
from config import PROJECT_ROOT, IF_USER_PK
from execution.schemas import JobRequest
from execution.service import get_execution_service
from storage.factory import get_directive_store
from agent.specialists import list_specialists
from .context import build_runtime_context
from .session_dirs import resolve_session_dir
from .history import write_history, _load_events


@dataclass
class FlowResult:
    content: str
    file_refs: list[FileRef] = field(default_factory=list)
    attachments: list[dict[str, Any]] = field(default_factory=list)


def conversation_scope(owner, conversation):
    if owner == IF_USER_PK:
        return conversation
    return "person_" + hashlib.sha256((owner + "\0" + conversation).encode()).hexdigest()


def _run_model(request_data):
    model = request_data.get("coordinator_model") or request_data.get("model")
    return model if model in {"gpt-5.6-sol", "gpt-6-astra"} else "gpt-5.6-sol"


def instruction_payload(owner):
    directives = get_directive_store(owner)
    directives.load()
    persona_path = PROJECT_ROOT / "app" / "main_system_prompt.txt"
    if not persona_path.exists():
        persona_path = PROJECT_ROOT / "main_system_prompt.txt"
    return {"persona": persona_path.read_text(), "directives": directives.format_directives(directives.get_for_subagent(["core"])),
            "specialist_directives": {spec.slug: directives.format_directives(directives.get_for_subagent(spec.directive_types)) for spec in list_specialists()}}


def prepare_conversation(request_data, context_id, cache_key, webhook=None):
    owner = request_data.get("_owner") or IF_USER_PK
    scope = conversation_scope(owner, context_id)
    messages = request_data.get("messages") or []
    session_dir = resolve_session_dir(request_data, webhook, cache_key)
    previous = list(_load_events(session_dir / "history.json").values())
    reset_marker = session_dir / ".thread-reset"
    if reset_marker.exists():
        previous = [event for event in previous if event.get("created_at", "") > reset_marker.read_text()]
    write_history(session_dir, messages, history_events=request_data.get("_history_events"))
    context = build_runtime_context(owner=owner, messages=messages, context_id=scope, cache_key=scope, session_dir=session_dir, uploaded_files=request_data.get("_uploaded_files"), thinking_mode_requested=bool(request_data.get("_thinking_mode_requested")), self_aware=bool(getattr(webhook, "self_aware", False)))
    uploads = []
    upload_names = set()
    for item in request_data.get("_uploaded_files", []):
        source = Path(item.get("local_path", ""))
        if not source.is_file() or not source.resolve().is_relative_to(session_dir.resolve()) or source.stat().st_size > 25 * 1024 * 1024:
            continue
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        target = Path(os.getenv("IF_ARTIFACT_DIR", "./data/artifacts")) / "inputs" / digest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        name = source.name if source.name not in upload_names else f"{source.stem}-{digest[:8]}{source.suffix}"
        upload_names.add(name)
        uploads.append({"artifact_id": digest, "name": name})
        context = context.replace(str(source), "uploads/" + name)
    payload = {
        "model": _run_model(request_data), "reasoning_effort": request_data.get("reasoning_effort", "medium"),
        "messages": messages, "output_schema": request_data.get("output_schema"), "history": previous if reset_marker.exists() else previous or messages[:-1], "history_path": str(session_dir / "history.json"),
        "runtime_context": context, "memory_scope": scope, "uploaded_files": uploads,
        **instruction_payload(owner),
        **({"delivery": request_data["_delivery"]} if request_data.get("_delivery") else {}),
        **({"specialist": request_data["_specialist"]} if request_data.get("_specialist") else {}),
    }
    return owner, JobRequest(conversation_id=context_id, kind="conversation", payload=payload, idempotency_key=request_data.get("_idempotency_key") or uuid.uuid4().hex), session_dir


def materialize_result(result, session_dir):
    content, _ = strip_files_line(result.get("content", ""))
    refs = []
    for artifact in result.get("artifacts", []):
        source = Path(os.getenv("IF_ARTIFACT_DIR", "./data/artifacts")) / result["job_id"] / artifact["artifact_id"]
        if source.is_file() and Path(artifact["name"]).name == artifact["name"]:
            target = session_dir / "artifacts" / artifact["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            refs.append(FileRef(path=str(target), description=artifact["name"]))
    return FlowResult(content=content, file_refs=refs)


async def run_if_flow(*, request_data, http_client, cache_key, context_id, webhook=None):
    owner, request, session_dir = await asyncio.to_thread(prepare_conversation, request_data, context_id, cache_key, webhook)
    result = await get_execution_service().submit_and_wait(owner, request, emit=request_data.get("_emit"))
    write_history(session_dir, [{"id": result["job_id"], "role": "assistant", "content": result.get("content", "")}])
    return materialize_result(result, session_dir)


async def run_specialist_flow(*, specialist_slug, task, http_client, session_dir, context_id="", cache_key="", selected_model=None, owner=IF_USER_PK):
    request_data = {"_owner": owner, "messages": [{"role": "user", "content": task}], "_specialist": specialist_slug,
                    "conversation_id": context_id or cache_key or uuid.uuid4().hex, "model": selected_model}
    result = await run_if_flow(request_data=request_data, http_client=http_client, cache_key=cache_key, context_id=request_data["conversation_id"])
    return result.content, result.file_refs


def materialize_file_ref(ref: FileRef, cache_key: str) -> dict[str, Any] | None:
    path = Path(ref.path)
    if not path.is_file():
        return None
    from .session_dirs import safe_segment
    target_dir = Path(tempfile.gettempdir()) / "if-attachments" / safe_segment(cache_key)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    try:
        if path.resolve() != target.resolve():
            shutil.copy2(path, target)
    except OSError:
        return None
    return {"filename": path.name, "url": f"/files/sandbox/{cache_key}/{path.name}", "local_path": str(target), "content_type": "application/octet-stream", "description": ref.description}
