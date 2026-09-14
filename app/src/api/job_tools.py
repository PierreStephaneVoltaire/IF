import asyncio
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .jobs import internal_auth, native
from execution.service import get_execution_service


router = APIRouter(prefix="/v1/turns", tags=["turn tools"])
MEMORY_TOOLS = {
    "user_facts_search": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
    "user_facts_add": {"content": {"type": "string"}, "category": {"type": "string"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
    "user_facts_supersede": {"old_fact_id": {"type": "string"}, "new_content": {"type": "string"}, "reason": {"type": "string"}},
    "capability_gap_log": {"content": {"type": "string"}, "workaround": {"type": "string"}},
}


def role_token(job_id, worker_id, role):
    key = os.environ["INTERNAL_API_TOKEN"].encode()
    return hmac.new(key, f"{job_id}:{worker_id}:{role}".encode(), hashlib.sha256).hexdigest()


def roles():
    from agent.specialists import list_specialists
    return {spec.slug: spec for spec in list_specialists()}


def domain_operations():
    from config import PROJECT_ROOT
    root = Path(os.getenv("PL_OPERATIONS_DIR", str(PROJECT_ROOT / "utils/powerlifting-app/services/operations")))
    return {op["name"]: op for path in root.glob("*.json") for op in json.loads(path.read_text())}


def schemas(role):
    from mcp_runtime import get_mcp_manager
    specs = roles()
    if role != "coordinator" and role not in specs:
        raise HTTPException(404, "Unknown Specialist")
    allowed = set(specs[role].tools) if role != "coordinator" else set().union(*(set(spec.tools) for spec in specs.values()))
    manager = get_mcp_manager()
    external_categories = set(specs[role].mcp_servers) if role != "coordinator" else set().union(*(set(spec.mcp_servers) for spec in specs.values()))
    external_categories.add("time")
    allowed.update(name for name, category in manager.categories_for_names(manager.list_tool_names()).items() if category in external_categories)
    result = {fn["function"]["name"]: {"name": fn["function"]["name"], "description": fn["function"].get("description", ""), "inputSchema": fn["function"]["parameters"]} for fn in get_mcp_manager().tools_for_names(allowed | {"get_current_date"})}
    for name, op in domain_operations().items():
        if name in allowed or role in {"coordinator", "powerlifting_coach", "health_write"}:
            result[name] = {"name": name, "description": op["description"], "inputSchema": op["input_schema"]}
    result["skill_read"] = {"name": "skill_read", "description": "Read an IF thinking workflow before using it", "inputSchema": {"type": "object", "properties": {"name": {"enum": ["deep_think", "sequential_plan", "parallel_analysis"]}}, "required": ["name"], "additionalProperties": False}}
    result["conversation_history"] = {"name": "conversation_history", "description": "Read older history in this Conversation only", "inputSchema": {"type": "object", "properties": {"offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "additionalProperties": False}}
    result["attachment_read"] = {"name": "attachment_read", "description": "Read one uploaded text attachment within this turn", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}}, "required": ["name"], "additionalProperties": False}}
    if role in {"coordinator", "coder", "writer", "health_write", "powerlifting_coach"}:
        result["artifact_write"] = {"name": "artifact_write", "description": "Save a UTF-8 text artifact for delivery in this Conversation", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}}, "required": ["name", "content"], "additionalProperties": False}}
        result["import_attachment"] = {"name": "import_attachment", "description": "Parse an uploaded spreadsheet using the import service, then complete any native inference continuation with domain_resume", "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": False}}
    for name, properties in MEMORY_TOOLS.items():
        result[name] = {"name": name, "description": f"{name} within this Conversation", "inputSchema": {"type": "object", "properties": properties, "additionalProperties": False}}
    if role in {"coordinator", "powerlifting_coach", "health_write"}:
        result["domain_resume"] = {"name": "domain_resume", "description": "Resume an active domain operation with a native Specialist answer, or poll without challenge_id. Never enqueue another job.", "inputSchema": {"type": "object", "properties": {"domain": {"type": "string"}, "execution_id": {"type": "string"}, "challenge_id": {"type": "string"}, "content": {}}, "required": ["domain", "execution_id"]}}
    return result


@router.get("/{job_id}/tool-config", dependencies=[Depends(internal_auth)])
async def tool_config(job_id: str, request: Request, x_worker_id: str = Header()):
    await native(get_execution_service().active_scope, job_id)
    base = os.getenv("IF_API_URL", str(request.base_url).rstrip("/"))
    return {role: {"url": f"{base}/v1/turns/{job_id}/tools/{role}/mcp", "token": role_token(job_id, "native", role), "tools": list(schemas(role))} for role in ["coordinator", *roles()]}


