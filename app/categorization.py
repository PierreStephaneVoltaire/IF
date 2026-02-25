"""Categorization functions for content and reasoning classification.

This module handles the categorization of conversations to route them to the
appropriate agent. The categorization uses multiple models to get consensus
on the category scores.
"""
from __future__ import annotations
import os
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from helpers import clean_json_response as _clean_json_response


def normalize_message(msg: Any) -> Dict[str, Any]:
    """Convert a message (dict or LangChain message object) to a dict.
    
    Args:
        msg: Either a dict with 'role' and 'content' keys, or a LangChain
             message object (HumanMessage, AIMessage, etc.)
    
    Returns:
        Dict with 'role' and 'content' keys
    """
    if isinstance(msg, dict):
        # Ensure required keys exist
        role = msg.get("role") or msg.get("type") or "unknown"
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        return {"role": role, "content": msg.get("content", "")}
    elif hasattr(msg, 'model_dump'):
        # LangChain message object (newer versions)
        dumped = msg.model_dump(exclude_none=True)
        role = dumped.get("role") or dumped.get("type") or "unknown"
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        return {"role": role, "content": dumped.get("content", "")}
    elif hasattr(msg, 'dict'):
        # LangChain message object (older versions)
        dumped = msg.dict()
        role = dumped.get("role") or dumped.get("type") or "unknown"
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        return {"role": role, "content": dumped.get("content", "")}
    elif hasattr(msg, 'content') and hasattr(msg, 'type'):
        # Fallback for LangChain messages
        role = getattr(msg, 'type', 'unknown')
        if role == 'human':
            role = 'user'
        elif role == 'ai':
            role = 'assistant'
        return {"role": role, "content": msg.content}
    else:
        # Last resort
        return {"role": "unknown", "content": str(msg)}


def normalize_messages(messages: List[Any]) -> List[Dict[str, Any]]:
    """Convert a list of messages to list of dicts.
    
    Args:
        messages: List of message dicts or LangChain message objects
        
    Returns:
        List of message dicts
    """
    return [normalize_message(msg) for msg in messages]


# Load prompts from files
CATEGORIZATION_PROMPT = open(os.path.join(os.path.dirname(__file__), "categorization_prompt.txt")).read()
REASONING_CATEGORIZATION_PROMPT = open(os.path.join(os.path.dirname(__file__), "reasoning_categorization_prompt.txt")).read()
COMBINED_CATEGORIZATION_PROMPT = open(os.path.join(os.path.dirname(__file__), "combined_categorization_prompt.txt")).read()
MAIN_SYSTEM_PROMPT = open(os.path.join(os.path.dirname(__file__), "main_system_prompt.txt")).read()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Categories that map to agents
CATEGORIES = [
    "coding",
    "architecture", 
    "social",
    "financial",
    "health",
    "general",
    "shell",
]

# Reasoning patterns
REASONING_PATTERNS = [
    "simple",
    "opposing_perspective",
    "multi_perspective",
    "sequential_refinement",
    "research",
]

# Models used for categorization (cheap, fast models)
CATEGORIZATION_MODELS = [
    "meta-llama/llama-4-maverick",
    "google/gemini-2.5-flash-lite", 
]

# JSON schemas for structured output
CATEGORY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "category_scores",
        "schema": {
            "type": "object",
            "properties": {
                "coding": {"type": "number"},
                "architecture": {"type": "number"},
                "social": {"type": "number"},
                "financial": {"type": "number"},
                "health": {"type": "number"},
                "general": {"type": "number"},
                "shell": {"type": "number"},
            },
            "required": ["coding", "architecture", "social", "financial", "health", "general", "shell"],
        },
    },
}

REASONING_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "reasoning_scores",
        "schema": {
            "type": "object",
            "properties": {
                "simple": {"type": "number"},
                "opposing_perspective": {"type": "number"},
                "multi_perspective": {"type": "number"},
                "sequential_refinement": {"type": "number"},
                "research": {"type": "number"},
            },
            "required": ["simple", "opposing_perspective", "multi_perspective", "sequential_refinement", "research"],
        },
    },
}

# Combined schema: category + reasoning in a single JSON object (Phase 4)
COMBINED_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "combined_scores",
        "schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "object",
                    "properties": {
                        "coding": {"type": "number"},
                        "architecture": {"type": "number"},
                        "social": {"type": "number"},
                        "financial": {"type": "number"},
                        "health": {"type": "number"},
                        "general": {"type": "number"},
                        "shell": {"type": "number"},
                    },
                    "required": ["coding", "architecture", "social", "financial", "health", "general", "shell"],
                },
                "reasoning": {
                    "type": "object",
                    "properties": {
                        "simple": {"type": "number"},
                        "opposing_perspective": {"type": "number"},
                        "multi_perspective": {"type": "number"},
                        "sequential_refinement": {"type": "number"},
                        "research": {"type": "number"},
                    },
                    "required": ["simple", "opposing_perspective", "multi_perspective", "sequential_refinement", "research"],
                },
            },
            "required": ["category", "reasoning"],
        },
    },
}

