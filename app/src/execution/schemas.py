from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1, max_length=200)
    kind: Literal["conversation", "specialist", "inference", "domain", "reflection", "heartbeat", "summary"] = "conversation"
    payload: dict[str, Any]
    priority: Literal[0, 10] = 0
    idempotency_key: str = Field(min_length=1, max_length=200)


class JobError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class Artifact(BaseModel):
    artifact_id: str
    name: str
    media_type: str
    size: int = Field(ge=0)
    sha256: str


class Job(BaseModel):
    job_id: str
    owner: str
    request: JobRequest
    status: Literal["starting", "queued", "running", "succeeded", "failed", "cancel_requested", "cancelled", "uncertain"]
    created_at: float
    updated_at: float
    worker_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    lease_until: float | None = None
    result: dict[str, Any] | None = None
    error: JobError | None = None
    artifacts: list[Artifact] = Field(default_factory=list)


class JobEvent(BaseModel):
    sequence: int
    job_id: str
    event: str
    data: dict[str, Any]
    created_at: float
