"""OpenWebUI message translator.

Converts a debounced OpenWebUI message batch into a ChatCompletionRequest
format that can be processed by the existing agent pipeline.
"""
from __future__ import annotations
from typing import Dict, List, Any


def translate_openwebui_batch(
    messages: List[Dict[str, Any]],
    conversation_id: str,
) -> Dict[str, Any]:
    """Convert OpenWebUI message batch to ChatCompletionRequest format.
    
    Takes a list of raw message dicts from the debounce queue and converts
    them into the same dict structure that POST /v1/chat/completions receives.
    
    Same pattern as Discord translator - strips channel metadata, preserves
    files, and prepends sender attribution.
    
    Args:
        messages: List of message dicts from OpenWebUI listener
        conversation_id: Conversation ID for this batch
        
    Returns:
        Dict matching ChatCompletionRequest shape with messages and metadata
    """
    content_parts: List[Dict[str, Any]] = []

    for msg in messages:
        # Add text content with sender attribution
        text = msg.get("content", "")
        author = msg.get("author", "unknown")
        
        if text:
            content_parts.append({
                "type": "text",
                "text": f"[{author}]: {text}",
            })

        # Handle attachments
        for att in msg.get("attachments", []):
            ct = att.get("content_type", "")
            url = att.get("url", "")
            filename = att.get("filename", "attachment")
            
            if ct.startswith("image/") and url:
                # Image attachments become image_url content
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": url},
                })
            else:
                # Non-image attachments become text references
                content_parts.append({
                    "type": "text",
                    "text": (
                        f"[Attachment: {filename} "
                        f"({ct}) — {url}]"
                    ),
                })

    return {
        "model": "if-prototype",
        "stream": True,
        "messages": [{"role": "user", "content": content_parts}],
        "_conversation_id": conversation_id,
    }
