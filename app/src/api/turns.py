import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from execution.service import get_execution_service
from execution.store import TERMINAL
from flow.runner import prepare_conversation
from .schemas import ChatCompletionMessage
from .jobs import native, owner_scope, events as stream_events


router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatCompletionMessage] = Field(min_length=1, max_length=1000)
    output_schema: dict | None = None
    specialist: str | None = None
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "medium"
    idempotency_key: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=1, max_length=200)


@router.post("/{conversation_id}/turns", status_code=202)
async def submit(conversation_id: str, body: TurnRequest, owner: str = Depends(owner_scope)):
    import asyncio
    if body.model not in {"gpt-5.6-sol", "gpt-6-astra"}:
        raise HTTPException(422, "Coordinator must be Sol or Astra")
    if body.specialist:
        from .job_tools import roles
        if body.specialist not in roles():
            raise HTTPException(422, "Unknown Specialist")
    data = {"_specialist": body.specialist, **body.model_dump(), "conversation_id": conversation_id, "_owner": owner, "_idempotency_key": body.idempotency_key}
    _, request, _ = await asyncio.to_thread(prepare_conversation, data, conversation_id, conversation_id)
    return await native(get_execution_service().submit, owner, request)


async def resolve(conversation_id, turn_id, owner):
    jobs = await native(get_execution_service().list, owner, conversation_id)
    job = next((job for job in jobs if turn_id in {job.turn_id, job.job_id}), None)
    if not job:
        raise HTTPException(404, "Turn not found in this Conversation")
    return job


@router.get("/{conversation_id}/turns")
async def list_turns(conversation_id: str, owner: str = Depends(owner_scope)):
    return await native(get_execution_service().list, owner, conversation_id)


@router.get("/{conversation_id}/turns/{turn_id}")
@router.get("/{conversation_id}/turns/{turn_id}/result")
async def status(conversation_id: str, turn_id: str, owner: str = Depends(owner_scope)):
    job = await resolve(conversation_id, turn_id, owner)
    return JSONResponse(job.model_dump(mode="json"), status_code=200 if job.status in TERMINAL else 202)


@router.post("/{conversation_id}/turns/{turn_id}/cancel")
async def cancel(conversation_id: str, turn_id: str, owner: str = Depends(owner_scope)):
    job = await resolve(conversation_id, turn_id, owner)
    return await native(get_execution_service().cancel, job.job_id, owner)


@router.get("/{conversation_id}/turns/{turn_id}/events")
async def events(conversation_id: str, turn_id: str, request: Request, after: int = 0, owner: str = Depends(owner_scope)):
    job = await resolve(conversation_id, turn_id, owner)
    return await stream_events(job.job_id, request, after, owner)
