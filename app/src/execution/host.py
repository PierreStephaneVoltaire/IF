import asyncio
import hashlib
import hmac
import os
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .native import NativeSession, failure, recover
from .schemas import Artifact, JobError, JobRequest
from .store import TERMINAL
from .turn_store import TurnStore


class BusyError(ValueError):
    pass


class ConversationHost:
    def __init__(self, root, session_factory=NativeSession, recover_turn=recover):
        self.root = Path(root)
        self.store = TurnStore(str(self.root / "turns.sqlite3"))
        self.session_factory = session_factory
        self.recover_turn = recover_turn
        self.active = {}
        self.ready = {}
        self.tasks = {}
        self.lock = asyncio.Lock()

    def workspace(self, owner, conversation):
        key = hashlib.sha256((owner + "\0" + conversation).encode()).hexdigest()
        return str(self.root / "conversations" / key)

    async def reconcile(self):
        for job in self.store.list():
            if job.status in TERMINAL and not (job.error and job.error.code == "host_disconnected"):
                continue
            try:
                result = await self.recover_turn(job, self.workspace(job.owner, job.request.conversation_id))
            except Exception:
                result = None
            if result and job.request.kind == "domain":
                if not (job.result and "domain_result" in job.result):
                    result = None
                else:
                    result.update(content=json.dumps(job.result["domain_result"]), domain_result=job.result["domain_result"])
            if result:
                job.status, job.result, job.error = "succeeded", result, None
            else:
                job.status = "uncertain"
                job.error = JobError(code="host_restarted", message="Native work was interrupted or its outcome is unknown. Inspect side effects and explicitly retry.")
            self.store.save(job)
            self.store.event(job.job_id, job.status, {"reconciled": True})

    async def submit(self, owner, request):
        async with self.lock:
            existing = self.store.existing(owner, request)
            if existing:
                return existing
            key = (owner, request.conversation_id)
            active = self.active.get(key)
            if active:
                if request.kind != "conversation" or active.job.request.kind != "conversation":
                    raise BusyError("This Conversation already has active work")
                if active.job.status == "cancel_requested":
                    raise BusyError("This turn is being interrupted")
                self.store.record_input(owner, request, active.job.job_id)
                active.job.request.payload.setdefault("uploaded_files", []).extend(request.payload.get("uploaded_files", []))
                self.store.save(active.job)
            else:
                if len(self.active) >= 2 or (request.priority == 10 and self.active):
                    raise BusyError("IF is busy: two Conversations can run at once. Retry when one finishes.")
                job = self.store.start(owner, request)
                job.thread_id = self.store.thread(owner, request.conversation_id)
                self.store.save(job)
                session = self.session_factory(job, self.workspace(*key))
                self.active[key] = session
                self.ready[job.job_id] = asyncio.Event()
                self.tasks[job.job_id] = asyncio.create_task(self.run(key, session))
                return job
        try:
            await asyncio.wait_for(self.ready[active.job.job_id].wait(), 30)
            if active.job.status != "running":
                raise RuntimeError("Turn ended before the follow-up could be steered; explicitly retry the message")
            await active.steer(request)
            self.store.confirm_input(owner, request.idempotency_key)
            self.store.event(active.job.job_id, "steered", {"idempotency_key": request.idempotency_key})
        except Exception:
            self.store.event(active.job.job_id, "steering_uncertain", {"idempotency_key": request.idempotency_key, "message": "Follow-up may not have been accepted. Do not replay automatically."})
            raise
        return self.store.get(active.job.job_id, owner)

    async def run(self, key, session):
        job = session.job
        try:
            await session.start(self.store.bind)
            self.ready[job.job_id].set()
            self.store.event(job.job_id, "running", {"thread_id": job.thread_id, "turn_id": job.turn_id})
            job.result = await session.consume(lambda event, data: self.store.event(job.job_id, event, data))
            job.status = "succeeded"
        except asyncio.CancelledError:
            try:
                await session.interrupt()
            finally:
                job.status = "uncertain"
                job.error = JobError(code="interrupted", message="Turn interrupted. Inspect side effects before explicitly retrying.")
        except Exception as exc:
            job.error = JobError(**failure(exc))
            job.status = "uncertain" if job.turn_id or job.error.code in {"uncertain", "interrupted"} else "failed"
            if job.turn_id and job.error.code not in {"interrupted", "usage_limit", "auth_unavailable"}:
                job.error.code = "host_disconnected"
                try:
                    recovered = await self.recover_turn(job, session.workspace)
                except Exception:
                    recovered = None
                if recovered:
                    job.status, job.result, job.error = "succeeded", recovered, None
        finally:
            self.ready[job.job_id].set()
            latest = self.store.get(job.job_id)
            job.artifacts = latest.artifacts
            if job.result is not None:
                job.result["artifacts"] = [item.model_dump() for item in latest.artifacts]
            if job.request.kind == "domain" and job.status == "succeeded" and not (latest.result and "domain_result" in latest.result):
                job.status = "uncertain"
                job.error = JobError(code="domain_incomplete", message="The domain operation did not return a validated result. Inspect progress before explicitly retrying.")
            if latest.result and "domain_result" in latest.result:
                job.result = {**(job.result or {}), "domain_result": latest.result["domain_result"], "artifacts": [item.model_dump() for item in latest.artifacts]}
                if job.status == "succeeded":
                    job.result["content"] = json.dumps(latest.result["domain_result"])
            self.store.save(job)
            self.store.event(job.job_id, job.status, {"error": job.error.model_dump() if job.error else None})
            self.active.pop(key, None)
            try:
                await session.close()
            finally:
                self.tasks.pop(job.job_id, None)

    async def cancel(self, job_id, owner):
        job = self.store.get(job_id, owner)
        if job.status in TERMINAL:
            return job
        session = self.active.get((owner, job.request.conversation_id))
        if not session or session.job.job_id != job_id:
            raise ValueError("Native turn unavailable; reconnect to reconcile")
        session.job.status = "cancel_requested"
        self.store.save(session.job)
        self.store.event(job_id, "cancel_requested", {})
        task = self.tasks.get(job_id)
        if task:
            asyncio.get_running_loop().call_soon(task.cancel)
        return session.job

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            asyncio.get_running_loop().call_soon(task.cancel)
        await asyncio.gather(*tasks, return_exceptions=True)