# Shared HTTP client reference (set by main.py)
http_client: Optional[httpx.AsyncClient] = None


async def call_openrouter(
    model: str,
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Call OpenRouter API."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost",
        "X-Title": "FastAPI Router",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }
    if response_format:
        payload["response_format"] = response_format
    if tools:
        payload["tools"] = tools

    resp = await http_client.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    return resp.json()


# Use the canonical implementation from helpers.py
clean_json_response = _clean_json_response


async def categorize(messages: List[Any]) -> tuple[Dict[str, float], List[Dict[str, Any]]]:
    """Categorize content using all cheap models and return mean scores.
    
    Args:
        messages: List of message dicts or LangChain message objects
        
    Returns:
        Tuple of (mean_scores, debug_info) where debug_info contains model responses
    """
    # Normalize messages to dicts
    normalized_messages = normalize_messages(messages)
    recent_messages = normalized_messages[-5:] if len(normalized_messages) > 5 else normalized_messages
    chat_history = "\n".join([f"{msg['role']}: {msg.get('content', '')}" for msg in recent_messages])
    prompt = CATEGORIZATION_PROMPT + chat_history
    msgs = [{"role": "user", "content": prompt}]
    tasks = [call_openrouter(model, msgs, CATEGORY_SCHEMA) for model in CATEGORIZATION_MODELS]
    results = await asyncio.gather(*tasks)

    aggregated: Dict[str, List[float]] = {cat: [] for cat in CATEGORIES}
    debug_info: List[Dict[str, Any]] = []
    
    for i, res in enumerate(results):
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_debug = {"model": CATEGORIZATION_MODELS[i], "response": content}
        content = clean_json_response(content)
        try:
            scores = json.loads(content)
            model_debug["parsed_scores"] = scores
        except json.JSONDecodeError as e:
            model_debug["error"] = f"Failed to parse JSON: {e}"
            debug_info.append(model_debug)
            continue
        for cat in aggregated:
            aggregated[cat].append(float(scores.get(cat, 0)))
        debug_info.append(model_debug)
    
    mean_scores = {cat: sum(vals) / len(vals) if vals else 0 for cat, vals in aggregated.items()}
    return mean_scores, debug_info


async def categorize_reasoning(messages: List[Any]) -> tuple[Dict[str, float], List[Dict[str, Any]]]:
    """Classify the reasoning pattern scores for the query using all cheap models.
    
    Args:
        messages: List of message dicts or LangChain message objects
        
    Returns:
        Tuple of (mean_scores, debug_info) where debug_info contains model responses
    """
    # Normalize messages to dicts
    normalized_messages = normalize_messages(messages)
    recent_messages = normalized_messages[-5:] if len(normalized_messages) > 5 else normalized_messages
    chat_history = "\n".join([f"{msg['role']}: {msg.get('content', '')}" for msg in recent_messages])
    prompt = REASONING_CATEGORIZATION_PROMPT + chat_history
    msgs = [{"role": "user", "content": prompt}]
    
    tasks = [call_openrouter(model, msgs, REASONING_SCHEMA) for model in CATEGORIZATION_MODELS]
    results = await asyncio.gather(*tasks)
    
    reasoning_patterns = ["simple", "opposing_perspective", "multi_perspective", "sequential_refinement", "research"]
    aggregated: Dict[str, List[float]] = {pattern: [] for pattern in reasoning_patterns}
    debug_info: List[Dict[str, Any]] = []
    
    for i, res in enumerate(results):
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_debug = {"model": CATEGORIZATION_MODELS[i], "response": content}
        content = clean_json_response(content)
        try:
            scores = json.loads(content)
            model_debug["parsed_scores"] = scores
        except json.JSONDecodeError as e:
            model_debug["error"] = f"Failed to parse JSON: {e}"
            debug_info.append(model_debug)
            continue
        for pattern in aggregated:
            aggregated[pattern].append(float(scores.get(pattern, 0)))
        debug_info.append(model_debug)
    
    mean_scores = {pattern: sum(vals) / len(vals) if vals else 0 for pattern, vals in aggregated.items()}
    return mean_scores, debug_info


