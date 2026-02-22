"""Streaming infrastructure using LangGraph's native streaming and interrupts.

This module provides OpenAI-compatible streaming with:
- LangGraph checkpoint support
- Native interrupt mechanism for human-in-the-loop
- Memory via LangGraph's state management
- Graph visualization support
"""
from __future__ import annotations
import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

from langgraph.types import interrupt, Command
from langgraph.constants import START, END


class CheckpointType(str, Enum):
    """Types of checkpoints in the conversation flow."""
    ACKNOWLEDGED = "acknowledged"           # Message received confirmation
    CATEGORIZED = "categorized"             # Category and reasoning pattern determined
    PLAN_READY = "plan_ready"               # Execution plan ready for review
    AWAITING_INPUT = "awaiting_input"       # Waiting for user input/choice
    IN_PROGRESS = "in_progress"             # Work in progress update
    RESEARCH_COMPLETE = "research_complete" # Research phase done, awaiting confirmation
    PERSPECTIVES_READY = "perspectives_ready"  # Multiple perspectives generated
    COMPLETE = "complete"                   # Final response ready
    ERROR = "error"                         # Error occurred
    INTERRUPT = "interrupt"                 # LangGraph interrupt


class EventType(str, Enum):
    """SSE event types."""
    CHECKPOINT = "checkpoint"       # Checkpoint event requiring potential action
    PROGRESS = "progress"           # Progress update (no action needed)
    CONTENT = "content"             # Partial content stream
    OPTIONS = "options"             # Options for user to choose
    QUESTION = "question"           # Question requiring user answer
    FINAL = "final"                 # Final response
    ERROR = "error"                 # Error event
    INTERRUPT = "interrupt"         # LangGraph interrupt event
    STATE_UPDATE = "state_update"   # State update event


@dataclass
class AgentOption:
    """A single option that can be presented to the user."""
    id: str
    label: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamMessage:
    """A message in the stream."""
    event_type: EventType
    checkpoint_type: Optional[CheckpointType] = None
    content: str = ""
    options: List[AgentOption] = field(default_factory=list)
    requires_input: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    checkpoint_id: Optional[str] = None
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        data = {
            "event_type": self.event_type.value,
            "checkpoint_type": self.checkpoint_type.value if self.checkpoint_type else None,
            "content": self.content,
            "options": [asdict(opt) for opt in self.options],
            "requires_input": self.requires_input,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "checkpoint_id": self.checkpoint_id,
        }
        return f"event: {self.event_type.value}\ndata: {json.dumps(data)}\n\n"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type.value,
            "checkpoint_type": self.checkpoint_type.value if self.checkpoint_type else None,
            "content": self.content,
            "options": [asdict(opt) for opt in self.options],
            "requires_input": self.requires_input,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "checkpoint_id": self.checkpoint_id,
        }


