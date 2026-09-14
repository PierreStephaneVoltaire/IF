import asyncio
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from execution import codex_worker
from execution.tool_policy import evaluate
from agent.codex_specialists import load_codex_specialists


def test_worker_uploads_duplicate_basenames_with_distinct_names(monkeypatch, tmp_path):
    uploaded = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def put(self, url, **_):
            uploaded.append(url.rsplit("/", 1)[-1])
            return Response()

    (tmp_path / "first").mkdir()
    (tmp_path / "second").mkdir()
    (tmp_path / "first" / "report.txt").write_text("first")
    (tmp_path / "second" / "report.txt").write_text("second")
    (tmp_path / "report #1.txt").write_text("third")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-only")
    monkeypatch.setattr(codex_worker.httpx, "AsyncClient", lambda **_: Client())

    asyncio.run(codex_worker._upload_artifacts({"if_api_url": "http://main", "job_id": "job", "worker_id": "worker"}, tmp_path))

    assert len(set(uploaded)) == 3
    assert "report%20%231.txt" in uploaded


def test_scoped_mcp_policy_injects_specialist_token():
    result = evaluate(
        {
            "tool_name": "mcp__if_tools__get_current_date",
            "agent_id": "child",
            "agent_type": "code_reviewer",
            "tool_input": {},
        },
        {"code_reviewer": {"tools": ["get_current_date"], "token": "scoped-token"}},
    )

    assert result["hookSpecificOutput"]["updatedInput"]["__if_scope"]["token"] == "scoped-token"


def test_root_hook_denies_ambient_filesystem_and_records_its_decision(tmp_path):
    workspace = tmp_path / "workspace"
    policy_dir = workspace / ".codex"
    policy_dir.mkdir(parents=True)
    codex_worker.scope_path(workspace).write_text("{}")
    event = {"cwd": str(workspace), "tool_name": "apply_patch", "tool_input": {"command": "*** Begin Patch"}}

    result = subprocess.run([sys.executable, str(Path(evaluate.__globals__["__file__"]))], input=json.dumps(event), text=True, capture_output=True, check=True)

    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    audit = json.loads((policy_dir / "policy-audit.jsonl").read_text())
    assert audit["tool_name"] == "apply_patch"
    assert audit["decision"] == "deny"




def test_native_specialist_configuration_preserves_distinct_scopes(tmp_path):
    root = Path(__file__).resolve().parents[2]
    roles = ['coordinator', *load_codex_specialists(root)]
    tools = {role: {'url': f'http://main/turns/j/{role}/mcp', 'token': role, 'tools': ['get_current_date']} for role in roles}
    codex_worker._write_agent_config({'job_id': 'j'}, str(tmp_path), 'coordinator', tools)
    configs = list((tmp_path / '.codex/agents').glob('*.toml'))
    assert len(configs) == len(roles) - 1
    assert all(tomllib.loads(path.read_text())['features']['shell_tool'] is False for path in configs)
    scopes = codex_worker.scope_path(tmp_path)
    assert scopes.stat().st_mode & 0o777 == 0o600
    assert json.loads(scopes.read_text())['code_reviewer']['token'] == 'code_reviewer'
    with pytest.raises(codex_worker.CodexInferenceError, match='authenticated turn scope'):
        asyncio.run(codex_worker._tool_config({}))
