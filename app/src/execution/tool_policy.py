import json
import sys
from pathlib import Path


def evaluate(event, scopes):
    name = event["tool_name"].split(".")[-1].removeprefix("collaboration")
    role = str(event.get("agent_type") or "")
    child = bool(event.get("agent_id")) and role != "coordinator"
    arguments = event.get("tool_input") or {}
    output = {"hookEventName": "PreToolUse"}
    if name == "spawn_agent":
        selected = arguments.get("agent_type") or arguments.get("task_name", "").split("__")[0]
        if child or selected not in scopes or selected == "coordinator" or selected.startswith("_"):
            output.update(permissionDecision="deny", permissionDecisionReason="Use a registered Specialist slug as task_name, optionally followed by __ and a task suffix.")
        elif arguments.get("model") and scopes.get("_models") and arguments["model"] not in scopes["_models"]:
            output.update(permissionDecision="deny", permissionDecisionReason="Select an available subscription model.")
        elif arguments.get("model") and arguments.get("reasoning_effort") and scopes.get("_models") and arguments["reasoning_effort"] not in scopes["_models"].get(arguments["model"], []):
            output.update(permissionDecision="deny", permissionDecisionReason="Select a supported reasoning effort for this model.")
        else:
            output.update(permissionDecision="allow", updatedInput={**{key: value for key, value in arguments.items() if key != "fork_context"}, "agent_type": selected, "fork_turns": "none"})
    elif child:
        allowed = scopes.get(role, {}).get("tools", [])
        tool = name.removeprefix("mcp__if_tools__")
        if name not in {"wait_agent", "send_message", "list_agents", "wait", "close_agent", "interrupt_agent"} and (not name.startswith("mcp__if_tools__") or tool not in allowed):
            output.update(permissionDecision="deny", permissionDecisionReason="This tool is outside this Specialist's scope.")
        elif name.startswith("mcp__if_tools__"):
            output.update(permissionDecision="allow", updatedInput={**arguments, "__if_scope": {"role": role, "token": scopes[role]["token"]}})
    elif not name.startswith("mcp__if_tools__") and name not in {"wait_agent", "send_message", "followup_task", "list_agents", "wait", "close_agent", "interrupt_agent", "web_search", "web_search_preview", "web__run"}:
        output.update(permissionDecision="deny", permissionDecisionReason="Use scoped IF tools; ambient filesystem and shell access are unavailable.")
    return {"hookSpecificOutput": output}


def scope_path(cwd):
    root = Path(cwd)
    return root.with_name(root.name + ".scopes.json")


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
        scopes = json.loads(scope_path(event["cwd"]).read_text())
        result = evaluate(event, scopes)
        output = result["hookSpecificOutput"]
        with (Path(event["cwd"]) / ".codex/policy-audit.jsonl").open("a") as audit:
            audit.write(json.dumps({**{key: event.get(key) for key in ("agent_id", "agent_type", "tool_name", "tool_use_id")}, "decision": output.get("permissionDecision", "continue"), "reason": output.get("permissionDecisionReason"), "updated_input": "updatedInput" in output}) + "\n")
        if "permissionDecision" in output or "updatedInput" in output:
            print(json.dumps(result))
    except Exception:
        print("Specialist tool policy could not verify this call.", file=sys.stderr)
        sys.exit(2)
