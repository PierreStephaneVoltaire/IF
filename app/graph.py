"""LangGraph implementation for the multi-agent FastAPI router.

This module implements the conversation flow using LangGraph with native:
- State management with checkpointer
- Memory (conversation history with add_messages reducer)
- Interrupts for human-in-the-loop
- Checkpoints for persistence
- Graph visualization

Flow:
1. Prepare messages and check token count
2. Condense if needed (100k threshold)
3. Main agent node: IF Prototype A1 as a real LLM agent with tool-calling loop
   - Agent calls categorize_conversation, get_directives, condense_intent, spawn_subagent
   - Agent decides routing and writes the final response in its own voice
4. Generate final response

Workflows (spawned by main agent via spawn_subagent tool):
- simple: Direct agent execution
- sequential_refinement: Planner-executor-evaluator loop (coding)
- opposing_perspective: Two parallel agents with opposing views
- multi_perspective: Multiple agents with aggregation
- research: Research-first approach
"""
from __future__ import annotations
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Annotated, Sequence, Union
from datetime import datetime
from operator import add

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import START, END
from langgraph.types import interrupt, Command

from condenser import estimate_tokens, condense_conversation, TOKEN_THRESHOLD
from persistence import (
    PersistenceManager,
    ConversationState,
    LangGraphState,
    create_persistence_manager,
    get_graph_image,
)
from helpers import get_conversation_hash
from tools.main_agent_tools import ALL_MAIN_AGENT_TOOLS
from tools.tool_executor import (
    execute_categorize,
    execute_get_directives,
    execute_condense_intent,
    execute_spawn_subagent,
)


# Sandbox base directory
SANDBOX_BASE_DIR = Path(__file__).parent / "sandbox"


def merge_dicts(left: Dict, right: Dict) -> Dict:
    """Merge two dictionaries, with right taking precedence."""
    return {**left, **right}


def create_initial_state(messages_dicts: List[Dict[str, Any]], chat_id: str) -> LangGraphState:
    """Create the initial state for a conversation."""
    return {
        # Core conversation state - uses add_messages reducer for memory
        "messages": messages_dicts,
        
        # Session tracking
        "chat_id": chat_id,
        "sandbox_dir": None,
        
        # Conversation tracking
        "conv_hash": "",
        "current_message_count": 0,
        "token_count": 0,
        
        # Condensation
        "was_condensed": False,
        "condensation_summary": None,
        
        # Categorization results
        "category": "",
        "reasoning_pattern": "",
        "condensed_intent": "",
        "applicable_directives": [],
        
        # Workflow execution
        "workflow_result": {},
        "personalized_response": "",
        
        # Final response
        "final_response": {},
        "file_attachments": [],
        "summary": "",
        
        # Interrupt state for human-in-the-loop
        "interrupt_type": None,
        "interrupt_data": None,
        "user_response": None,
        "is_waiting_for_input": False,
        
        # Execution trace
        "execution_trace": [],
        
        # Is last step
        "is_last_step": False,
    }


def node_prepare_messages(state: LangGraphState) -> Dict[str, Any]:
    """Prepare messages, compute hash and token count."""
    start_time = time.perf_counter()
    
    messages = state["messages"]
    conv_hash = get_conversation_hash(messages)
    current_message_count = len(messages)
    token_count = estimate_tokens(messages)
    
    end_time = time.perf_counter()
    
    return {
        "conv_hash": conv_hash,
        "current_message_count": current_message_count,
        "token_count": token_count,
        "execution_trace": ["prepare_messages"],
    }


async def node_initialize_persistence(state: LangGraphState) -> Dict[str, Any]:
    """Initialize persistence manager for the session."""
    start_time = time.perf_counter()
    
    chat_id = state["chat_id"]
    
    # Create persistence manager with LangGraph checkpointer
    persistence = await create_persistence_manager(
        chat_id=chat_id,
        base_dir=str(SANDBOX_BASE_DIR)
    )
    
    # Initialize conversation state
    conv_state = ConversationState(
        conversation_id=chat_id,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        message_count=state["current_message_count"],
        token_count=state["token_count"],
    )
    persistence.save_conversation_state(conv_state)
    
    end_time = time.perf_counter()
    
    return {
        "sandbox_dir": persistence.sandbox_dir,
        "execution_trace": ["init_persistence"],
    }


