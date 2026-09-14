import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from execution.schemas import JobError, JobRequest
from execution.service import get_execution_service, HostError
from execution.store import TERMINAL


router = APIRouter(prefix="/v1/jobs", tags=["domain compatibility"])
turn_router = APIRouter(prefix="/v1/turns", tags=["turn artifacts"])


def internal_auth(x_internal_token: str = Header(default="")):
    expected = os.getenv("INTERNAL_API_TOKEN", "")
    if not expected or not hmac.compare_digest(expected, x_internal_token):
        raise HTTPException(401, "Invalid internal token")


def owner_scope(_: None = Depends(internal_auth), x_person_pk: str = Header(default="")) -> str:
    if not x_person_pk:
        raise HTTPException(403, "Authenticated Person scope required")
    return x_person_pk


def store():
    return get_execution_service().store


async def invoke(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except KeyError:
        raise HTTPException(404, "Job not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))


async def native(function, *args):
    try:
        return await function(*args)
    except HostError as exc:
        raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from exc


@router.post("", status_code=202)
async def submit(request: JobRequest, owner: str = Depends(owner_scope)):
    if request.kind != "domain":
        raise HTTPException(422, "Only asynchronous domain consumers may submit /v1/jobs; use Conversation turns")
    from .job_tools import domain_operations
    from flow.runner import instruction_payload
    from jsonschema import validate, ValidationError
    operation = domain_operations().get(request.payload.get("operation"))
    if not operation:
        raise HTTPException(422, "Unknown domain operation")
    try:
        validate(request.payload.get("arguments", {}), operation["input_schema"])
    except ValidationError as exc:
        raise HTTPException(422, exc.message) from exc
    request.payload.update(domain=operation["domain"], athlete=request.payload.get("athlete") or request.payload.get("arguments", {}).get("pk") or owner)
    request.payload.update(await asyncio.to_thread(instruction_payload, owner))
    return await native(get_execution_service().submit, owner, request)


@router.get("/{job_id}")
async def status(job_id: str, owner: str = Depends(owner_scope)):
    return await native(get_execution_service().get, job_id, owner)


@router.get("/{job_id}/result")
async def result(job_id: str, owner: str = Depends(owner_scope)):
    job = await native(get_execution_service().get, job_id, owner)
    return JSONResponse(job.model_dump(mode="json"), status_code=200 if job.status in TERMINAL else 202)


@router.post("/{job_id}/cancel")
async def cancel(job_id: str, owner: str = Depends(owner_scope)):
    return await native(get_execution_service().cancel, job_id, owner)


@router.get("/{job_id}/events")
async def events(job_id: str, request: Request, after: int = 0, owner: str = Depends(owner_scope)):
    service = get_execution_service()
    await native(service.get, job_id, owner)

    async def stream():
        cursor = after
        while not await request.is_disconnected():
            rows = await native(service.events, job_id, owner, cursor)
            for event in rows:
                cursor = event.sequence
                yield f"id: {cursor}\nevent: {event.event}\ndata: {event.model_dump_json()}\n\n"
            job = await native(service.get, job_id, owner)
            if job.status in TERMINAL and not rows:
                return
            if not rows:
                yield ": keepalive\n\n"
                await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream")


def artifact_root() -> Path:
    return Path(os.getenv("IF_ARTIFACT_DIR", "./data/artifacts"))


@turn_router.put("/{job_id}/artifacts/{name}", dependencies=[Depends(internal_auth)])
async def upload_artifact(job_id: str, name: str, request: Request, x_worker_id: str = Header()):
    await native(get_execution_service().active_scope, job_id)
    if Path(name).name != name or name in {".", ".."}:
        raise HTTPException(422, "Invalid artifact name")
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(413, "Artifact exceeds 25 MiB")
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = hashlib.sha256(name.encode() + b"\\0" + content).hexdigest()
    target = artifact_root() / job_id / artifact_id
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    artifact = {"artifact_id": artifact_id, "name": name, "media_type": request.headers.get("content-type", "application/octet-stream"), "size": len(content), "sha256": digest}
    await get_execution_service().request("POST", f"/turns/{job_id}/artifacts", json=artifact)
    return artifact


@router.get("/{job_id}/artifacts/{artifact_id}")
@turn_router.get("/{job_id}/artifacts/{artifact_id}")
async def download_artifact(job_id: str, artifact_id: str, owner: str = Depends(owner_scope)):
    job = await native(get_execution_service().get, job_id, owner)
    if len(artifact_id) != 64 or any(c not in "0123456789abcdef" for c in artifact_id):
        raise HTTPException(404, "Artifact not found")
    target = artifact_root() / job_id / artifact_id
    if not target.is_file():
        raise HTTPException(404, "Artifact not found")
    artifact = next((item for item in job.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None:
        raise HTTPException(404, "Artifact not found")
    return FileResponse(target, filename=artifact.name, media_type=artifact.media_type)


@turn_router.get("/{job_id}/inputs/{artifact_id}", dependencies=[Depends(internal_auth)])
async def download_input(job_id: str, artifact_id: str, x_worker_id: str = Header()):
    job = await native(get_execution_service().active_scope, job_id)
    allowed = {item["artifact_id"] for item in job.request.payload.get("uploaded_files", [])}
    if artifact_id not in allowed or len(artifact_id) != 64 or any(c not in "0123456789abcdef" for c in artifact_id):
        raise HTTPException(404, "Input not found")
    target = artifact_root() / "inputs" / artifact_id
    if not target.is_file():
        raise HTTPException(404, "Input not found")
    return FileResponse(target)
