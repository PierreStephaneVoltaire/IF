
from __future__ import annotations
from typing import List, Optional, Dict, Any, Sequence

from pydantic import Field

from openhands.sdk import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    register_tool,
)
from openhands.sdk.tool import ToolExecutor
from agent.tools.base import TextObservation

from memory.store import get_memory_store



def memory_search(query: str, n_results: int = 5) -> str:

    try:
        store = get_memory_store()
        results = store.search(query, n_results)

        if not results:
            return "No memories found matching that query."

        output_lines = [f"Found {len(results)} relevant memories:", ""]
        for i, entry in enumerate(results, 1):
            output_lines.append(f"{i}. [{entry.category}] {entry.content}")
            if entry.metadata:
                for key, value in entry.metadata.items():
                    output_lines.append(f"   {key}: {value}")

        output_lines.extend([
            "",
            "[Memory results — Directive priority 5. Background context only.",
            "Explicit directives and operator instructions always take precedence.]",
        ])
        return "\n".join(output_lines)
    except Exception as e:
        return f"Error searching memories: {str(e)}"


def memory_add(content: str, category: str, metadata: Optional[Dict[str, Any]] = None) -> str:

    valid_categories = {
        "preference", "personal", "skill_level", "opinion",
        "life_event", "future_plan", "mental_state",
    }
    if category not in valid_categories:
        return f"Invalid category '{category}'. Valid categories: {', '.join(sorted(valid_categories))}"
    try:
        store = get_memory_store()
        entry = store.add(content, category, metadata)
        return f"Memory stored successfully (ID: {entry.id})"
    except Exception as e:
        return f"Error storing memory: {str(e)}"


def memory_remove(memory_id: str, operator_confirmed: bool = False) -> str:

    if not operator_confirmed:
        return (
            "PER DIRECTIVE 0-1: Memory deletion requires explicit operator confirmation.\n"
            f"Memory ID: {memory_id}\n"
            "Please confirm deletion by responding with 'yes' or 'confirm'."
        )
    try:
        store = get_memory_store()
        entry = store.get(memory_id)
        if not entry:
            return f"Memory not found: {memory_id}"
        success = store.remove(memory_id)
        if success:
            return f"Memory removed successfully.\nDeleted: [{entry.category}] {entry.content}"
        return f"Failed to remove memory: {memory_id}"
    except Exception as e:
        return f"Error removing memory: {str(e)}"


def memory_list(category: Optional[str] = None, limit: int = 20) -> str:

    try:
        store = get_memory_store()
        entries = store.list_all(category, limit)
        if not entries:
            return f"No memories found in category '{category}'." if category else "No memories stored yet."
        output_lines = [f"Stored memories ({len(entries)} total):", ""]
        for i, entry in enumerate(entries, 1):
            output_lines.append(f"{i}. [{entry.category}] {entry.content}")
            output_lines.append(f"   ID: {entry.id}")
            output_lines.append(f"   Created: {entry.created_at}")
        return "\n".join(output_lines)
    except Exception as e:
        return f"Error listing memories: {str(e)}"



class MemorySearchAction(Action):
    query: str = Field(description="Semantic search query (e.g., 'programming language preference')")
    n_results: int = Field(default=5, description="Maximum number of results to return")