async def node_condense(state: LangGraphState) -> Dict[str, Any]:
    """Check token count and condense if needed."""
    start_time = time.perf_counter()
    
    messages = state["messages"]
    token_count = state["token_count"]
    
    was_condensed = False
    condensation_summary = None
    final_messages = messages
    
    if token_count >= TOKEN_THRESHOLD:
        print(f"[Graph] Token count {token_count:,} exceeds threshold {TOKEN_THRESHOLD:,}")
        
        result = await condense_conversation(messages)
        final_messages = result.condensed_messages
        was_condensed = True
        condensation_summary = result.summary
        
        print(f"[Graph] Condensed to {result.condensed_tokens:,} tokens")
    
    end_time = time.perf_counter()
    
    return {
        "messages": final_messages,
        "was_condensed": was_condensed,
        "condensation_summary": condensation_summary,
        "execution_trace": ["condense"],
    }


async def node_main_agent(state: LangGraphState) -> Dict[str, Any]:
    """Main agent node — IF Prototype A1 as a real LLM agent with tool-calling loop.

    The LLM receives the main system prompt and all tools, then decides what to call:
    1. categorize_conversation → understand category + reasoning pattern
    2. get_directives → retrieve applicable rules
    3. For social/simple: respond directly in character (no further tools needed)
    4. For complex: condense_intent → spawn_subagent → rewrite output in voice

    The agent IS the personality. No separate rewriter node.
    """
    from categorization import call_openrouter, normalize_messages

    messages = state["messages"]
    sandbox_dir = state.get("sandbox_dir")
    chat_id = state.get("chat_id", "")

    # Load main system prompt
    main_system_prompt_path = Path(__file__).parent / "main_system_prompt.txt"
    main_system_prompt = main_system_prompt_path.read_text(encoding="utf-8")

    # Build initial agent messages: system prompt + conversation history
    normalized = normalize_messages(messages)
    agent_messages: List[Dict[str, Any]] = [
        {"role": "developer", "content": main_system_prompt},
    ] + normalized

    # Tool-calling loop — the LLM decides what to call and when to stop
    MAX_ITERATIONS = 10
    category = ""
    reasoning_pattern = ""
    final_content = "Acknowledged."
    for iteration in range(MAX_ITERATIONS):
        result = await call_openrouter(
            "google/gemini-2.5-flash-lite",
            agent_messages,
            tools=ALL_MAIN_AGENT_TOOLS,
        )
        choice = result.get("choices", [{}])[0]
        message = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "stop")
        tool_calls = message.get("tool_calls") or []

        # Add the assistant turn to history
        agent_messages.append(message)
        if not tool_calls or finish_reason == "stop":
            # LLM produced a final text response — loop ends
            final_content = message.get("content") or "Acknowledged."
            print(f"[MainAgent] Final response after {iteration + 1} iteration(s)")
            break

        # Execute each tool call and feed results back
        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            tool_call_id = tc.get("id", "")
            try:
                tool_args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                tool_args = {}

            print(f"[MainAgent] Tool call: {tool_name}")

            if tool_name == "categorize_conversation":
                tool_result = await execute_categorize(messages)
                category = tool_result["category"]
                reasoning_pattern = tool_result["reasoning_pattern"]
                result_str = json.dumps(tool_result)

            elif tool_name == "get_directives":
                directives = execute_get_directives(
                    tool_args.get("category", category),
                    tool_args.get("reasoning_pattern", reasoning_pattern),
                )
                result_str = json.dumps({"directives": directives})

            elif tool_name == "condense_intent":
                condensed = await execute_condense_intent(messages)
                result_str = json.dumps({"condensed_intent": condensed})

            elif tool_name == "spawn_subagent":
                subagent_result = await execute_spawn_subagent(
                    messages=messages,
                    category=tool_args.get("category", category),
                    reasoning_pattern=tool_args.get("reasoning_pattern", reasoning_pattern),
                    condensed_intent=tool_args.get("condensed_intent", ""),
                    applicable_directives=tool_args.get("applicable_directives", []),
                    sandbox_dir=sandbox_dir,
                    chat_id=chat_id,
                )
                result_str = json.dumps(subagent_result)

            else:
                result_str = json.dumps({"error": f"Unknown tool: {tool_name}"})

            agent_messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result_str,
            })
    print(f"[Response-main] {json.dumps(final_content, indent=2)}")
    
    # Build the workflow_result first
    workflow_result = {
        "content": final_content,
        "success": True,
        "agent_name": "if_prototype_a1",
        "model": "google/gemini-2.5-flash-lite",
        "attachments": [],
        "metadata": {"agent_driven": True},
    }
    
    # Build the final_response here to ensure it's always set
    final_response = {
        "id": f"chatcmpl-{chat_id[:8] if chat_id else 'default'}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "google/gemini-2.5-flash-lite",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": final_content,
                },
                "finish_reason": "stop",
            }
        ],
        "agent_name": "if_prototype_a1",
        "category": category,
        "reasoning_pattern": reasoning_pattern,
        "attachments": [],
    }
    
    print(f"[DEBUG-main_agent] Returning final_response with content: {final_content[:50] if final_content else 'EMPTY'}...")

    return {
        "category": category,
        "reasoning_pattern": reasoning_pattern,
        "condensed_intent": "",
        "applicable_directives": [],
        "workflow_result": workflow_result,
        "personalized_response": final_content,
        "final_response": final_response,  # Add this to ensure it's always set
        "execution_trace": ["main_agent:tool_loop"],
    }


