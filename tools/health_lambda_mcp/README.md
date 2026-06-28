# health_lambda MCP server

HTTP-discovering MCP server for the migrated Powerlifting health Lambda tools.

## Purpose

Replaces the in-process `tools/health` MCP execution path for the **94 migrated tools** (75 deterministic + 19 AI). The IF agent no longer runs these tools in its own pod — they live behind an AWS HTTP API Gateway as one Lambda function per tool.

## How it works

1. On startup, the server fetches `${POWERLIFTING_LAMBDA_BASE_URL}/openapi.json` (served by the `tool_registry` Lambda).
2. Each `POST /<tool>` path becomes an MCP tool exposed to the LLM:
   - `name` = `operationId`
   - `description` = `summary`
   - `inputSchema` = the OpenAPI `requestBody.schema`
3. On a tool call, the server POSTs the args as JSON to `${POWERLIFTING_LAMBDA_BASE_URL}/<tool>`, parses the Lambda response `{"statusCode":200,"body":<json>}`, and returns the body to the LLM.

## Environment

- `POWERLIFTING_LAMBDA_BASE_URL` (required) — HTTP API Gateway endpoint, e.g. `https://abc123.execute-api.ca-central-1.amazonaws.com`
- `INTERNAL_API_TOKEN` (required at the API Gateway layer) — added to the outbound `X-Internal-Token` header so the `pl_authorizer` request authorizer accepts the call

## Registration

Registered as the local MCP category `health_lambda` in `app/src/mcp_runtime/manager.py` (spawned directly from `tools/health_lambda_mcp/server.py` rather than going through `tools/mcp_server.py`) and listed in `app/src/config.py::MCP_SERVER_CATEGORIES`. Per-run `opencode.json` config emits an `if_health_lambda` server entry for the migrated tool names.

## What stays in-process

`health_rag_search` is the one exception — it needs local ChromaDB, so it stays on the original `health` MCP category served by `tools/mcp_server.py health` + `tools/health/tool.py`.