async def call_tool(job, role, name, arguments):
    from jsonschema import validate
    definitions = schemas(role)
    if name not in definitions:
        raise HTTPException(403, "Tool is unavailable to this Specialist")
    if job.request.kind == "domain" and name == job.request.payload.get("operation"):
        arguments = job.request.payload["arguments"]
    validate(arguments, definitions[name]["inputSchema"])
    if name in {"attachment_read", "import_attachment"}:
        from .jobs import artifact_root
        attachment = next((item for item in job.request.payload.get("uploaded_files", []) if item["name"] == arguments["name"]), None)
        if not attachment:
            raise HTTPException(404, "Attachment not found in this turn")
        content = (artifact_root() / "inputs" / attachment["artifact_id"]).read_bytes()
        if name == "attachment_read":
            offset = arguments.get("offset", 0)
            return {"name": attachment["name"], "content": content.decode("utf-8")[offset:offset + 32000], "size": len(content)}
        return await call_tool(job, role, "import_parse_file", {"filename": attachment["name"], "base64_content": base64.b64encode(content).decode(), "pk": job.request.payload.get("athlete", job.owner)})
    if name == "artifact_write":
        from .jobs import artifact_root
        filename = arguments["name"]
        if Path(filename).name != filename or filename in {".", ".."}:
            raise HTTPException(422, "Invalid artifact name")
        content = arguments["content"].encode()
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(413, "Artifact exceeds 25 MiB")
        digest = hashlib.sha256(content).hexdigest()
        artifact_id = hashlib.sha256(filename.encode() + b"\0" + content).hexdigest()
        target = artifact_root() / job.job_id / artifact_id
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        artifact = {"artifact_id": artifact_id, "name": filename, "media_type": "text/plain", "size": len(content), "sha256": digest}
        await get_execution_service().request("POST", f"/turns/{job.job_id}/artifacts", json=artifact)
        return artifact
    if name == "skill_read":
        from config import SKILLS_PATH
        return {"name": arguments["name"], "instructions": (Path(SKILLS_PATH) / arguments["name"] / "SKILL.md").read_text()}
    if name == "conversation_history":
        from flow.history import _load_events
        path = Path(job.request.payload.get("history_path", ""))
        from config import IF_WORKSPACE_BASE
        if not path.is_file() or not path.resolve().is_relative_to(Path(IF_WORKSPACE_BASE).resolve()):
            return []
        history = list(_load_events(path).values())
        offset, limit = arguments.get("offset", 0), arguments.get("limit", 50)
        return history[offset:offset + limit]
    if name in MEMORY_TOOLS:
        from flow import runtime_tool
        function = getattr(runtime_tool, "_" + name)
        from flow.runner import conversation_scope
        scope = job.request.payload.get("memory_scope") or conversation_scope(job.owner, job.request.conversation_id)
        scoped = {**arguments, "context_id": scope, "cache_key": scope, "username": job.owner}
        return await asyncio.to_thread(function, scoped)
    operations = domain_operations()
    if name in operations or name == "domain_resume":
        domain = operations[name]["domain"] if name in operations else arguments["domain"]
        if domain not in {op["domain"] for op in operations.values()}:
            raise HTTPException(404, "Unknown domain")
        namespace = os.getenv("IF_MCP_NAMESPACE", "if-portals")
        base = os.getenv("PL_SERVICE_URL_TEMPLATE", "http://pl-{domain}.{namespace}.svc.cluster.local:8000").format(domain=domain, namespace=namespace)
        path = f"/operations/{name}" if name in operations else f"/executions/{arguments['execution_id']}"
        athlete = job.request.payload.get("athlete", job.owner)
        if job.request.kind == "domain" and name == job.request.payload.get("operation"):
            dispatch = await get_execution_service().request("POST", f"/turns/{job.job_id}/domain-dispatch")
            if not dispatch["dispatch"]:
                return dispatch["result"]
        from api.powerlifting_principal import principal_token
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(base + path, json=arguments, headers={"X-Internal-Token": os.environ["INTERNAL_API_TOKEN"], "X-Athlete-Pk": athlete, "X-Person-Pk": job.owner, "X-PL-Principal": principal_token(job.owner, athlete, name), "X-IF-Turn-Id": job.job_id, **({"X-IF-Generation-Id": job.request.payload.get("generation_id", ""), "X-IF-Generation-Attempt": str(job.request.payload.get("generation_attempt", 0))} if name == job.request.payload.get("operation") else {})})
            response.raise_for_status()
            result = response.json()
            await get_execution_service().request("POST", f"/turns/{job.job_id}/domain-progress", json={**result, "operation": name, "domain": domain, "execution_id": arguments.get("execution_id") or result.get("execution_id")})
            return {**result, "domain": domain} if isinstance(result, dict) and result.get("status") in {"needs_inference", "running"} else result
    from mcp_runtime import get_mcp_manager
    return await get_mcp_manager().call_tool(name, {**arguments, "_conversation_id": job.request.conversation_id, "_user_pk": job.owner})


@router.post("/{job_id}/tools/{role}/mcp")
async def mcp(job_id: str, role: str, request: Request, authorization: str = Header(default="")):
    job = await native(get_execution_service().active_scope, job_id)
    expected = "Bearer " + role_token(job_id, "native", role)
    if not hmac.compare_digest(expected, authorization):
        raise HTTPException(401, "Invalid turn scope")
    body = await request.json()
    request_id, method = body.get("id"), body.get("method")
    if request_id is None:
        return JSONResponse({}, status_code=202)
    if method == "initialize":
        result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "if-scoped-tools", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": list(schemas(role).values())}
    elif method == "tools/call":
        params = body.get("params", {})
        try:
            arguments = dict(params.get("arguments", {}))
            scope = arguments.pop("__if_scope", None)
            if scope is not None:
                scoped_role = str(scope.get("role", ""))
                valid_scope = hmac.compare_digest(role_token(job_id, "native", scoped_role), str(scope.get("token", "")))
                if not valid_scope or (role == "coordinator" and scoped_role == "coordinator") or (role != "coordinator" and scoped_role != role):
                    raise HTTPException(403, "Invalid Specialist scope")
                if role == "coordinator":
                    role = scoped_role
            value = await call_tool(job, role, params.get("name"), arguments)
            result = {"content": [{"type": "text", "text": json.dumps(value, default=str)}], "isError": False}
        except Exception as exc:
            result = {"content": [{"type": "text", "text": json.dumps({"error": str(exc)})}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
