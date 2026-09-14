from __future__ import annotations

import json
import os
import mimetypes
import shutil
import hashlib
from urllib.parse import quote
from pathlib import Path
from dataclasses import replace

import httpx
from typing import Any

from flow.codex_llm import CodexInferenceError
from execution.tool_policy import scope_path


async def _tool_config(payload: dict[str, Any]) -> dict[str, Any]:
    base = payload.get("if_api_url")
    job_id = payload.get("job_id")
    worker_id = payload.get("worker_id")
    token = os.environ.get("INTERNAL_API_TOKEN")
    if not all((base, job_id, worker_id, token)):
        raise CodexInferenceError("scope_unavailable", "Worker requires authenticated turn scope")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{str(base).rstrip('/')}/v1/turns/{job_id}/tool-config", headers={"X-Internal-Token": str(token), "X-Worker-Id": str(worker_id)})
        response.raise_for_status()
        return response.json()


def _worker_messages(payload: dict[str, Any], messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source = payload.get("source_messages") or messages
    if payload.get("kind") == "domain":
        source = [{"role": "user", "content": "Execute the domain operation " + str(payload["operation"]) + " in domain " + str(payload["domain"]) + " with arguments " + json.dumps(payload["arguments"]) + ". Call its deterministic tool. If the result needs_inference, delegate the returned messages and output schema to a native Specialist child, then call domain_resume with domain, execution_id, challenge_id and the child response. Poll running executions using domain_resume without challenge_id. Repeat until succeeded. Return the final result as JSON. Never enqueue another top-level job."}]
    context = str(payload.get("runtime_context") or "").strip()
    persona = str(payload.get("persona") or "").strip()
    directives = str(payload.get("directives") or "").strip()
    prefix = "\n\n".join(part for part in (persona, directives, context) if part)
    if payload.get("specialist") not in {None, "general", "coordinator"}:
        prefix += "\nDelegate this request to the named Specialist: " + str(payload["specialist"])
    if not prefix:
        return source
    return [{"role": "system", "content": prefix}, *source]


def _write_agent_config(payload: dict[str, Any], workspace: str, role: str, tool_config: dict[str, Any]) -> None:
    from agent.codex_specialists import load_codex_specialists, render_specialist_toml

    root = Path(__file__).resolve().parents[3]
    output = Path(workspace) / ".codex" / "agents"
    output.mkdir(parents=True, exist_ok=True)
    for metadata in (".git", ".agents"):
        (Path(workspace) / metadata).mkdir(exist_ok=True)
    directives = payload.get("specialist_directives", {})
    for slug, specialist in load_codex_specialists(root, athlete=str(payload.get("athlete") or payload.get("owner") or ""), models={"code_reviewer": "gpt-5.6-terra"}).items():
        config = tool_config.get(slug)
        if not config:
            raise CodexInferenceError("scope_unavailable", f"Missing scoped configuration for {slug}")
        path = output / f"{slug}.toml"
        path.write_text(render_specialist_toml(replace(specialist, tools=tuple(config["tools"])), workspace, payload["job_id"], mcp_endpoints={"if_tools": config["url"]}, mcp_credentials={"if_tools": config["token"]}, directive_text=directives.get(slug, "")))
        path.chmod(0o600)
    config = tool_config["coordinator"]
    settings = Path(workspace) / ".codex" / "config.toml"
    settings.write_text('[mcp_servers.if_tools]\ndefault_tools_approval_mode = "approve"\nurl = ' + json.dumps(config['url']) + '\nenabled_tools = ' + json.dumps(config['tools']) + '\n[mcp_servers.if_tools.http_headers]\nAuthorization = ' + json.dumps('Bearer ' + config['token']) + '\n')
    settings.chmod(0o600)
    skills = root / "skills"
    target = Path(workspace) / ".agents" / "skills"
    if skills.is_dir():
        shutil.copytree(skills, target, dirs_exist_ok=True)
    import shlex
    import sys
    from execution.tool_policy import __file__ as policy_path

    scopes = scope_path(workspace)
    scopes.write_text(json.dumps({slug: {"tools": config["tools"], "token": config["token"]} for slug, config in tool_config.items()}))
    scopes.chmod(0o600)
    (output.parent / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": shlex.join([sys.executable, policy_path]), "timeout": 5}]}]}}))


async def _upload_artifacts(payload, workspace):
    artifacts = []
    names = set()
    async with httpx.AsyncClient(timeout=30) as client:
        for path in Path(workspace).rglob("*"):
            if not path.is_file() or path.is_symlink() or ".codex" in path.parts or ".agents" in path.parts or ".git" in path.parts or "uploads" in path.relative_to(workspace).parts:
                continue
            if path.stat().st_size > 25 * 1024 * 1024:
                continue
            relative = path.relative_to(workspace)
            name = path.name
            if name in names:
                name = relative.as_posix().replace("/", "__")
            if name in names:
                name = f"{path.stem}-{hashlib.sha256(relative.as_posix().encode()).hexdigest()[:8]}{path.suffix}"
            names.add(name)
            response = await client.put(f"{payload['if_api_url']}/v1/turns/{payload['job_id']}/artifacts/{quote(name, safe='')}", content=path.read_bytes(), headers={"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"], "X-Worker-Id": payload["worker_id"], "Content-Type": mimetypes.guess_type(name)[0] or "application/octet-stream"})
            response.raise_for_status()
            artifacts.append(response.json())
    return artifacts


async def _download_inputs(payload, workspace):
    async with httpx.AsyncClient(timeout=30) as client:
        for item in payload.get("uploaded_files", []):
            name = item["name"]
            if Path(name).name != name or name in {".", ".."}:
                raise CodexInferenceError("invalid_input", "Invalid input artifact name")
            response = await client.get(f"{payload['if_api_url']}/v1/turns/{payload['job_id']}/inputs/{item['artifact_id']}", headers={"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"], "X-Worker-Id": payload["worker_id"]})
            response.raise_for_status()
            target = Path(workspace) / "uploads" / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(response.content)


