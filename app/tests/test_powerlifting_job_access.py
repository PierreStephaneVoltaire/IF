import asyncio

import httpx
from fastapi import FastAPI, HTTPException

from api import jobs
from api.powerlifting_principal import principal_token
from execution.schemas import Job, JobRequest


def domain_job(owner="original-actor", operation="analytics.markdown", status="succeeded"):
    request = JobRequest(
        conversation_id="powerlifting:athlete-a",
        kind="domain",
        idempotency_key="request",
        payload={"domain": "analytics", "operation": operation, "athlete": "athlete-a", "arguments": {"pk": "athlete-a"}},
    )
    return Job(job_id="job-1", owner=owner, request=request, status=status, created_at=0, updated_at=0)


def test_domain_job_read_is_bound_to_current_actor_and_cached_permission(monkeypatch, tmp_path):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-only")
    monkeypatch.setenv("PL_PRINCIPAL_SECRET", "principal-test-secret-never-used-outside-tests")
    job = domain_job()
    job.request.payload['instructions'] = 'private instructions'
    job.result = {'domain_result': {'summary': 'report'}, 'messages': ['private transcript']}

    class Service:
        async def get(self, job_id, owner=None):
            assert job_id == job.job_id
            return job

    checked = []

    async def check(operation, arguments, person, athlete, principal):
        checked.append((operation, arguments, person, athlete))

    monkeypatch.setattr(jobs, "get_execution_service", lambda: Service())
    monkeypatch.setattr(jobs, "_check_profile_access", check)
    app = FastAPI()
    app.include_router(jobs.router)

    async def run():
        token = principal_token("current-actor", "athlete-a", jobs.DOMAIN_JOB_READ, issuer="powerlifting-gateway")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/v1/jobs/{job.job_id}/result",
                headers={"X-Internal-Token": "test-only", "X-Person-Pk": "current-actor", "X-PL-Principal": token},
            )
        assert response.status_code == 200
        assert response.json()['result'] == {'content': '{"summary": "report"}'}
        assert 'private' not in response.text and 'original-actor' not in response.text
        assert checked == [("analytics.markdown", {"pk": "athlete-a", "cache_only": True, "refresh": False, "_required_access": None}, "current-actor", "athlete-a")]

    asyncio.run(run())


def test_invalid_principal_is_a_validation_error(monkeypatch):
    import pytest
    from api.powerlifting_principal import verify_principal
    monkeypatch.setenv('PL_PRINCIPAL_SECRET', 'principal-test-secret-never-used-outside-tests')
    with pytest.raises(ValueError):
        verify_principal('malformed')


def test_domain_job_read_fails_closed_when_profile_revokes_access(monkeypatch, tmp_path):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-only")
    monkeypatch.setenv("PL_PRINCIPAL_SECRET", "principal-test-secret-never-used-outside-tests")
    job = domain_job(owner="actor", operation="program_get", status="running")

    class Service:
        async def get(self, job_id, owner=None):
            return job

    monkeypatch.setattr(jobs, "get_execution_service", lambda: Service())

    async def revoked(*args):
        raise HTTPException(403, "Powerlifting operation access denied")

    monkeypatch.setattr(jobs, "_check_profile_access", revoked)
    app = FastAPI()
    app.include_router(jobs.router)

    async def run():
        token = principal_token("actor", "athlete-a", jobs.DOMAIN_JOB_READ, issuer="powerlifting-gateway")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/jobs/{job.job_id}", headers={"X-Internal-Token": "test-only", "X-Person-Pk": "actor", "X-PL-Principal": token})
        assert response.status_code == 403

    asyncio.run(run())
