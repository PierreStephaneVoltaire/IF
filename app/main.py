from __future__ import annotations
import os
import json
import asyncio
import hashlib
import sqlite3
from typing import Any, Dict, List, Optional, Union
import httpx
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
import zlib

PROMPTS = json.load(open(os.path.join(os.path.dirname(__file__), "prompts.json")))

CATEGORY_MODEL_MAP = {
    "coding": "openai/gpt-5.2-codex",
    "architecture": "anthropic/claude-opus-4.6",
    "social": "mistralai/mistral-nemo",
    "financial": "perplexity/sonar-deep-research",
    "health": "anthropic/claude-sonnet-4.5",
    "general": "google/gemini-3-flash-preview",
    "shell": "moonshotai/kimi-k2.5"
}

CATEGORIZATION_MODELS = [
    "z-ai/glm-4.7-flash",
    "openai/gpt-oss-120b"    
]

SUMMARIZATION_MODEL = "anthropic/claude-sonnet-4.5"

CATEGORIZATION_PROMPT = open(os.path.join(os.path.dirname(__file__), "categorization_prompt.txt")).read()
MAIN_SYSTEM_PROMPT = open(os.path.join(os.path.dirname(__file__), "main_system_prompt.txt")).read()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY","sk-or-v1-")

DB_PATH = os.path.join(os.path.dirname(__file__), "conversations.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_hash TEXT PRIMARY KEY,
            message_count INTEGER NOT NULL,
            summary TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

app = FastAPI()

# Shared HTTP client for connection pooling
http_client: Optional[httpx.AsyncClient] = None

@app.on_event("startup")
async def startup_event():
    """Initialize shared HTTP client on startup"""
    global http_client
    http_client = httpx.AsyncClient(
        timeout=120.0,
        limits=httpx.Limits(
            max_keepalive_connections=20,
            max_connections=100,
            keepalive_expiry=60.0
        )
    )

@app.on_event("shutdown")
async def shutdown_event():
    """Close shared HTTP client on shutdown"""
    global http_client
    if http_client:
        await http_client.aclose()


class Model(BaseModel):
    id: str
    object: str = "model"
    created: int = 1704067200
    owned_by: str = "openrouter"


class ModelList(BaseModel):
    object: str = "list"
    data: List[Model] = []


@app.get("/api/v1/models", response_model=ModelList)
async def list_models():
    """Return available models for OpenWebUI discovery"""
    return ModelList(
        data=[
            Model(
                id="router",
                owned_by="local"
            )
        ]
    )


@app.get("/api/models", response_model=ModelList)
async def list_models_alias():
    """Alias for /api/v1/models"""
    return await list_models()


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


def normalize_message_content(msg: Message) -> Dict[str, Any]:
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


async def call_openrouter(
    model: str,
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
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
        
    # Use shared HTTP client for connection pooling
    resp = await http_client.post(url, headers=headers, json=payload)
    return resp.json()

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
            "required": ["coding", "architecture", "social", "financial", "health", "general","shell"],
        },
    },
}

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