async def node_generate_response(state: LangGraphState) -> Dict[str, Any]:
    """Generate final response with personality applied."""
    start_time = time.perf_counter()
    
    category = state["category"]
    reasoning_pattern = state["reasoning_pattern"]
    workflow_result = state["workflow_result"]
    personalized_response = state["personalized_response"]
    chat_id = state.get("chat_id", "unknown")
    
    # Build final response
    final_response = {
        "id": f"chatcmpl-{chat_id[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": workflow_result.get("model", "unknown"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": personalized_response,
                },
                "finish_reason": "stop",
            }
        ],
        "agent_name": workflow_result.get("agent_name", "unknown"),
        "category": category,
        "reasoning_pattern": reasoning_pattern,
        "attachments": workflow_result.get("attachments", []),
    }
    
    end_time = time.perf_counter()

    print(f"[Response]-generate-res {json.dumps(final_response, indent=2)}")

    return {
        "final_response": final_response,
        "file_attachments": workflow_result.get("attachments", []),
        "summary": personalized_response,
        "is_last_step": True,
        "execution_trace": ["generate_response"],
    }


# Human-in-the-loop interrupt nodes

async def node_plan_review_interrupt(state: LangGraphState) -> Command:
    """Interrupt for plan review - human-in-the-loop checkpoint.
    
    This node uses LangGraph's interrupt mechanism to pause execution
    and wait for user input on the execution plan.
    """
    workflow_result = state["workflow_result"]
    plan = workflow_result.get("metadata", {}).get("plan")
    
    if not plan:
        # No plan to review, continue
        return Command(goto="generate_response")
    
    # Use LangGraph interrupt - this pauses execution and saves checkpoint
    user_response = interrupt({
        "type": "plan_review",
        "plan": plan,
        "question": "Review the execution plan. Would you like to proceed, modify, or cancel?",
        "options": [
            {"id": "proceed", "label": "Proceed with plan"},
            {"id": "modify", "label": "Modify plan"},
            {"id": "cancel", "label": "Cancel execution"},
        ],
    })
    
    # Process user response
    action = user_response.get("action")
    
    if action == "cancel":
        return Command(
            update={
                "interrupt_type": "plan_review",
                "user_response": user_response,
                "workflow_result": {
                    "content": "Execution cancelled by user.",
                    "success": False,
                },
            },
            goto="generate_response",
        )
    elif action == "modify":
        # Store modification request
        return Command(
            update={
                "interrupt_type": "plan_review",
                "user_response": user_response,
            },
            goto="main_agent",  # Re-execute with modifications via main agent
        )
    else:
        # Proceed with plan
        return Command(
            update={
                "interrupt_type": "plan_review",
                "user_response": user_response,
            },
            goto="generate_response",
        )


async def node_question_interrupt(state: LangGraphState) -> Dict[str, Any]:
    """Interrupt for asking questions - human-in-the-loop checkpoint.
    
    This node uses LangGraph's interrupt mechanism to ask the user
    a question and wait for their response.
    """
    interrupt_data = state.get("interrupt_data", {})
    
    # Use LangGraph interrupt
    user_response = interrupt({
        "type": "question",
        "question": interrupt_data.get("question", "Please provide input:"),
        "context": interrupt_data.get("context"),
    })
    
    return {
        "interrupt_type": "question",
        "user_response": user_response,
        "is_waiting_for_input": False,
    }


async def node_options_interrupt(state: LangGraphState) -> Dict[str, Any]:
    """Interrupt for presenting options - human-in-the-loop checkpoint.
    
    This node uses LangGraph's interrupt mechanism to present
    options to the user and wait for their selection.
    """
    interrupt_data = state.get("interrupt_data", {})
    
    # Use LangGraph interrupt
    user_response = interrupt({
        "type": "options",
        "prompt": interrupt_data.get("prompt", "Please select an option:"),
        "options": interrupt_data.get("options", []),
        "allow_custom": interrupt_data.get("allow_custom", True),
    })
    
    return {
        "interrupt_type": "options",
        "user_response": user_response,
        "is_waiting_for_input": False,
    }


