"""Helper functions for the FastAPI router."""
from __future__ import annotations
import json
import hashlib
from typing import Any, Dict, List, Union


def clean_json_response(content: str) -> str:
    """Clean and extract valid JSON from model response."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if len(lines) > 1:
            content = "\n".join(lines[1:])
    if content.endswith("```"):
        content = content[:-3]
    
    content = content.strip()
    json_start = -1
    for i, char in enumerate(content):
        if char in "{[":
            json_start = i
            break
    
    if json_start >= 0:
        content = content[json_start:]
    stack = []
    in_string = False
    escape_next = False
    
    for i, char in enumerate(content):
        if escape_next:
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            continue
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        
        if char in "{[":
            stack.append(char)
        elif char == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif char == "]" and stack and stack[-1] == "[":
            stack.pop()
    
    if stack:
        pass 
    
    return content


def normalize_message_content(msg) -> Dict[str, Any]:
    """Convert Message to dict with proper content structure for OpenRouter"""
    result = {"role": msg.role}
    
    if isinstance(msg.content, list):
        result["content"] = [part.model_dump(exclude_none=True) for part in msg.content]
    elif isinstance(msg.content, str):
        if msg.images:
            content_parts = [{"type": "text", "text": msg.content}]
            for img_url in msg.images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
            result["content"] = content_parts
        else:
            result["content"] = msg.content
    else:
        result["content"] = msg.content
    
    return result


def get_conversation_hash(messages: List[Any]) -> str:
    """Generate a hash based on the last message to mark conversation position.
    
    Handles both dict messages and LangChain message objects (HumanMessage, AIMessage, etc.)
    """
    if not messages:
        return ""
    last_message = messages[-1]
    
    # Handle LangChain message objects
    if hasattr(last_message, 'model_dump'):
        # LangChain message object
        msg_dict = last_message.model_dump(exclude_none=True)
    elif hasattr(last_message, 'dict'):
        # Older LangChain message object
        msg_dict = last_message.dict()
    elif isinstance(last_message, dict):
        # Already a dict
        msg_dict = last_message
    else:
        # Fallback - convert to string representation
        msg_dict = {"content": str(last_message), "role": "unknown"}
    
    content = json.dumps(msg_dict, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()
