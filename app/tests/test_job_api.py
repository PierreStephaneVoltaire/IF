import asyncio

import httpx
from fastapi import FastAPI
from api import jobs, job_tools
from flow import runner
from execution.host import ConversationHost, create_app
from execution.service import ExecutionService
from execution.store import JobStore
from test_conversation_host import Session


def test_native_domain_compatibility_and_artifact_scope(monkeypatch, tmp_path):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-only")
    monkeypatch.setenv("IF_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(runner, "instruction_payload", lambda owner: {})
    monkeypatch.setattr(job_tools, "domain_operations", lambda: {"test": {"domain": "calculations", "input_schema": {"type": "object"}}})
    host = ConversationHost(tmp_path / "host", Session)
    service = ExecutionService(JobStore(str(tmp_path / "legacy.db")), httpx.ASGITransport(app=create_app(host)))
    monkeypatch.setattr(jobs, "get_execution_service", lambda: service)
    app = FastAPI()
    app.include_router(jobs.router)
    app.include_router(jobs.turn_router)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            body = {"conversation_id": "c", "payload": {"operation": "test", "arguments": {}}, "idempotency_key": "request"}
            assert (await client.post("/v1/jobs", json=body)).status_code == 401
            headers = {"X-Internal-Token": "test-only", "X-Person-Pk": "a"}
            assert (await client.post("/v1/jobs", headers=headers, json=body)).status_code == 422
            job = (await client.post("/v1/jobs", headers=headers, json={**body, "kind": "domain"})).json()
            await asyncio.sleep(0)
            path = "/v1/jobs/" + job["job_id"]
            assert (await client.get(path + "/result", headers=headers)).status_code == 202
            assert (await client.get(path, headers={**headers, "X-Person-Pk": "b"})).status_code == 404
            turn_path = "/v1/turns/" + job["job_id"]
            uploaded = (await client.put(turn_path + "/artifacts/report.txt", headers={**headers, "X-Worker-Id": "native"}, content=b"report")).json()
            assert (await client.get(path + "/artifacts/" + uploaded["artifact_id"], headers=headers)).content == b"report"
            assert (await client.post(path + "/cancel", headers=headers)).json()["status"] == "cancel_requested"
            await host.tasks[job["job_id"]]
            assert (await client.put(turn_path + "/artifacts/late.txt", headers={**headers, "X-Worker-Id": "native"}, content=b"late")).status_code == 403
        await host.close()
    asyncio.run(check())


def test_domain_dispatch_is_not_replayed_and_auxiliary_results_are_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv('INTERNAL_API_TOKEN', 'test-only')
    host = ConversationHost(tmp_path, Session)
    async def check():
        from execution.schemas import JobRequest
        job = await host.submit('alice', JobRequest(conversation_id='report', kind='domain', idempotency_key='report', payload={'domain': 'analytics', 'operation': 'report'}))
        await asyncio.sleep(0)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(host)), base_url='http://host', headers={'X-Internal-Token': 'test-only'}) as client:
            base = f'/turns/{job.job_id}'
            assert (await client.post(base + '/domain-dispatch')).json() == {'dispatch': True}
            assert (await client.post(base + '/domain-dispatch')).status_code == 409
            pending = {'operation': 'report', 'domain': 'analytics', 'status': 'needs_inference', 'execution_id': 'primary'}
            await client.post(base + '/domain-progress', json=pending)
            assert (await client.post(base + '/domain-dispatch')).json() == {'dispatch': False, 'result': pending}
            await client.post(base + '/domain-progress', json={'operation': 'domain_resume', 'domain': 'analytics', 'status': 'succeeded', 'execution_id': 'auxiliary', 'result': {'wrong': True}})
            assert 'domain_result' not in host.store.get(job.job_id).result
            await client.post(base + '/domain-progress', json={'operation': 'domain_resume', 'domain': 'analytics', 'status': 'succeeded', 'execution_id': 'primary', 'result': {'summary': 'validated'}})
            assert host.store.get(job.job_id).result['domain_result'] == {'summary': 'validated'}
        await host.close()
    asyncio.run(check())