async def categorize_combined(
    messages: List[Any],
) -> tuple[Dict[str, float], Dict[str, float], List[Dict[str, Any]]]:
    """Categorize content AND reasoning pattern in a single prompt per model.

    This replaces the separate categorize() + categorize_reasoning() calls with
    a single combined prompt, reducing API calls from 6 to 3 (3 models in parallel,
    each returning both category and reasoning scores in one response).

    Args:
        messages: List of message dicts or LangChain message objects

    Returns:
        Tuple of (category_mean_scores, reasoning_mean_scores, debug_info)
    """
    normalized_messages = normalize_messages(messages)
    recent_messages = normalized_messages[-5:] if len(normalized_messages) > 5 else normalized_messages
    chat_history = "\n".join([f"{msg['role']}: {msg.get('content', '')}" for msg in recent_messages])
    prompt = COMBINED_CATEGORIZATION_PROMPT + chat_history
    msgs = [{"role": "user", "content": prompt}]

    tasks = [call_openrouter(model, msgs, COMBINED_SCHEMA) for model in CATEGORIZATION_MODELS]
    results = await asyncio.gather(*tasks)

    cat_aggregated: Dict[str, List[float]] = {cat: [] for cat in CATEGORIES}
    reas_aggregated: Dict[str, List[float]] = {pat: [] for pat in REASONING_PATTERNS}
    debug_info: List[Dict[str, Any]] = []

    for i, res in enumerate(results):
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_debug = {"model": CATEGORIZATION_MODELS[i], "response": content}
        content = clean_json_response(content)
        try:
            parsed = json.loads(content)
            model_debug["parsed_scores"] = parsed
        except json.JSONDecodeError as e:
            model_debug["error"] = f"Failed to parse JSON: {e}"
            debug_info.append(model_debug)
            continue

        cat_scores = parsed.get("category", {})
        reas_scores = parsed.get("reasoning", {})

        for cat in cat_aggregated:
            cat_aggregated[cat].append(float(cat_scores.get(cat, 0)))
        for pat in reas_aggregated:
            reas_aggregated[pat].append(float(reas_scores.get(pat, 0)))

        debug_info.append(model_debug)

    cat_mean = {cat: sum(vals) / len(vals) if vals else 0 for cat, vals in cat_aggregated.items()}
    reas_mean = {pat: sum(vals) / len(vals) if vals else 0 for pat, vals in reas_aggregated.items()}
    return cat_mean, reas_mean, debug_info


# ============================================================================
# Intent Condensation
# ============================================================================

INTENT_CONDENSER_PROMPT = """Summarize the user's intent from this conversation into a clear, actionable prompt.

Rules:
1. Extract the core request/question
2. Include relevant context that affects the answer
3. Remove pleasantries, filler words, and repetition
4. Keep technical details intact
5. Output should be 1-3 sentences maximum
6. Write from the perspective of what a specialized agent needs to know

Example:
Input: "Hey! So I've been thinking about this for a while, and I really need help with my AWS setup. Basically, I have an EC2 instance and I want to connect it to RDS but I'm not sure about the security groups. Can you help me figure out the right configuration? Thanks!"
Output: "Configure AWS security groups to allow EC2 instance to connect to RDS database. Need specific inbound/outbound rules for the connection."

Conversation:
{chat_history}

Condensed intent:"""


async def condense_intent(messages: List[Dict[str, Any]]) -> str:
    """Condense the conversation into a focused intent statement.
    
    This creates a clear, actionable summary that can be passed to
    subagents without the noise of conversational elements.
    
    Args:
        messages: List of conversation messages (dicts or LangChain message objects)
        
    Returns:
        Condensed intent string
    """
    # Normalize messages to dicts
    normalized_messages = normalize_messages(messages)
    recent_messages = normalized_messages[-10:] if len(normalized_messages) > 10 else normalized_messages
    chat_history = "\n".join([
        f"{msg['role'].upper()}: {msg.get('content', '')}" 
        for msg in recent_messages
    ])
    
    prompt = INTENT_CONDENSER_PROMPT.format(chat_history=chat_history)
    msgs = [{"role": "user", "content": prompt}]
    
    # Use a fast model for intent condensation
    result = await call_openrouter("google/gemini-3-flash-preview", msgs)
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    return content.strip()


# ============================================================================
# Directive Extraction — delegated to directive_injector.py (canonical source)
# ============================================================================

def get_applicable_directives(
    category: str,
    reasoning_pattern: str,
) -> List[str]:
    """Get directives applicable to the given category and pattern.

    Delegates to directive_injector.py which is the canonical source.

    Args:
        category: The content category
        reasoning_pattern: The reasoning pattern

    Returns:
        List of directive strings to inject into subagent context
    """
    from directive_injector import get_directive_injector
    injector = get_directive_injector()
    directives = injector.get_directives_for_context(category, reasoning_pattern)
    return [f"Directive {d.id} - {d.title}: {d.content}" for d in directives]
