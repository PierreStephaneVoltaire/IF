import asyncio
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from execution.schemas import JobError, JobRequest
from execution.service import get_execution_service, HostError
from execution.store import TERMINAL
from .powerlifting_principal import verify_principal


router = APIRouter(prefix="/v1/jobs", tags=["domain compatibility"])
turn_router = APIRouter(prefix="/v1/turns", tags=["turn artifacts"])
DOMAIN_JOB_READ = "domain_job_read"
DOMAIN_JOB_CANCEL = "domain_job_cancel"


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


def _job_operation(job) -> str:
    operation = job.request.payload.get("operation")
    if job.request.kind != "domain" or not isinstance(operation, str) or not operation:
        raise HTTPException(404, "Job not found")
    return operation


def _check_scope(value: Any, athlete: str):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == '_report_source':
                continue
            if key in {"athlete", "pk", "user_pk", "mapped_pk", "person_pk", "_user_pk"} and item != athlete:
                raise HTTPException(403, "Job payload scope conflicts with authenticated Athlete")
            _check_scope(item, athlete)
    elif isinstance(value, list):
        for item in value:
            _check_scope(item, athlete)


async def _check_profile_access(operation: str, arguments: dict[str, Any], person: str, athlete: str, principal: str):
    from .powerlifting_principal import principal_token

    root_principal = principal_token(person, athlete, operation)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                os.getenv("PL_PROFILE_URL", "http://pl-profile.if-portals.svc.cluster.local:8000") + "/internal/access",
                headers={"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"], "X-PL-Principal": root_principal},
                json={"operation": operation, "arguments": arguments},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Powerlifting permission service unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(response.status_code if response.status_code in {401, 403} else 503, "Powerlifting operation access denied")


async def _domain_job(job_id: str, person: str, principal: str, action: str):
    job = await native(get_execution_service().get, job_id)
    operation = _job_operation(job)
    athlete = job.request.payload.get("athlete")
    if not isinstance(athlete, str) or not athlete:
        raise HTTPException(404, "Job not found")
    _check_scope(job.request.payload.get("arguments") or {}, athlete)
    try:
        verify_principal(principal, action, person=person, athlete=athlete)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(401, "Verified acting Person required") from exc
    arguments = dict(job.request.payload.get("arguments") or {})
    if action == DOMAIN_JOB_CANCEL and job.owner != person:
        raise HTTPException(403, "Only the submitting Person may cancel this job")
    if action == DOMAIN_JOB_READ:
        arguments.update(cache_only=True, refresh=False)
    await _check_profile_access(operation, arguments, person, athlete, principal)
    return job


async def _portal_job(job_id: str, person: str, principal: str, action: str):
    job = await native(get_execution_service().get, job_id)
    if job.request.kind != "domain":
        if job.owner != person:
            raise HTTPException(404, "Job not found")
        return job
    return await _domain_job(job_id, person, principal, action)


def _job_view(job):
    if job.request.kind != 'domain':
        return job.model_dump(mode='json')
    result = job.result or {}
    return {
        **job.model_dump(mode='json', include={'job_id', 'status', 'created_at', 'updated_at', 'error', 'artifacts'}),
        'request': {'payload': {'arguments': {'filename': job.request.payload.get('arguments', {}).get('filename')}}},
        'result': {'content': json.dumps(result['domain_result'])} if 'domain_result' in result else None,
    }


@router.post("", status_code=202)
async def submit(request: JobRequest, owner: str = Depends(owner_scope), x_pl_principal: str = Header(default="")):
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
    athlete = request.payload.get("athlete")
    if not isinstance(athlete, str) or not athlete:
        raise HTTPException(422, "Authenticated Athlete scope required")
    _check_scope(request.payload.get("arguments") or {}, athlete)
    try:
        claims = verify_principal(x_pl_principal, request.payload["operation"], person=owner, athlete=athlete)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(401, "Verified acting Person required") from exc
    internal_fields = {key for key in request.payload.get('arguments', {}) if key.startswith('_')}
    if internal_fields - ({'_report_source'} if claims['iss'] == 'if-native' else set()):
        raise HTTPException(403, 'Internal operation fields cannot be supplied')
    await _check_profile_access(request.payload["operation"], request.payload.get("arguments", {}), owner, athlete, x_pl_principal)
    request.payload.update(domain=operation["domain"], athlete=athlete)
    request.payload.update(await asyncio.to_thread(instruction_payload, owner))
    return _job_view(await native(get_execution_service().submit, owner, request))


@router.get("/{job_id}")
async def status(job_id: str, owner: str = Depends(owner_scope), x_pl_principal: str = Header(default="")):
    return _job_view(await _portal_job(job_id, owner, x_pl_principal, DOMAIN_JOB_READ))


@router.get("/{job_id}/result")
async def result(job_id: str, owner: str = Depends(owner_scope), x_pl_principal: str = Header(default="")):
    job = await _portal_job(job_id, owner, x_pl_principal, DOMAIN_JOB_READ)
    return JSONResponse(_job_view(job), status_code=200 if job.status in TERMINAL else 202)


@router.post("/{job_id}/cancel")
async def cancel(job_id: str, owner: str = Depends(owner_scope), x_pl_principal: str = Header(default="")):
    job = await _portal_job(job_id, owner, x_pl_principal, DOMAIN_JOB_CANCEL)
    return _job_view(await native(get_execution_service().cancel, job_id, job.owner))


@router.get("/{job_id}/events")
async def events(job_id: str, request: Request, after: int = 0, owner: str = Depends(owner_scope), x_pl_principal: str = Header(default="")):
    service = get_execution_service()
    job = await _portal_job(job_id, owner, x_pl_principal, DOMAIN_JOB_READ)
    if job.request.kind == 'domain' and job.owner != owner:
        raise HTTPException(403, 'Only the submitting Person may read execution events')

    async def stream():
        cursor = after
        while not await request.is_disconnected():
            if job.request.kind == 'domain':
                try:
                    await _domain_job(job_id, owner, x_pl_principal, DOMAIN_JOB_READ)
                except HTTPException:
                    return
            rows = await native(service.events, job_id, job.owner, cursor)
            for event in rows:
                cursor = event.sequence
                yield f"id: {cursor}\nevent: {event.event}\ndata: {event.model_dump_json()}\n\n"
            latest = await native(service.get, job_id, job.owner)
            if latest.status in TERMINAL and not rows:
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
async def download_artifact(job_id: str, artifact_id: str, owner: str = Depends(owner_scope), x_pl_principal: str = Header(default="")):
    job = await _portal_job(job_id, owner, x_pl_principal, DOMAIN_JOB_READ)
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