class MemoryAddAction(Action):
    content: str = Field(description="The memory content to store")
    category: str = Field(
        description=(
            "Category for filtering. One of: preference, personal, skill_level, "
            "opinion, life_event, future_plan, mental_state"
        )
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional additional context")


class MemoryRemoveAction(Action):
    memory_id: str = Field(description="The unique identifier of the memory to remove")
    operator_confirmed: bool = Field(
        default=False,
        description="Must be True to proceed with deletion (Directive 0-1 requires explicit confirmation)",
    )


class MemoryListAction(Action):
    category: Optional[str] = Field(default=None, description="Optional category to filter results")
    limit: int = Field(default=20, description="Maximum number of memories to list")



class MemorySearchObservation(TextObservation):
    pass


class MemoryAddObservation(TextObservation):
    pass


class MemoryRemoveObservation(TextObservation):
    pass


class MemoryListObservation(TextObservation):
    pass



class MemorySearchExecutor(ToolExecutor[MemorySearchAction, MemorySearchObservation]):
    def __call__(self, action: MemorySearchAction, conversation=None) -> MemorySearchObservation:
        result = memory_search(action.query, action.n_results)
        return MemorySearchObservation.from_text(result)


class MemoryAddExecutor(ToolExecutor[MemoryAddAction, MemoryAddObservation]):
    def __call__(self, action: MemoryAddAction, conversation=None) -> MemoryAddObservation:
        result = memory_add(action.content, action.category, action.metadata)
        return MemoryAddObservation.from_text(result)


class MemoryRemoveExecutor(ToolExecutor[MemoryRemoveAction, MemoryRemoveObservation]):
    def __call__(self, action: MemoryRemoveAction, conversation=None) -> MemoryRemoveObservation:
        result = memory_remove(action.memory_id, action.operator_confirmed)
        return MemoryRemoveObservation.from_text(result)


class MemoryListExecutor(ToolExecutor[MemoryListAction, MemoryListObservation]):
    def __call__(self, action: MemoryListAction, conversation=None) -> MemoryListObservation:
        result = memory_list(action.category, action.limit)
        return MemoryListObservation.from_text(result)



class MemorySearchTool(ToolDefinition[MemorySearchAction, MemorySearchObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["MemorySearchTool"]:
        return [cls(
            description=(
                "Search the operator's memory store for relevant context. "
                "Use when the conversation would benefit from knowing the operator's "
                "background, preferences, or history."
            ),
            action_type=MemorySearchAction,
            observation_type=MemorySearchObservation,
            executor=MemorySearchExecutor(),
        )]


class MemoryAddTool(ToolDefinition[MemoryAddAction, MemoryAddObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["MemoryAddTool"]:
        return [cls(
            description=(
                "Store a new memory about the operator. Use when the operator "
                "discloses preferences, events, profession, plans, or other "
                "cross-session context."
            ),
            action_type=MemoryAddAction,
            observation_type=MemoryAddObservation,
            executor=MemoryAddExecutor(),
        )]


class MemoryRemoveTool(ToolDefinition[MemoryRemoveAction, MemoryRemoveObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["MemoryRemoveTool"]:
        return [cls(
            description=(
                "Remove a memory from the store. "
                "REQUIRES EXPLICIT OPERATOR CONFIRMATION per Directive 0-1. "
                "Set operator_confirmed=True only after the operator has confirmed."
            ),
            action_type=MemoryRemoveAction,
            observation_type=MemoryRemoveObservation,
            executor=MemoryRemoveExecutor(),
        )]


class MemoryListTool(ToolDefinition[MemoryListAction, MemoryListObservation]):
    @classmethod
    def create(cls, conv_state=None, **params) -> Sequence["MemoryListTool"]:
        return [cls(
            description="List all stored memories, optionally filtered by category.",
            action_type=MemoryListAction,
            observation_type=MemoryListObservation,
            executor=MemoryListExecutor(),
        )]



register_tool("MemorySearchTool", MemorySearchTool)
register_tool("MemoryAddTool", MemoryAddTool)
register_tool("MemoryRemoveTool", MemoryRemoveTool)
register_tool("MemoryListTool", MemoryListTool)


def get_memory_tools() -> List[Tool]:

    return [
        Tool(name="MemorySearchTool"),
        Tool(name="MemoryAddTool"),
        Tool(name="MemoryRemoveTool"),
        Tool(name="MemoryListTool"),
    ]


def execute_memory_tool(tool_name: str, **kwargs) -> str:

    tool_map = {
        "memory_search": memory_search,
        "memory_add": memory_add,
        "memory_remove": memory_remove,
        "memory_list": memory_list,
        "MemorySearchTool": memory_search,
        "MemoryAddTool": memory_add,
        "MemoryRemoveTool": memory_remove,
        "MemoryListTool": memory_list,
    }
    
    if tool_name not in tool_map:
        raise ValueError(
            f"Unknown memory tool: {tool_name}. "
            f"Available tools: {', '.join(tool_map.keys())}"
        )
    
    tool_func = tool_map[tool_name]
    
    try:
        return tool_func(**kwargs)
    except TypeError as e:
        return f"Error executing {tool_name}: {str(e)}. Check the required parameters."