def should_interrupt_for_plan_review(state: LangGraphState) -> str:
    """Determine if we should interrupt for plan review."""
    reasoning_pattern = state.get("reasoning_pattern", "")
    workflow_result = state.get("workflow_result", {})
    
    # Only interrupt for sequential_refinement (coding) workflows with plans
    if reasoning_pattern == "sequential_refinement":
        plan = workflow_result.get("metadata", {}).get("plan")
        if plan:
            return "plan_review_interrupt"
    
    return "generate_response"


def build_graph() -> StateGraph:
    """Build the LangGraph conversation flow graph.
    
    This graph uses:
    - LangGraph StateGraph for flow control
    - Checkpointer for persistence
    - Interrupts for human-in-the-loop
    - Memory via add_messages reducer
    
    Flow:
    prepare_messages -> init_persistence -> condense -> main_agent -> 
    [plan_review_interrupt?] -> generate_response -> END
    """
    graph = StateGraph(LangGraphState)
    
    # Add core nodes
    graph.add_node("prepare_messages", node_prepare_messages)
    graph.add_node("init_persistence", node_initialize_persistence)
    graph.add_node("condense", node_condense)
    graph.add_node("main_agent", node_main_agent)
    graph.add_node("generate_response", node_generate_response)
    
    # Add human-in-the-loop interrupt nodes
    graph.add_node("plan_review_interrupt", node_plan_review_interrupt)
    graph.add_node("question_interrupt", node_question_interrupt)
    graph.add_node("options_interrupt", node_options_interrupt)
    
    # Set entry point
    graph.set_entry_point("prepare_messages")
    
    # Add linear edges for main flow
    graph.add_edge("prepare_messages", "init_persistence")
    graph.add_edge("init_persistence", "condense")
    graph.add_edge("condense", "main_agent")
    
    # Conditional edge for plan review interrupt
    graph.add_conditional_edges(
        "main_agent",
        should_interrupt_for_plan_review,
        {
            "plan_review_interrupt": "plan_review_interrupt",
            "generate_response": "generate_response",
        }
    )
    
    graph.add_edge("generate_response", END)
    
    return graph


# Compiled graph cache
_compiled_graph = None
_persistence_managers: Dict[str, PersistenceManager] = {}


def get_graph(checkpointer: Optional[BaseCheckpointSaver] = None):
    """Get or create the compiled graph with optional checkpointer.
    
    Args:
        checkpointer: Optional LangGraph checkpointer for persistence.
                     If provided, enables checkpointing and memory.
    
    Returns:
        Compiled LangGraph with checkpointer if provided
    """
    global _compiled_graph
    
    if checkpointer:
        # Create new compiled graph with checkpointer
        graph = build_graph()
        return graph.compile(checkpointer=checkpointer)
    
    if _compiled_graph is None:
        graph = build_graph()
        _compiled_graph = graph.compile()
    
    return _compiled_graph


async def get_persistence_manager(chat_id: str) -> PersistenceManager:
    """Get or create a persistence manager for a conversation.
    
    This caches persistence managers to reuse the same checkpointer
    across multiple invocations.
    """
    if chat_id not in _persistence_managers:
        _persistence_managers[chat_id] = await create_persistence_manager(
            chat_id=chat_id,
            base_dir=str(SANDBOX_BASE_DIR)
        )
    return _persistence_managers[chat_id]


async def run_conversation_flow(
    messages_dicts: List[Dict[str, Any]],
    chat_id: str,
    enable_interrupts: bool = False,
) -> Dict[str, Any]:
    """Run the full conversation flow through LangGraph.
    
    This uses LangGraph's native features:
    - Checkpointer for persistence and memory
    - Interrupts for human-in-the-loop
    - State management with add_messages reducer
    
    Args:
        messages_dicts: List of message dictionaries
        chat_id: Unique conversation identifier
        enable_interrupts: Whether to enable human-in-the-loop interrupts
        
    Returns:
        Final state dictionary
    """
    # Get persistence manager with checkpointer
    persistence = await get_persistence_manager(chat_id)
    
    # Get compiled graph with checkpointer (async)
    checkpointer = await persistence.get_checkpointer()
    graph = get_graph(checkpointer=checkpointer)
    
    # Get thread config for this conversation
    config = persistence.get_thread_config(chat_id)
    
    # Create initial state
    initial_state = create_initial_state(messages_dicts, chat_id)
    
    # Run the graph
    result = await graph.ainvoke(initial_state, config)
    
    return result


