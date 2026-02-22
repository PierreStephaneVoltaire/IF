"""LangGraph-based persistence module for conversation state and agent data.

This module uses LangGraph's native checkpointer for:
- State persistence (checkpoints)
- Memory management
- Conversation history
- Human-in-the-loop interrupts
- Graph visualization support
"""
from __future__ import annotations
import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Annotated, Sequence
from dataclasses import dataclass, asdict, field

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointMetadata
from langgraph.graph.message import MessagesState, add_messages
from langgraph.managed import IsLastStep
from langgraph.constants import START, END

import sqlite3
import aiosqlite


# Default meta folder name
META_FOLDER = ".meta"
CHECKPOINTS_DB = "checkpoints.db"


@dataclass
class ConversationState:
    """State for a conversation session."""
    conversation_id: str
    created_at: str
    updated_at: str
    message_count: int
    token_count: int
    category: Optional[str] = None
    selected_agent: Optional[str] = None
    status: str = "active"
    summary: Optional[str] = None


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    step_number: int
    description: str
    files_to_create: List[str]
    files_to_modify: List[str]
    acceptance_criteria: List[str]
    dependencies: List[int]
    estimated_complexity: str
    status: str = "pending"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Execution plan for a coding task."""
    task_summary: str
    steps: List[PlanStep]
    estimated_total_steps: int
    potential_challenges: List[str]
    created_at: str
    updated_at: str


@dataclass
class StepEvaluation:
    """Evaluation result for a plan step."""
    step_number: int
    status: str  # approved, needs_revision
    criteria_results: List[Dict[str, Any]]
    issues_found: List[Dict[str, Any]]
    overall_assessment: str
    recommendations: List[str]
    evaluated_at: str


class LangGraphState(TypedDict):
    """LangGraph state for the conversation flow.
    
    This is the main state that flows through all nodes in the graph.
    It includes:
    - Messages (conversation history with add_messages reducer)
    - Memory (persistent across invocations)
    - Interrupt state (for human-in-the-loop)
    - Checkpoint metadata
    """
    # Core conversation state - uses add_messages reducer for memory
    messages: Annotated[List[Dict[str, Any]], add_messages]
    
    # Session tracking
    chat_id: str
    sandbox_dir: Optional[str]
    
    # Conversation tracking
    conv_hash: str
    current_message_count: int
    token_count: int
    
    # Condensation
    was_condensed: bool
    condensation_summary: Optional[str]
    
    # Categorization results
    category: str
    reasoning_pattern: str
    condensed_intent: str
    applicable_directives: List[str]
    
    # Workflow execution
    workflow_result: Dict[str, Any]
    personalized_response: str
    
    # Final response
    final_response: Dict[str, Any]
    file_attachments: List[Dict[str, str]]
    summary: str
    
    # Interrupt state for human-in-the-loop
    interrupt_type: Optional[str]  # "plan_review", "question", "options", "research"
    interrupt_data: Optional[Dict[str, Any]]
    user_response: Optional[Dict[str, Any]]
    is_waiting_for_input: bool
    
    # Execution trace
    execution_trace: List[str]
    
    # Is last step (for graph control)
    is_last_step: bool


class CheckpointManager:
    """Manages LangGraph checkpoints for persistence.
    
    This class wraps LangGraph's checkpointer to provide:
    - SQLite-based persistence for production (async)
    - Memory-based checkpointer for development/testing
    - Checkpoint listing and retrieval
    - Thread-based conversation isolation
    """
    
    def __init__(self, sandbox_dir: str, use_memory: bool = False):
        self.sandbox_dir = Path(sandbox_dir)
        self.meta_dir = self.sandbox_dir / META_FOLDER
        self.checkpoints_path = self.meta_dir / CHECKPOINTS_DB
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._checkpointer_context: Optional[Any] = None
        self._use_memory = use_memory
        
    async def get_checkpointer(self) -> BaseCheckpointSaver:
        """Get or create the checkpointer (async)."""
        if self._checkpointer is None:
            if self._use_memory:
                self._checkpointer = MemorySaver()
            else:
                # Ensure directory exists
                self.meta_dir.mkdir(parents=True, exist_ok=True)
                # Create async SQLite checkpointer
                # from_conn_string returns an async context manager
                self._checkpointer_context = AsyncSqliteSaver.from_conn_string(str(self.checkpoints_path))
                # Enter the context manager to get the actual checkpointer
                self._checkpointer = await self._checkpointer_context.__aenter__()
        return self._checkpointer
    
    async def close(self) -> None:
        """Close the checkpointer context if needed."""
        if self._checkpointer_context is not None:
            await self._checkpointer_context.__aexit__(None, None, None)
            self._checkpointer_context = None
            self._checkpointer = None
    
    def get_thread_config(self, chat_id: str) -> Dict[str, Any]:
        """Get the thread configuration for a conversation.
        
        This is used to isolate state between different conversations.
        """
        return {
            "configurable": {
                "thread_id": chat_id,
            }
        }
    
    async def list_checkpoints(self, chat_id: str) -> List[Dict[str, Any]]:
        """List all checkpoints for a conversation."""
        config = self.get_thread_config(chat_id)
        checkpoints = []
        checkpointer = await self.get_checkpointer()
        # Get checkpoint history
        async for checkpoint in checkpointer.alist(config):
            checkpoints.append({
                "checkpoint_id": checkpoint.config.get("configurable", {}).get("checkpoint_id"),
                "timestamp": checkpoint.metadata.get("created_at"),
                "source": checkpoint.metadata.get("source"),
            })
        return checkpoints
    
    async def get_checkpoint(self, chat_id: str, checkpoint_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific checkpoint state."""
        config = self.get_thread_config(chat_id)
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        checkpointer = await self.get_checkpointer()
        return await checkpointer.aget(config)


