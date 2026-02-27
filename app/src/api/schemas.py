"""Pydantic models for OpenAI-compatible API requests and responses.

This module defines the schemas for the API endpoints according to the
OpenAI API specification.
"""
from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Models Endpoint
# ============================================================================

class Model(BaseModel):
    """Model object returned by /v1/models endpoint."""
    id: str
    object: Literal["model"] = "model"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    owned_by: str = "if-prototype"


class ModelList(BaseModel):
    """Response from /v1/models endpoint."""
    object: Literal["list"] = "list"
    data: List[Model]


# ============================================================================
# Chat Completions
# ============================================================================

class ChatCompletionMessage(BaseModel):
    """Message in a chat completion request."""
    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[Union[str, List[Dict[str, Any]]]] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    """Request body for /v1/chat/completions endpoint."""
    model: str
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    # Additional parameters for our implementation
    metadata: Optional[Dict[str, Any]] = None


class ChatCompletionChoice(BaseModel):
    """Choice in a chat completion response."""
    index: int
    message: ChatCompletionMessage
    finish_reason: Optional[str] = None


class Usage(BaseModel):
    """Token usage information."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class Attachment(BaseModel):
    """File attachment in a response."""
    filename: str
    content_type: str
    url: str


class ChatCompletionResponse(BaseModel):
    """Response from /v1/chat/completions endpoint."""
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[Usage] = None
    # Custom field for attachments
    attachments: Optional[List[Attachment]] = None


# ============================================================================
# Streaming
# ============================================================================

class ChatCompletionChunkDelta(BaseModel):
    """Delta content in a streaming chunk."""
    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionChunkChoice(BaseModel):
    """Choice in a streaming chunk."""
    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """Streaming chunk for chat completions."""
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    model: str
    choices: List[ChatCompletionChunkChoice]


# ============================================================================
# Error Responses
# ============================================================================

class ErrorDetail(BaseModel):
    """Error detail object."""
    type: str
    code: Optional[str] = None
    message: str
    param: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: ErrorDetail