def get_conversation_hash(messages: List[Dict[str, Any]]) -> str:
    """Generate a hash based on the last message to mark conversation position"""
    if not messages:
        return ""
    last_message = messages[-1]
    content = json.dumps(last_message, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def get_cached_summary(conv_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached summary from database"""
    if not conv_hash:
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT message_count, summary FROM conversations WHERE conversation_hash = ?",
        (conv_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "message_count": row[0],
            "summary": row[1]
        }
    return None


def save_summary(conv_hash: str, message_count: int, summary: str):
    """Save summary to database"""
    if not conv_hash:
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO conversations (conversation_hash, message_count, summary, last_updated)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (conv_hash, message_count, summary)
    )
    conn.commit()
    conn.close()


async def summarize_conversation(messages: List[Dict[str, Any]], existing_summary: Optional[str] = None) -> str:
    """Summarize conversation history, focusing on facts, decisions, and code changes"""
    summary_prompt = """Summarize the following conversation, focusing ONLY on:
- Main facts and information discussed
- list of topics
- Decisions made
- Code files changed or created
- Technical specifications or requirements

Keep it concise and factual. Do not include greetings, pleasantries, or conversational flow.

"""
    if existing_summary:
        summary_prompt += f"Previous summary:\n{existing_summary}\n\nNew messages to add:\n"
    chat_text = "\n".join([
        f"{msg.get('role', 'unknown')}: {msg.get('content', '')}" 
        for msg in messages
    ])
    
    summary_messages = [
        {"role": "user", "content": summary_prompt + chat_text}
    ]
    
    response = await call_openrouter(SUMMARIZATION_MODEL, summary_messages)
    summary = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    return summary


async def categorize(messages: List[Dict[str, str]]) -> Dict[str, float]:
    recent_messages = messages[-5:] if len(messages) > 5 else messages
    chat_history = "\n".join([f"{msg['role']}: {msg.get('content', '')}" for msg in recent_messages])
    prompt = CATEGORIZATION_PROMPT + chat_history
    msgs = [{"role": "user", "content": prompt}]
    tasks = [call_openrouter(model, msgs, CATEGORY_SCHEMA) for model in CATEGORIZATION_MODELS]
    results = await asyncio.gather(*tasks)

    aggregated: Dict[str, List[float]] = {cat: [] for cat in CATEGORY_MODEL_MAP.keys()}
    for i,res in enumerate(results):
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"Model {CATEGORIZATION_MODELS[i]} response: {content}")
        content = clean_json_response(content)
        try:
            scores = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}, content: {content}")
            continue
        for cat in aggregated:
            aggregated[cat].append(float(scores.get(cat, 0)))
    mean_scores = {cat: sum(vals) / len(vals) if vals else 0 for cat, vals in aggregated.items()}
    return mean_scores


@app.post("/api/v1/chat/completions")
async def chat_completions(body: ChatRequest):
    messages_dicts = [normalize_message_content(msg) for msg in body.messages]
    conv_hash = get_conversation_hash(messages_dicts)
    summary = None
    current_message_count = len(messages_dicts)
    
    # Prepare summary logic - use cached immediately, fire background update if needed
    summarization_task = None
    if conv_hash:
        cached = get_cached_summary(conv_hash)
        
        if cached:
            # Use cached summary immediately
            summary = cached.get("summary")
            cached_count = cached["message_count"]
            messages_since_marker = current_message_count - cached_count
            
            # Fire background task to update summary if needed (non-blocking)
            if messages_since_marker > 5:
                messages_to_summarize = messages_dicts[cached_count:-5] if current_message_count > 5 else []
                if messages_to_summarize:
                    # Fire and forget - don't await
                    async def update_summary_background():
                        new_summary = await summarize_conversation(messages_to_summarize, summary)
                        save_summary(conv_hash, current_message_count - 5, new_summary)
                        print(f"Background: Updated summary: {new_summary[:100]}...")
                    
                    summarization_task = asyncio.create_task(update_summary_background())
                    print(f"Using cached summary, updating in background")
            else:
                print(f"Using cached summary (within n-5 tolerance)")
        else:
            # No cache - fire background task for initial summary
            if current_message_count > 5:
                messages_to_summarize = messages_dicts[:-5]
                
                async def create_summary_background():
                    new_summary = await summarize_conversation(messages_to_summarize)
                    save_summary(conv_hash, current_message_count - 5, new_summary)
                    print(f"Background: Created initial summary: {new_summary[:100]}...")
                
                summarization_task = asyncio.create_task(create_summary_background())
                print(f"No cached summary, creating in background")
    
    # Run categorization in parallel (not waiting for summarization)
    mean_scores = await categorize(messages_dicts)
    category = max(mean_scores, key=mean_scores.get)
    print(f"Category: {category}, Scores: {mean_scores}")

    # Build final messages with current summary (if available)
    system_prompt = PROMPTS.get(category, "You are a helpful assistant.")
    if summary:
        system_prompt = f"{system_prompt}\n\nConversation Summary:\n{summary}"
    
    # Replace summarized messages with summary, keep last 5 messages
    if summary and current_message_count > 5:
        # Use only the last 5 messages plus the summary in system prompt
        final_messages = [
            {"role": "developer", "content": system_prompt},
        ] + messages_dicts[-5:]
    else:
        final_messages = [
            {"role": "developer", "content": system_prompt},
        ] + messages_dicts
    
    final_model = CATEGORY_MODEL_MAP[category]
    
    final_response = await call_openrouter(
        final_model,
        final_messages
    )
    
    return final_response
