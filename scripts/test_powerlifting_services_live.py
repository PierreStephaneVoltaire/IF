import os
import json
import httpx

SERVICES = "program sessions competition federation glossary goals budget calculations performance weight-log templates imports profile lift-profiles analytics videos".split()
TOKEN = os.environ["INTERNAL_API_TOKEN"]
HEADERS = {"X-Internal-Token": TOKEN, "X-Athlete-Pk": "operator", "X-Person-Pk": "operator"}

def main():
    client = httpx.Client(timeout=20)
    checks = {}
    for service in SERVICES:
        base = f"http://pl-{service}:8000"
        health = client.get(base + "/health")
        openapi = client.get(base + "/openapi.json")
        denied = client.post(base + "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        mcp = client.post(base + "/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        paths = openapi.json().get("paths", {}) if openapi.status_code == 200 else {}
        operations = {path.rsplit("/", 1)[-1] for path in paths if path.startswith("/operations/")}
        tools = {item.get("name") for item in mcp.json().get("result", {}).get("tools", [])} if mcp.status_code == 200 else set()
        checks[service] = health.status_code == 200 and openapi.status_code == 200 and denied.status_code == 401 and mcp.status_code == 200 and operations == tools
        print(service, "PASS" if checks[service] else "FAIL")
    def operation(service, name, payload):
        response = client.post(f"http://pl-{service}:8000/operations/{name}", headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()
    program_list = operation("program", "program_list", {"pk": "operator"})
    programs = program_list.get("programs", [])
    checks["program_historical_detail"] = bool(programs)
    if programs:
        item = programs[0]
        sort_key = item.get("program_sk") or item.get("sk") or item.get("sort_key")
        checks["program_historical_detail"] = bool(sort_key and isinstance(operation("program", "program_get", {"pk": "operator", "program_sk": sort_key}), dict))
    checks["session_read"] = isinstance(operation("sessions", "session_list", {"pk": "operator", "limit": 1}), dict)
    for name, payload in (("lb_to_kg", {"lb": 220.462}), ("estimate_1rm", {"weight_kg": 100, "reps": 5})):
        http_result = operation("calculations", name, payload)
        mcp = client.post("http://pl-calculations:8000/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": payload}})
        mcp.raise_for_status()
        structured = mcp.json().get("result", {}).get("structuredContent")
        checks[f"{name}_http_mcp_parity"] = structured == http_result
    print("COUNTS", json.dumps({"services": sum(checks[name] for name in SERVICES), "checks": sum(checks.values()), "total": len(checks)}, sort_keys=True))
    if not all(checks.values()):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
