import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from execution import native
from execution.tool_policy import scope_path
from execution.schemas import Job, JobRequest


def test_native_resume_refreshes_system_and_explicit_specialist(monkeypatch, tmp_path):
    injected = []
    turn_inputs = []
    class Codex:
        def __init__(self, config):
            self._client = self
        async def __aenter__(self):
            return self
        async def request(self, method, params, **kwargs):
            injected.extend(params['items'])
        async def thread_resume(self, thread_id, **kwargs):
            return SimpleNamespace(id=thread_id, turn=self.turn)
        async def turn(self, inputs, **kwargs):
            turn_inputs.extend(inputs)
            return SimpleNamespace(id='new-turn')
    async def noop(*args):
        return {}
    monkeypatch.setenv('IF_API_URL', 'http://test')
    monkeypatch.setattr(native, 'AsyncCodex', Codex)
    monkeypatch.setattr(native, '_tool_config', noop)
    monkeypatch.setattr(native, '_download_inputs', noop)
    monkeypatch.setattr(native, '_preflight', noop)
    monkeypatch.setattr(native, '_trust_worker_policy', noop)
    monkeypatch.setattr(native, '_write_agent_config', lambda payload, workspace, *args: scope_path(workspace).write_text('{}'))
    request = JobRequest(conversation_id='c', idempotency_key='key', payload={'specialist': 'writer', 'history': [{'role': 'system', 'content': 'OLD'}], 'messages': [{'role': 'system', 'content': 'NEW'}, {'role': 'user', 'content': 'write'}]})
    job = Job(job_id='job', owner='alice', request=request, status='starting', thread_id='existing', created_at=0, updated_at=0)
    asyncio.run(native.NativeSession(job, str(tmp_path)).start(lambda job: None))
    text = json.dumps(injected)
    assert 'NEW' in text and 'named Specialist: writer' in text and 'OLD' not in text
    assert turn_inputs[0].text == 'write'
    assert job.thread_id == 'existing'