@dataclass
class UserResponse:
    """User response to a checkpoint/interrupt."""
    conversation_id: str
    checkpoint_id: str
    action: str  # "continue", "stop", "select", "answer", "resume"
    selected_option_id: Optional[str] = None
    answer_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationStream:
    """Manages bidirectional streaming for a conversation using LangGraph.
    
    This class handles:
    - Outgoing SSE events to the client
    - LangGraph interrupt integration
    - User responses to checkpoints
    - Conversation state tracking
    """
    
    def __init__(self, conversation_id: Optional[str] = None):
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.checkpoint_id: Optional[str] = None
        self.is_waiting_for_input = False
        self.user_response: Optional[UserResponse] = None
        self._response_event = asyncio.Event()
        self._message_queue: asyncio.Queue[StreamMessage] = asyncio.Queue()
        self._is_closed = False
        self._state: Dict[str, Any] = {}
        self._interrupt_data: Optional[Dict[str, Any]] = None
    
    @property
    def state(self) -> Dict[str, Any]:
        """Get current conversation state."""
        return self._state
    
    def update_state(self, **kwargs) -> None:
        """Update conversation state."""
        self._state.update(kwargs)
    
    async def emit(self, message: StreamMessage) -> None:
        """Emit a message to the stream."""
        if self._is_closed:
            return
        await self._message_queue.put(message)
    
    async def emit_acknowledged(self) -> None:
        """Emit acknowledgment that message was received."""
        await self.emit(StreamMessage(
            event_type=EventType.CHECKPOINT,
            checkpoint_type=CheckpointType.ACKNOWLEDGED,
            content="Message received. Processing...",
        ))
    
    async def emit_categorized(
        self,
        category: str,
        reasoning_pattern: str,
        condensed_intent: str,
    ) -> None:
        """Emit categorization results."""
        await self.emit(StreamMessage(
            event_type=EventType.CHECKPOINT,
            checkpoint_type=CheckpointType.CATEGORIZED,
            content=f"Categorized as '{category}' using '{reasoning_pattern}' reasoning pattern.",
            metadata={
                "category": category,
                "reasoning_pattern": reasoning_pattern,
                "condensed_intent": condensed_intent,
            },
        ))
    
    async def emit_plan(self, plan: Dict[str, Any]) -> None:
        """Emit execution plan for review."""
        await self.emit(StreamMessage(
            event_type=EventType.CHECKPOINT,
            checkpoint_type=CheckpointType.PLAN_READY,
            content="Execution plan ready for review.",
            metadata={"plan": plan},
        ))
    
    async def emit_progress(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Emit progress update."""
        await self.emit(StreamMessage(
            event_type=EventType.PROGRESS,
            checkpoint_type=CheckpointType.IN_PROGRESS,
            content=content,
            metadata=metadata or {},
        ))
    
    async def emit_content(self, content: str) -> None:
        """Emit partial content (for streaming text)."""
        await self.emit(StreamMessage(
            event_type=EventType.CONTENT,
            content=content,
        ))
    
    async def emit_state_update(self, state: Dict[str, Any]) -> None:
        """Emit state update event."""
        await self.emit(StreamMessage(
            event_type=EventType.STATE_UPDATE,
            metadata={"state": state},
        ))
    
    async def emit_interrupt(
        self,
        interrupt_type: str,
        data: Dict[str, Any],
    ) -> Optional[UserResponse]:
        """Emit LangGraph interrupt event and wait for response.
        
        This integrates with LangGraph's interrupt mechanism for
        human-in-the-loop flows.
        
        Args:
            interrupt_type: Type of interrupt (plan_review, question, options)
            data: Interrupt data including question, options, etc.
            
        Returns:
            UserResponse with the user's input
        """
        self.checkpoint_id = str(uuid.uuid4())
        self.is_waiting_for_input = True
        self._interrupt_data = data
        self._response_event.clear()
        
        # Create appropriate event based on interrupt type
        if interrupt_type == "options":
            options = [
                AgentOption(
                    id=opt.get("id", str(i)),
                    label=opt.get("label", f"Option {i+1}"),
                    description=opt.get("description", ""),
                    metadata=opt.get("metadata", {}),
                )
                for i, opt in enumerate(data.get("options", []))
            ]
            await self.emit(StreamMessage(
                event_type=EventType.INTERRUPT,
                checkpoint_type=CheckpointType.INTERRUPT,
                content=data.get("question", data.get("prompt", "Please choose:")),
                options=options,
                requires_input=True,
                checkpoint_id=self.checkpoint_id,
                metadata={
                    "interrupt_type": interrupt_type,
                    **data,
                },
            ))
        elif interrupt_type == "question":
            await self.emit(StreamMessage(
                event_type=EventType.INTERRUPT,
                checkpoint_type=CheckpointType.INTERRUPT,
                content=data.get("question", "Please provide input:"),
                requires_input=True,
                checkpoint_id=self.checkpoint_id,
                metadata={
                    "interrupt_type": interrupt_type,
                    "context": data.get("context"),
                },
            ))
        else:
            await self.emit(StreamMessage(
                event_type=EventType.INTERRUPT,
                checkpoint_type=CheckpointType.INTERRUPT,
                content=data.get("question", "Interrupt:"),
                requires_input=True,
                checkpoint_id=self.checkpoint_id,
                metadata={
                    "interrupt_type": interrupt_type,
                    **data,
                },
            ))
        
        # Wait for user response
        await self._response_event.wait()
        self.is_waiting_for_input = False
        return self.user_response
    
    async def emit_options(
        self,
        prompt: str,
        options: List[AgentOption],
        allow_custom: bool = True,
    ) -> Optional[UserResponse]:
        """Present options to user and wait for selection.
        
        Args:
            prompt: The question/prompt for the user
            options: List of options to choose from
            allow_custom: Whether to allow custom text input
            
        Returns:
            UserResponse with the user's selection, or None if cancelled
        """
        return await self.emit_interrupt("options", {
            "prompt": prompt,
            "options": [
                {
                    "id": opt.id,
                    "label": opt.label,
                    "description": opt.description,
                    "metadata": opt.metadata,
                }
                for opt in options
            ],
            "allow_custom": allow_custom,
        })
    
    async def emit_question(
        self,
        question: str,
        context: Optional[str] = None,
    ) -> Optional[UserResponse]:
        """Ask user a question and wait for answer.
        
        Args:
            question: The question to ask
            context: Optional context for the question
            
        Returns:
            UserResponse with the user's answer, or None if cancelled
        """
        return await self.emit_interrupt("question", {
            "question": question,
            "context": context,
        })
    
    async def emit_perspectives(
        self,
        perspectives: List[Dict[str, Any]],
        prompt: str = "Which perspective would you like to explore further?",
    ) -> Optional[UserResponse]:
        """Present multiple perspectives and let user choose.
        
        Args:
            perspectives: List of perspective results
            prompt: Question to ask user
            
        Returns:
            UserResponse with selection
        """
        options = [
            {
                "id": f"perspective_{i}",
                "label": p.get("label", f"Perspective {i+1}"),
                "description": p.get("summary", ""),
                "metadata": {"full_response": p.get("response", "")},
            }
            for i, p in enumerate(perspectives)
        ]
        
        # Add "both" option for opposing perspectives
        if len(perspectives) == 2:
            options.append({
                "id": "both",
                "label": "Show both perspectives",
                "description": "Present a balanced view incorporating both perspectives",
            })
        
        return await self.emit_interrupt("options", {
            "prompt": prompt,
            "options": options,
            "perspectives": perspectives,
        })
    
    async def emit_research_results(
        self,
        research_summary: str,
        sources: List[Dict[str, str]],
    ) -> Optional[UserResponse]:
        """Present research results and ask if user wants to proceed.
        
        Args:
            research_summary: Summary of research findings
            sources: List of sources with urls and titles
            
        Returns:
            UserResponse with user's decision
        """
        options = [
            {
                "id": "proceed",
                "label": "Proceed with analysis",
                "description": "Use these findings for the analysis",
            },
            {
                "id": "refine",
                "label": "Refine search",
                "description": "Adjust the search parameters",
            },
            {
                "id": "skip",
                "label": "Skip research",
                "description": "Proceed without using research results",
            },
        ]
        
        return await self.emit_interrupt("options", {
            "prompt": f"Research complete.\n\n{research_summary}",
            "options": options,
            "sources": sources,
        })
    
    async def emit_final(
        self,
        content: str,
        attachments: Optional[List[Dict]] = None,
    ) -> None:
        """Emit final response."""
        await self.emit(StreamMessage(
            event_type=EventType.FINAL,
            checkpoint_type=CheckpointType.COMPLETE,
            content=content,
            metadata={
                "attachments": attachments or [],
            },
        ))
    
    async def emit_error(self, error: str, recoverable: bool = False) -> None:
        """Emit error event."""
        await self.emit(StreamMessage(
            event_type=EventType.ERROR,
            checkpoint_type=CheckpointType.ERROR,
            content=error,
            metadata={"recoverable": recoverable},
        ))
    
    def receive_response(self, response: UserResponse) -> None:
        """Receive a user response to a checkpoint/interrupt."""
        if response.checkpoint_id == self.checkpoint_id:
            self.user_response = response
            self._response_event.set()
    
    def resume_with_response(self, response: Dict[str, Any]) -> None:
        """Resume after interrupt with response data.
        
        This is used to integrate with LangGraph's resume mechanism.
        """
        self.user_response = UserResponse(
            conversation_id=self.conversation_id,
            checkpoint_id=self.checkpoint_id or "",
            action=response.get("action", "continue"),
            selected_option_id=response.get("selected_option_id"),
            answer_text=response.get("answer_text"),
            metadata=response.get("metadata", {}),
        )
        self._response_event.set()
    
    async def stream(self) -> AsyncGenerator[str, None]:
        """Generate SSE stream."""
        while not self._is_closed:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=30.0  # Send keepalive every 30s
                )
                yield message.to_sse()
                
                if message.checkpoint_type == CheckpointType.COMPLETE:
                    break
                if message.checkpoint_type == CheckpointType.ERROR and not message.metadata.get("recoverable"):
                    break
                    
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"
    
    def close(self) -> None:
        """Close the stream."""
        self._is_closed = True
        self._response_event.set()  # Unblock any waiters


# Global registry of active conversation streams
_active_streams: Dict[str, ConversationStream] = {}


def get_stream(conversation_id: str) -> Optional[ConversationStream]:
    """Get an active conversation stream by ID."""
    return _active_streams.get(conversation_id)


def create_stream(conversation_id: Optional[str] = None) -> ConversationStream:
    """Create a new conversation stream."""
    stream = ConversationStream(conversation_id)
    _active_streams[stream.conversation_id] = stream
    return stream


def remove_stream(conversation_id: str) -> None:
    """Remove a conversation stream."""
    if conversation_id in _active_streams:
        _active_streams[conversation_id].close()
        del _active_streams[conversation_id]


def get_all_streams() -> Dict[str, ConversationStream]:
    """Get all active streams."""
    return _active_streams.copy()


def make_openai_chunk(
    content: str,
    completion_id: str,
    model: str,
    created: int,
    finish_reason: Optional[str] = None,
    role: Optional[str] = None,
) -> str:
    """Serialize one OpenAI-compatible streaming chunk as a ``data:`` SSE line.

    Format::

        data: {"id":"chatcmpl-...","object":"chat.completion.chunk",...}\\n\\n

    Args:
        content: Token text (may be empty for role/stop chunks).
        completion_id: Stable ID for the whole completion (e.g. ``chatcmpl-<uuid>``).
        model: Model name echoed back to the client.
        created: Unix timestamp for the completion.
        finish_reason: ``"stop"`` on the final chunk, ``None`` otherwise.
        role: Set to ``"assistant"`` on the very first chunk only.
    """
    delta: Dict[str, Any] = {}
    if role:
        delta["role"] = role
    if content:
        delta["content"] = content
    chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


async def stream_langgraph_events(
    events: AsyncGenerator[Dict[str, Any], None],
    stream: ConversationStream,
) -> AsyncGenerator[StreamMessage, None]:
    """Convert LangGraph astream_events to StreamMessages.
    
    This bridges LangGraph's native streaming with our SSE format.
    
    Args:
        events: Async generator from graph.astream_events()
        stream: The conversation stream to emit to
        
    Yields:
        StreamMessage objects
    """
    async for event in events:
        event_type = event.get("event")
        
        if event_type == "on_chain_start":
            # Node started
            name = event.get("name", "unknown")
            yield StreamMessage(
                event_type=EventType.PROGRESS,
                checkpoint_type=CheckpointType.IN_PROGRESS,
                content=f"Starting: {name}",
                metadata={"node": name},
            )
        
        elif event_type == "on_chain_end":
            # Node completed
            name = event.get("name", "unknown")
            output = event.get("data", {}).get("output", {})
            
            # Check for interrupt
            if isinstance(output, dict):
                if "__interrupt__" in output:
                    interrupt_data = output["__interrupt__"]
                    yield StreamMessage(
                        event_type=EventType.INTERRUPT,
                        checkpoint_type=CheckpointType.INTERRUPT,
                        content=interrupt_data.get("question", "Interrupt occurred"),
                        requires_input=True,
                        metadata=interrupt_data,
                    )
        
        elif event_type == "on_chat_model_stream":
            # Streaming token from LLM
            chunk = event.get("data", {}).get("chunk")
            if chunk:
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                yield StreamMessage(
                    event_type=EventType.CONTENT,
                    content=content,
                )
        
        elif event_type == "on_tool_start":
            # Tool started
            name = event.get("name", "unknown")
            yield StreamMessage(
                event_type=EventType.PROGRESS,
                checkpoint_type=CheckpointType.IN_PROGRESS,
                content=f"Running tool: {name}",
                metadata={"tool": name},
            )
        
        elif event_type == "on_tool_end":
            # Tool completed
            name = event.get("name", "unknown")
            yield StreamMessage(
                event_type=EventType.PROGRESS,
                checkpoint_type=CheckpointType.IN_PROGRESS,
                content=f"Tool completed: {name}",
                metadata={"tool": name},
            )