def authenticate(x_internal_token: str = Header(default="")):
    expected = os.getenv("INTERNAL_API_TOKEN", "")
    if not expected or not hmac.compare_digest(expected, x_internal_token):
        raise HTTPException(401, "Invalid host credential")


class Submit(BaseModel):
    owner: str
    request: JobRequest


def create_app(host=None):
    @asynccontextmanager
    async def lifespan(app):
        await app.state.host.reconcile()
        yield
        await app.state.host.close()

    app = FastAPI(lifespan=lifespan, dependencies=[Depends(authenticate)])
    app.state.host = host or ConversationHost(os.getenv("IF_HOST_STATE_DIR", "/work/host"))

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Turn not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": str(exc), "code": "busy" if isinstance(exc, BusyError) else "conflict"}, status_code=429 if isinstance(exc, BusyError) else 409)

    @app.post("/conversations/reset")
    async def reset(owner: str, conversation: str):
        async with app.state.host.lock:
            if (owner, conversation) in app.state.host.active:
                raise BusyError("Cancel the active turn before ending this Conversation")
            with app.state.host.store.connect() as db:
                db.execute("UPDATE conversations SET thread=NULL WHERE owner=? AND conversation=?", (owner, conversation))
        return {"reset": True}

    @app.get("/health")
    async def health():
        return {"active": len(app.state.host.active), "capacity": 2}

    @app.post("/turns", status_code=202)
    async def submit(body: Submit):
        if not body.owner:
            raise HTTPException(403, "Authenticated Person required")
        return await app.state.host.submit(body.owner, body.request)

    @app.get("/turns")
    async def list_turns(owner: str | None = None, conversation: str | None = None, undelivered: bool = False):
        return app.state.host.store.list(owner, conversation, undelivered=undelivered)

    @app.get("/turns/{job_id}")
    async def get_turn(job_id: str, owner: str | None = None):
        return app.state.host.store.get(job_id, owner)

    @app.post("/turns/{job_id}/cancel")
    async def cancel(job_id: str, owner: str):
        return await app.state.host.cancel(job_id, owner)

    @app.get("/turns/{job_id}/events")
    async def events(job_id: str, owner: str, after: int = 0):
        return app.state.host.store.events(job_id, owner, after)

    @app.post("/turns/{job_id}/artifacts")
    async def artifact(job_id: str, artifact: Artifact):
        job = app.state.host.store.get(job_id)
        if job.status not in {"starting", "running"}:
            raise HTTPException(409, "Turn scope revoked")
        job.artifacts = [item for item in job.artifacts if item.artifact_id != artifact.artifact_id] + [artifact]
        app.state.host.store.save(job)
        return artifact

    @app.post("/turns/{job_id}/domain-dispatch")
    async def domain_dispatch(job_id: str):
        async with app.state.host.lock:
            job = app.state.host.store.get(job_id)
            if job.status != "running" or job.request.kind != "domain":
                raise HTTPException(403, "Active domain turn required")
            previous = job.result or {}
            if previous.get("domain_dispatched"):
                if "domain_dispatch_result" not in previous:
                    raise HTTPException(409, "Domain dispatch outcome is uncertain. Do not replay; inspect progress and explicitly retry.")
                return {"dispatch": False, "result": previous["domain_dispatch_result"]}
            job.result = {**previous, "domain_dispatched": True}
            app.state.host.store.save(job)
            return {"dispatch": True}

    @app.post("/turns/{job_id}/domain-progress")
    async def domain_progress(job_id: str, result: dict):
        job = app.state.host.store.get(job_id)
        if job.status != "running":
            raise HTTPException(403, "Turn scope revoked")
        primary_execution = (job.result or {}).get("domain_dispatch_result", {}).get("execution_id")
        matches = result.get("operation") == job.request.payload.get("operation") or (result.get("operation") == "domain_resume" and result.get("domain") == job.request.payload.get("domain") and primary_execution and result.get("execution_id") == primary_execution)
        if result.get("operation") == job.request.payload.get("operation") and job.request.kind == "domain":
            job.result = {**(job.result or {}), "domain_dispatch_result": result}
            app.state.host.store.save(job)
        if result.get("status") == "succeeded" and job.request.kind == "domain" and matches:
            job.result = {**(job.result or {}), "domain_result": result["result"]}
            app.state.host.store.save(job)
        app.state.host.store.event(job_id, "domain_progress", {"status": result.get("status"), "execution_id": result.get("execution_id")})
        return {"ok": True}

    @app.post("/turns/{job_id}/delivered")
    async def delivered(job_id: str, owner: str):
        job = app.state.host.store.get(job_id, owner)
        if job.status not in TERMINAL:
            raise HTTPException(409, "Turn is still active")
        job.result = {**(job.result or {}), "delivered": True}
        return app.state.host.store.save(job)

    return app
