import os
import json
from pathlib import Path
import httpx
from services.principal import principal_token

SERVICES = "program sessions competition federation glossary goals budget calculations performance weight-log templates imports profile lift-profiles analytics videos".split()
PERSON = os.environ.get("POWERLIFTING_TEST_PERSON_PK", "live-acceptance-luna")
ATHLETE = os.environ.get("POWERLIFTING_TEST_ATHLETE_PK", PERSON)

def headers(operation):
    token = os.environ["INTERNAL_API_TOKEN"]
    return {"X-Internal-Token": token, "X-Athlete-Pk": ATHLETE, "X-Person-Pk": PERSON, "X-PL-Principal": principal_token(PERSON, ATHLETE, operation)}

def operation_names(openapi):
    return {path[len("/operations/"):] for path in openapi.get("paths", {}) if path.startswith("/operations/") and path.count("/") == 2}

def internal_only_operations():
    permissions = json.loads((Path(__import__("services").__file__).parent / "permissions.json").read_text())
    return {name for name, rule in permissions.items() if rule.get("internal_only")}

def mcp_tool_names(document):
    return {tool.get("name") for tool in document.get("result", {}).get("tools", []) if tool.get("name")}

def program_sort_key(program):
    for key in ("sk", "program_sk", "sort_key"):
        value = program.get(key)
        if isinstance(value, str) and value:
            return value
    return None

def main():
    client = httpx.Client(timeout=20)
    checks = {}
    internal_only = internal_only_operations()
    for service in SERVICES:
        base = f"http://pl-{service}:8000"
        health = client.get(base + "/health")
        openapi = client.get(base + "/openapi.json")
        denied = client.post(base + "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        mcp = client.post(base + "/mcp", headers=headers("tools_list"), json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        openapi_document = openapi.json() if openapi.status_code == 200 else {}
        operations = operation_names(openapi_document)
        tools = mcp_tool_names(mcp.json()) if mcp.status_code == 200 else set()
        checks[service] = health.status_code == 200 and openapi.status_code == 200 and denied.status_code == 401 and mcp.status_code == 200 and operations - internal_only == tools
        print(service, "PASS" if checks[service] else "FAIL")
    def operation(service, name, payload):
        response = client.post(f"http://pl-{service}:8000/operations/{name}", headers=headers(name), json=payload)
        response.raise_for_status()
        return response.json()
    program_summaries = operation("program", "program_list", {"pk": ATHLETE})
    checks["program_list_http"] = isinstance(program_summaries, dict) and bool(program_summaries.get("programs")) and all(isinstance(item.get("version"), int) and program_sort_key(item) for item in program_summaries["programs"])
    program_list_mcp = client.post("http://pl-program:8000/mcp", headers=headers("program_list"), json={"jsonrpc": "2.0", "id": "program-list-mcp", "method": "tools/call", "params": {"name": "program_list", "arguments": {"pk": ATHLETE}}})
    program_list_mcp.raise_for_status()
    program_list_mcp_result = program_list_mcp.json().get("result", {})
    checks["program_list_mcp"] = program_list_mcp_result.get("isError") is False and bool((program_list_mcp_result.get("structuredContent") or {}).get("programs"))
    programs = operation("program", "program_list_full", {"pk": ATHLETE})
    checks["program_historical_detail"] = bool(programs)
    if programs:
        item = programs[0]
        sort_key = program_sort_key(item)
        checks["program_historical_detail"] = bool(sort_key and isinstance(operation("program", "program_get", {"pk": ATHLETE, "program_sk": sort_key}), dict))
    checks["session_read"] = isinstance(operation("sessions", "session_list", {"pk": ATHLETE, "limit": 1}), dict)
    for name, payload in (("lb_to_kg", {"lb": 220.462}), ("estimate_1rm", {"weight_kg": 100, "reps": 5})):
        http_result = operation("calculations", name, payload)
        mcp = client.post("http://pl-calculations:8000/mcp", headers=headers(name), json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": payload}})
        mcp.raise_for_status()
        structured = mcp.json().get("result", {}).get("structuredContent")
        checks[f"{name}_http_mcp_parity"] = structured == http_result
    print("COUNTS", json.dumps({"services": sum(checks[name] for name in SERVICES), "checks": sum(checks.values()), "total": len(checks)}, sort_keys=True))
    if not all(checks.values()):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
