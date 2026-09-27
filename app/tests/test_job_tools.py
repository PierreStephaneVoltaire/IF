from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import job_tools
from execution.schemas import JobRequest
from execution.turn_store import TurnStore
from execution.service import HostError


def test_specialist_token_and_server_tool_permissions(monkeypatch, tmp_path):
    store = TurnStore(str(tmp_path / 'jobs.db'))
    job = store.start('athlete-a', JobRequest(conversation_id='c', payload={}, idempotency_key='k'))
    monkeypatch.setenv('INTERNAL_API_TOKEN', 'test-only')
    async def active_scope(job_id):
        current = store.get(job_id)
        if current.status not in {"starting", "running"}:
            raise HostError(403, "Turn scope revoked")
        return current
    monkeypatch.setattr(job_tools, 'get_execution_service', lambda: SimpleNamespace(active_scope=active_scope))
    monkeypatch.setattr(job_tools, 'schemas', lambda role: {'allowed': {'name': 'allowed', 'inputSchema': {'type': 'object', 'properties': {}}}} if role == 'reader' else {})
    app = FastAPI()
    app.include_router(job_tools.router)
    client = TestClient(app)
    path = f'/v1/turns/{job.job_id}/tools/reader/mcp'
    body = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}
    assert client.post(path, json=body).status_code == 401
    writer_token = job_tools.role_token(job.job_id, 'native', 'writer')
    assert client.post(path, headers={'Authorization': 'Bearer ' + writer_token}, json=body).status_code == 401
    headers = {'Authorization': 'Bearer ' + job_tools.role_token(job.job_id, 'native', 'reader')}
    assert client.post(path, headers=headers, json=body).json()['result']['tools'][0]['name'] == 'allowed'
    forbidden = client.post(path, headers=headers, json={**body, 'method': 'tools/call', 'params': {'name': 'write', 'arguments': {}}})
    assert forbidden.json()['result']['isError'] is True
    job.status = 'succeeded'
    store.save(job)
    assert client.post(path, headers=headers, json=body).status_code == 403


def test_coordinator_connection_requires_valid_child_scope(monkeypatch, tmp_path):
    store = TurnStore(str(tmp_path / 'jobs.db'))
    job = store.start('athlete-a', JobRequest(conversation_id='conversation-a', payload={}, idempotency_key='k'))
    monkeypatch.setenv('INTERNAL_API_TOKEN', 'test-only')
    async def active_scope(job_id):
        current = store.get(job_id)
        if current.status not in {"starting", "running"}:
            raise HostError(403, "Turn scope revoked")
        return current
    monkeypatch.setattr(job_tools, 'get_execution_service', lambda: SimpleNamespace(active_scope=active_scope))
    monkeypatch.setattr(job_tools, 'schemas', lambda role: {'allowed': {'name': 'allowed', 'inputSchema': {'type': 'object', 'properties': {}}}})
    called = {}

    async def fake_call(job, role, name, arguments):
        called.update(role=role, name=name, arguments=arguments)
        return {'ok': True}

    monkeypatch.setattr(job_tools, 'call_tool', fake_call)
    app = FastAPI()
    app.include_router(job_tools.router)
    client = TestClient(app)
    path = f'/v1/turns/{job.job_id}/tools/coordinator/mcp'
    coordinator = {'Authorization': 'Bearer ' + job_tools.role_token(job.job_id, 'native', 'coordinator')}
    body = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'allowed', 'arguments': {'__if_scope': {'role': 'reader', 'token': job_tools.role_token(job.job_id, 'native', 'reader')}}}}

    assert client.post(path, headers=coordinator, json=body).json()['result']['isError'] is False
    assert called == {'role': 'reader', 'name': 'allowed', 'arguments': {}}

    bad = {**body, 'params': {**body['params'], 'arguments': {'__if_scope': {'role': 'reader', 'token': 'forged'}}}}
    assert client.post(path, headers=coordinator, json=bad).json()['result']['isError'] is True
    assert client.post(path, headers=coordinator, json={**body, 'params': {**body['params'], 'arguments': {'__if_scope': {'role': 'coordinator', 'token': job_tools.role_token(job.job_id, 'native', 'coordinator')}}}}).json()['result']['isError'] is True

    reader_path = f'/v1/turns/{job.job_id}/tools/reader/mcp'
    reader = {'Authorization': 'Bearer ' + job_tools.role_token(job.job_id, 'native', 'reader')}
    assert client.post(reader_path, headers=reader, json=body).json()['result']['isError'] is False
    assert called['role'] == 'reader'
    cross_role = {**body, 'params': {**body['params'], 'arguments': {'__if_scope': {'role': 'writer', 'token': job_tools.role_token(job.job_id, 'native', 'writer')}}}}
    assert client.post(reader_path, headers=reader, json=cross_role).json()['result']['isError'] is True


def test_auxiliary_tools_do_not_receive_report_generation_credentials(monkeypatch, tmp_path):
    import asyncio
    calls = []
    store = TurnStore(str(tmp_path / 'turns.db'))
    job = store.start('athlete-a', JobRequest(conversation_id='report', kind='domain', idempotency_key='key', payload={'domain': 'analytics', 'operation': 'report', 'arguments': {}, 'generation_id': 'generation', 'generation_attempt': 2}))
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'status': 'succeeded', 'result': 1})
    async def bridge(method, path, **kwargs):
        return {'dispatch': True}
    monkeypatch.setenv('INTERNAL_API_TOKEN', 'test-only')
    monkeypatch.setenv('PL_PRINCIPAL_SECRET', 'principal-test-secret-never-used-outside-tests')
    monkeypatch.setattr('httpx.AsyncClient', Client)
    monkeypatch.setattr(job_tools, 'get_execution_service', lambda: SimpleNamespace(request=bridge))
    monkeypatch.setattr(job_tools, 'schemas', lambda _: {name: {'inputSchema': {'type': 'object'}} for name in ('report', 'read')})
    monkeypatch.setattr(job_tools, 'domain_operations', lambda: {'report': {'domain': 'analytics'}, 'read': {'domain': 'program'}})
    async def check():
        await job_tools.call_tool(job, 'coordinator', 'report', {})
        await job_tools.call_tool(job, 'coordinator', 'read', {})
    asyncio.run(check())
    assert calls[0]['headers']['X-IF-Generation-Id'] == 'generation'
    assert 'X-IF-Generation-Id' not in calls[1]['headers']
