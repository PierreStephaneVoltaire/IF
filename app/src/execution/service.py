import asyncio
import inspect
import os
from pathlib import Path

import httpx

from .schemas import Job, JobEvent, JobRequest
from .store import JobStore, TERMINAL


class ExecutionFailure(RuntimeError):
    def __init__(self, job: Job):
        self.job = job
        self.code = job.error.code if job.error else job.status
        super().__init__(job.error.message if job.error else f"Execution {job.status}")


class HostError(RuntimeError):
    def __init__(self, status, detail, code="host_unavailable"):
        self.status, self.code = status, code
        super().__init__(detail)


class ExecutionService:
    def __init__(self, store: JobStore, transport=None):
        self.store = store
        self.transport = transport

    async def request(self, method, path, **kwargs):
        try:
            async with httpx.AsyncClient(base_url=os.getenv("IF_CODEX_HOST_URL", "http://if-codex-worker:8001"), headers={"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"]}, timeout=40, transport=self.transport) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HostError(503, "Codex host unavailable. Accepted work is not replayed; reconnect using its request reference.") from exc
        if response.is_error:
            data = response.json()
            raise HostError(response.status_code, data.get("detail", "Codex host error"), data.get("code", "host_error"))
        return response.json()

    async def submit(self, owner: str, request: JobRequest) -> Job:
        return Job.model_validate(await self.request("POST", "/turns", json={"owner": owner, "request": request.model_dump(mode="json")}))

    async def get(self, job_id, owner=None):
        try:
            return Job.model_validate(await self.request("GET", f"/turns/{job_id}", params={"owner": owner} if owner else {}))
        except HostError as exc:
            if exc.status in {404, 503}:
                try:
                    return await asyncio.to_thread(self.store.get, job_id, owner)
                except KeyError:
                    pass
            raise

    async def list(self, owner=None, conversation=None, undelivered=False):
        params = {key: value for key, value in {"owner": owner, "conversation": conversation, "undelivered": undelivered}.items() if value is not None}
        return [Job.model_validate(job) for job in await self.request("GET", "/turns", params=params)]

    async def cancel(self, job_id, owner):
        return Job.model_validate(await self.request("POST", f"/turns/{job_id}/cancel", params={"owner": owner}))

    async def events(self, job_id, owner, after=0):
        job = await self.get(job_id, owner)
        if not job.thread_id and job.status != "starting" and job.worker_id != "native":
            try:
                return await asyncio.to_thread(self.store.events, job_id, owner, after)
            except KeyError:
                pass
        return [JobEvent.model_validate(event) for event in await self.request("GET", f"/turns/{job_id}/events", params={"owner": owner, "after": after})]

    async def active_scope(self, job_id):
        job = Job.model_validate(await self.request("GET", f"/turns/{job_id}"))
        if job.status not in {"starting", "running"}:
            raise HostError(403, "Turn scope revoked", "scope_revoked")
        return job

    async def wait(self, job, emit=None):
        cursor = 0
        while True:
            if emit:
                rows = await self.events(job.job_id, job.owner, cursor)
                for event in rows:
                    cursor = event.sequence
                    outcome = emit(event.event, event.data)
                    if inspect.isawaitable(outcome):
                        await outcome
                if len(rows) == 100:
                    continue
            if job.status in TERMINAL:
                break
            await asyncio.sleep(0.25)
            job = await self.get(job.job_id, job.owner)
        if job.status != "succeeded":
            raise ExecutionFailure(job)
        return {**(job.result or {}), "job_id": job.job_id, "thread_id": job.thread_id, "turn_id": job.turn_id}

    async def submit_and_wait(self, owner: str, request: JobRequest, emit=None) -> dict:
        job = await self.submit(owner, request)
        return await self.wait(job, emit)


_service: ExecutionService | None = None


def get_execution_service() -> ExecutionService:
    global _service
    if _service is None:
        path = os.getenv("IF_JOB_DB", str(Path(os.getenv("PERSISTENCE_DIR", "./data/conversations")) / "execution.sqlite3"))
        _service = ExecutionService(JobStore(path))
    return _service