class PersistenceManager:
    """Manages persistence using LangGraph's checkpoint system.
    
    This is the main persistence interface that combines:
    - LangGraph checkpointer for state/memory/interrupts
    - File-based storage for plans, reviews, and workspace files
    
    Directory structure:
    {sandbox_dir}/
        .meta/
            checkpoints.db        # LangGraph SQLite checkpointer
            conversation.json     # Conversation metadata
            plans/
                plan.json          # Current execution plan
                current_step.json  # Current step being executed
                step_status.json   # Status of all steps
            reviews/
                step_N_eval.json   # Evaluation for step N
            workspace/
                # Working files for executor
            summary.json           # Final summary
    """
    
    def __init__(self, sandbox_dir: str, use_memory_checkpointer: bool = False):
        self.sandbox_dir = Path(sandbox_dir)
        self.meta_dir = self.sandbox_dir / META_FOLDER
        self.plans_dir = self.meta_dir / "plans"
        self.reviews_dir = self.meta_dir / "reviews"
        self.workspace_dir = self.meta_dir / "workspace"
        self._checkpoint_manager: Optional[CheckpointManager] = None
        self._use_memory_checkpointer = use_memory_checkpointer
    
    @property
    def checkpoint_manager(self) -> CheckpointManager:
        """Get or create the checkpoint manager."""
        if self._checkpoint_manager is None:
            self._checkpoint_manager = CheckpointManager(
                str(self.sandbox_dir),
                use_memory=self._use_memory_checkpointer
            )
        return self._checkpoint_manager
    
    async def get_checkpointer(self) -> BaseCheckpointSaver:
        """Get the LangGraph checkpointer (async)."""
        return await self.checkpoint_manager.get_checkpointer()
    
    def get_thread_config(self, chat_id: str) -> Dict[str, Any]:
        """Get thread configuration for LangGraph."""
        return self.checkpoint_manager.get_thread_config(chat_id)
    
    def initialize(self) -> None:
        """Initialize the persistence directory structure."""
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir.mkdir(exist_ok=True)
        self.reviews_dir.mkdir(exist_ok=True)
        self.workspace_dir.mkdir(exist_ok=True)
    
    # Conversation State
    def save_conversation_state(self, state: ConversationState) -> None:
        """Save conversation state to disk."""
        self.initialize()
        path = self.meta_dir / "conversation.json"
        with open(path, "w") as f:
            json.dump(asdict(state), f, indent=2)
    
    def load_conversation_state(self) -> Optional[ConversationState]:
        """Load conversation state from disk."""
        path = self.meta_dir / "conversation.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return ConversationState(**data)
    
    # Execution Plans
    def save_plan(self, plan: ExecutionPlan) -> None:
        """Save execution plan to disk."""
        self.initialize()
        path = self.plans_dir / "plan.json"
        plan_dict = asdict(plan)
        plan_dict["steps"] = [asdict(s) for s in plan.steps]
        with open(path, "w") as f:
            json.dump(plan_dict, f, indent=2)
    
    def load_plan(self) -> Optional[ExecutionPlan]:
        """Load execution plan from disk."""
        path = self.plans_dir / "plan.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        data["steps"] = [PlanStep(**s) for s in data.get("steps", [])]
        return ExecutionPlan(**data)
    
    def save_current_step(self, step_number: int) -> None:
        """Save the current step being executed."""
        self.initialize()
        path = self.plans_dir / "current_step.json"
        with open(path, "w") as f:
            json.dump({
                "current_step": step_number,
                "updated_at": datetime.utcnow().isoformat()
            }, f, indent=2)
    
    def load_current_step(self) -> int:
        """Load the current step number."""
        path = self.plans_dir / "current_step.json"
        if not path.exists():
            return 0
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("current_step", 0)
    
    def save_step_status(self, step_statuses: Dict[int, str]) -> None:
        """Save status of all steps."""
        self.initialize()
        path = self.plans_dir / "step_status.json"
        with open(path, "w") as f:
            json.dump({
                "statuses": {str(k): v for k, v in step_statuses.items()},
                "updated_at": datetime.utcnow().isoformat()
            }, f, indent=2)
    
    def load_step_status(self) -> Dict[int, str]:
        """Load status of all steps."""
        path = self.plans_dir / "step_status.json"
        if not path.exists():
            return {}
        with open(path, "r") as f:
            data = json.load(f)
        return {int(k): v for k, v in data.get("statuses", {}).items()}
    
    # Evaluations
    def save_evaluation(self, evaluation: StepEvaluation) -> None:
        """Save step evaluation to disk."""
        self.initialize()
        path = self.reviews_dir / f"step_{evaluation.step_number}_eval.json"
        with open(path, "w") as f:
            json.dump(asdict(evaluation), f, indent=2)
    
    def load_evaluation(self, step_number: int) -> Optional[StepEvaluation]:
        """Load evaluation for a step."""
        path = self.reviews_dir / f"step_{step_number}_eval.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return StepEvaluation(**data)
    
    # Summary
    def save_summary(self, summary: Dict[str, Any]) -> None:
        """Save final summary to disk."""
        self.initialize()
        path = self.meta_dir / "summary.json"
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
    
    def load_summary(self) -> Optional[Dict[str, Any]]:
        """Load final summary from disk."""
        path = self.meta_dir / "summary.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            return json.load(f)
    
    # File tracking
    def get_created_files(self) -> List[str]:
        """Get list of files created during execution."""
        # Scan sandbox for files, excluding .meta
        files = []
        for item in self.sandbox_dir.rglob("*"):
            if item.is_file() and not str(item).startswith(str(self.meta_dir)):
                files.append(str(item.relative_to(self.sandbox_dir)))
        return files
    
    def get_file_attachments(self) -> List[Dict[str, str]]:
        """Get file attachments for response."""
        attachments = []
        for file_path in self.get_created_files():
            full_path = self.sandbox_dir / file_path
            try:
                with open(full_path, "r") as f:
                    content = f.read()
                attachments.append({
                    "path": file_path,
                    "content": content,
                    "size": len(content),
                })
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
        return attachments
    
    # Checkpoint operations
    async def list_checkpoints(self, chat_id: str) -> List[Dict[str, Any]]:
        """List all checkpoints for a conversation."""
        return await self.checkpoint_manager.list_checkpoints(chat_id)
    
    async def get_checkpoint(self, chat_id: str, checkpoint_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a specific checkpoint state."""
        return await self.checkpoint_manager.get_checkpoint(chat_id, checkpoint_id)


async def create_persistence_manager(
    chat_id: str,
    base_dir: Optional[str] = None,
    use_memory_checkpointer: bool = False
) -> PersistenceManager:
    """Create a persistence manager for a conversation.
    
    Args:
        chat_id: Chat identifier (required) - used as sandbox folder name
        base_dir: Base directory for sandboxes
        use_memory_checkpointer: Use in-memory checkpointer instead of SQLite
        
    Returns:
        PersistenceManager instance with LangGraph checkpointer
        
    Directory structure:
        {base_dir}/{chat_id}/
            .meta/
                checkpoints.db        # LangGraph SQLite checkpointer
                conversation.json
                plans/
                    plan.json
                    current_step.json
                    step_status.json
                reviews/
                    step_N_eval.json
                workspace/
                summary.json
            (files created by executor)
    """
    from pathlib import Path
    
    # Determine sandbox directory
    if base_dir:
        sandbox_dir = Path(base_dir) / chat_id
    else:
        sandbox_dir = Path(__file__).parent / "sandbox" / chat_id
    
    manager = PersistenceManager(
        str(sandbox_dir),
        use_memory_checkpointer=use_memory_checkpointer
    )
    manager.initialize()
    
    return manager


def get_graph_image(graph, output_path: Optional[str] = None) -> Optional[str]:
    """Generate a visual diagram of the LangGraph graph.
    
    Args:
        graph: The compiled LangGraph
        output_path: Optional path to save the image (PNG)
        
    Returns:
        Base64 encoded image string or None if visualization not available
    """
    try:
        from langgraph.graph.state import CompiledStateGraph
        
        if isinstance(graph, CompiledStateGraph):
            # Get the graph structure as mermaid diagram
            mermaid = graph.get_graph().draw_mermaid()
            
            if output_path:
                # Save mermaid diagram to file
                with open(output_path, "w") as f:
                    f.write(mermaid)
            
            return mermaid
    except Exception as e:
        print(f"Could not generate graph visualization: {e}")
    
    return None
