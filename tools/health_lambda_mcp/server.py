"""HTTP-discovering MCP server for migrated Powerlifting health Lambda tools."""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

BASE_URL = os.environ.get("POWERLIFTING_LAMBDA_BASE_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("POWERLIFTING_LAMBDA_BASE_URL environment variable is required")


def _fetch(url: str, data: bytes | None = None) -> str:
    headers: dict[str, str] = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def _empty_schema() -> dict[str, Any]:
    return {"type": "object", "properties": {}, "required": []}


def _discover_tools(base: str) -> list[dict[str, Any]]:
    spec = json.loads(_fetch(f"{base}/openapi.json"))
    paths = spec.get("paths") or {}
    tools: list[dict[str, Any]] = []
    for path, item in paths.items():
        post = (item or {}).get("post")
        if not post:
            continue
        name = post.get("operationId") or path.strip("/")
        description = post.get("summary") or name
        schema = (
            (((post.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema")
            or _empty_schema()
        )
        tools.append({"name": name, "description": description, "inputSchema": schema})
    return tools


_DISCOVERED_TOOLS = _discover_tools(BASE_URL)

server = Server("if-health-lambda")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name=t["name"],
            description=t["description"],
            inputSchema=t["inputSchema"],
        )
        for t in _DISCOVERED_TOOLS
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> list[TextContent]:
    body = json.dumps(arguments or {}).encode("utf-8")
    try:
        raw = _fetch(f"{BASE_URL}/{name}", data=body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        return [TextContent(type="text", text=f"HTTP error {exc.code} calling {name}: {exc.reason} {detail}")]
    except urllib.error.URLError as exc:
        return [TextContent(type="text", text=f"URL error calling {name}: {exc.reason}")]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return [TextContent(type="text", text=raw)]
    if not isinstance(parsed, dict):
        return [TextContent(type="text", text=json.dumps(parsed, indent=2, default=str))]
    status = parsed.get("statusCode")
    body_field = parsed.get("body")
    if status == 200 and isinstance(body_field, str):
        try:
            result = json.loads(body_field)
        except json.JSONDecodeError:
            result = body_field
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    if status is not None and status != 200:
        msg = body_field if isinstance(body_field, str) else json.dumps(parsed, default=str)
        return [TextContent(type="text", text=f"Tool {name} failed (status {status}): {msg}")]
    if isinstance(body_field, str):
        try:
            return [TextContent(type="text", text=json.dumps(json.loads(body_field), indent=2, default=str))]
        except json.JSONDecodeError:
            return [TextContent(type="text", text=body_field)]
    return [TextContent(type="text", text=json.dumps(parsed, indent=2, default=str))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())