async def run_conversation_flow_streaming(
    messages_dicts: List[Dict[str, Any]],
    chat_id: str,
):
    """Run the conversation flow with streaming support.
    
    This uses LangGraph's streaming API to emit events as they happen.
    
    Args:
        messages_dicts: List of message dictionaries
        chat_id: Unique conversation identifier
        
    Yields:
        Stream events from LangGraph
    """
    # Get persistence manager with checkpointer
    persistence = await get_persistence_manager(chat_id)
    
    # Get compiled graph with checkpointer (async)
    checkpointer = await persistence.get_checkpointer()
    graph = get_graph(checkpointer=checkpointer)
    
    # Get thread config for this conversation
    config = persistence.get_thread_config(chat_id)
    
    # Create initial state
    initial_state = create_initial_state(messages_dicts, chat_id)
    
    # Stream the graph execution
    async for event in graph.astream_events(initial_state, config):
        yield event


async def resume_conversation(
    chat_id: str,
    user_response: Dict[str, Any],
) -> Dict[str, Any]:
    """Resume a conversation after an interrupt.
    
    This is used for human-in-the-loop flows where the user
    has provided input to continue execution.
    
    Args:
        chat_id: Unique conversation identifier
        user_response: User's response to the interrupt
        
    Returns:
        Final state dictionary after resuming
    """
    # Get persistence manager
    persistence = await get_persistence_manager(chat_id)
    
    # Get compiled graph with checkpointer (async)
    checkpointer = await persistence.get_checkpointer()
    graph = get_graph(checkpointer=checkpointer)
    
    # Get thread config for this conversation
    config = persistence.get_thread_config(chat_id)
    
    # Resume the graph with the user's response
    result = await graph.ainvoke(
        Command(resume=user_response),
        config
    )
    
    return result


def get_graph_diagram(output_path: Optional[str] = None) -> Optional[str]:
    """Generate a visual diagram of the conversation graph.
    
    Args:
        output_path: Optional path to save the diagram
        
    Returns:
        Mermaid diagram string or None
    """
    graph = get_graph()
    return get_graph_image(graph, output_path)


async def list_checkpoints(chat_id: str) -> List[Dict[str, Any]]:
    """List all checkpoints for a conversation.
    
    Args:
        chat_id: Unique conversation identifier
        
    Returns:
        List of checkpoint metadata
    """
    if chat_id in _persistence_managers:
        return await _persistence_managers[chat_id].list_checkpoints(chat_id)
    return []


async def get_checkpoint_state(chat_id: str, checkpoint_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get the state at a specific checkpoint.
    
    Args:
        chat_id: Unique conversation identifier
        checkpoint_id: Optional specific checkpoint ID
        
    Returns:
        State at the checkpoint or None
    """
    if chat_id in _persistence_managers:
        persistence = _persistence_managers[chat_id]
        config = persistence.get_thread_config(chat_id)
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        checkpointer = await persistence.get_checkpointer()
        
        # LangGraph checkpointer.aget returns a checkpoint dict
        # The actual state is in the 'channel_values' key
        checkpoint = await checkpointer.aget(config)
        
        print(f"[DEBUG-get_checkpoint_state] checkpoint type: {type(checkpoint)}")
        
        if checkpoint is None:
            print(f"[DEBUG-get_checkpoint_state] No checkpoint found for chat_id: {chat_id}")
            return None
        
        # Checkpoint is a dict with 'channel_values' containing the state
        if isinstance(checkpoint, dict):
            print(f"[DEBUG-get_checkpoint_state] checkpoint keys: {list(checkpoint.keys())}")
            if 'channel_values' in checkpoint:
                state = checkpoint['channel_values']
                print(f"[DEBUG-get_checkpoint_state] state keys from channel_values: {list(state.keys()) if isinstance(state, dict) else 'NOT A DICT'}")
                return state
            # Fallback: return the checkpoint itself
            print(f"[DEBUG-get_checkpoint_state] No channel_values, returning checkpoint directly")
            return checkpoint
        
        # Handle CheckpointTuple object
        if hasattr(checkpoint, 'channel_values'):
            state = checkpoint.channel_values
            print(f"[DEBUG-get_checkpoint_state] state keys from channel_values attr: {list(state.keys()) if isinstance(state, dict) else 'NOT A DICT'}")
            return state
        
        return None
    return None
