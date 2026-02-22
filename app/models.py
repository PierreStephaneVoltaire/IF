"""Pydantic models for the FastAPI router."""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict
from enum import Enum


class Model(BaseModel):
    id: str
    object: str = "model"
    created: int = 1704067200
    owned_by: str = "openrouter"


class ModelList(BaseModel):
    object: str = "list"
    data: List[Model] = []


class ImageUrl(BaseModel):
    url: str
    detail: Optional[str] = None


class ContentPart(BaseModel):
    type: str  # "text" or "image_url"
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None


class FileAttachment(BaseModel):
    type: Optional[str] = None        
    id: Optional[str] = None           
    url: Optional[str] = None          
    name: Optional[str] = None         
    filename: Optional[str] = None      
    mime_type: Optional[str] = None     
    content: Optional[str] = None       
    size: Optional[int] = None         


class Message(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: Union[str, List[ContentPart]] = ""
    images: Optional[List[str]] = None
    files: Optional[List[FileAttachment]] = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "router"
    messages: List[Message]
    files: Optional[List[FileAttachment]] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    chat_id: Optional[str] = None  # Chat identifier - used for sandbox folder and state persistence
    stream: bool = False  # Enable streaming mode
    metadata: Optional[Dict[str, Any]] = None  # Optional metadata (can include request_id for idempotency)


# ============================================================================
# Streaming Models
# ============================================================================

class StreamEventType(str, Enum):
    """Types of stream events."""
    CHECKPOINT = "checkpoint"
    PROGRESS = "progress"
    CONTENT = "content"
    OPTIONS = "options"
    QUESTION = "question"
    FINAL = "final"
    ERROR = "error"


class StreamCheckpointType(str, Enum):
    """Types of checkpoints in the flow."""
    ACKNOWLEDGED = "acknowledged"
    CATEGORIZED = "categorized"
    PLAN_READY = "plan_ready"
    AWAITING_INPUT = "awaiting_input"
    IN_PROGRESS = "in_progress"
    RESEARCH_COMPLETE = "research_complete"
    PERSPECTIVES_READY = "perspectives_ready"
    COMPLETE = "complete"
    ERROR = "error"


class AgentOptionModel(BaseModel):
    """A single option presented to the user."""
    id: str
    label: str
    description: str
    metadata: Dict[str, Any] = {}


class StreamEvent(BaseModel):
    """SSE stream event structure."""
    event_type: StreamEventType
    checkpoint_type: Optional[StreamCheckpointType] = None
    content: str = ""
    options: List[AgentOptionModel] = []
    requires_input: bool = False
    metadata: Dict[str, Any] = {}
    timestamp: str = ""


class UserCheckpointResponse(BaseModel):
    """User response to a checkpoint."""
    conversation_id: str
    checkpoint_id: str
    action: str  # "continue", "stop", "select", "answer"
    selected_option_id: Optional[str] = None
    answer_text: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ConversationContext(BaseModel):
    """Tracks current state across checkpoints."""
    conversation_id: str
    chat_id: str  # Chat identifier - used as sandbox folder key
    category: Optional[str] = None
    reasoning_pattern: Optional[str] = None
    condensed_intent: Optional[str] = None
    current_checkpoint: Optional[str] = None
    is_waiting_for_input: bool = False
    state: Dict[str, Any] = {}
    created_at: str = ""
    updated_at: str = ""


class CategorizationResult(BaseModel):
    """Result from categorization tool."""
    category: str
    reasoning_pattern: str
    condensed_intent: str
    category_scores: Dict[str, float] = {}
    reasoning_scores: Dict[str, float] = {}
    applicable_directives: List[str] = []
    debug_info: Dict[str, Any] = {}


class WorkflowResult(BaseModel):
    """Result from a workflow execution."""
    success: bool
    content: str
    raw_response: str = ""
    agent_name: str = ""
    model: str = ""
    attachments: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
