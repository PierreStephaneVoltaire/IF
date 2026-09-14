import argparse
import json
import os
import uuid
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pk", required=True)
    parser.add_argument("--base-url-template", default="http://pl-{service}:8000")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--evidence", default="/tmp/if-persistence-canary-evidence.json")
    args = parser.parse_args()
    if not args.pk.startswith("if-rewrite-canary-") or args.pk == "operator":
        raise SystemExit("--pk must be an exact synthetic if-rewrite-canary-* key")
    token = os.environ.get("INTERNAL_API_TOKEN")
    if not token:
        raise SystemExit("INTERNAL_API_TOKEN is required")
    headers = {"X-Internal-Token": token, "X-Athlete-Pk": args.pk, "X-Person-Pk": args.pk}
    client = httpx.Client(timeout=30)
    evidence = {"synthetic_pk": args.pk, "calls": [], "program_versions": [], "created": {}, "cleanup": args.cleanup}
    calls = 0

    def call(service, name, payload):
        nonlocal calls
        calls += 1
        if calls > 30:
            raise RuntimeError("bounded call limit exceeded")
        body = {**payload, "pk": args.pk}
        response = client.post(args.base_url_template.format(service=service) + "/operations/" + name, headers=headers, json=body)
        value = response.json()
        evidence["calls"].append({"service": service, "operation": name, "status": response.status_code, "shape": sorted(value) if isinstance(value, dict) else type(value).__name__})
        response.raise_for_status()
        return value

    try:
        call("program", "health_setup_initialize", {"mode": "blank", "program_name": "IF rewrite canary", "start_date": "2026-09-13", "week_start_day": "Monday", "maxes": {}})
        status = call("program", "health_setup_status", {})
        if not status.get("hasCurrentProgram"):
            raise AssertionError("program pointer was not initialized")
        before = call("program", "program_list", {})
        old_sk = (before.get("programs") or [{}])[0].get("sk")
        old_version = (before.get("programs") or [{}])[0].get("version")
        if not old_sk or old_version is None:
            raise AssertionError("program list omitted version identity")
        new_version = call("program", "health_new_version", {"change_reason": "IF rewrite canary version", "patches": []})
        after = call("program", "program_list", {})
        status_after = call("program", "health_setup_status", {})
        versions = after.get("programs") or []
        new_item = next((item for item in versions if item.get("sk") != old_sk), None)
        if not new_item or new_item.get("version", 0) <= old_version:
            raise AssertionError("program version or current pointer did not advance")
        version_labels = {str(new_item.get("version")), f"{new_item.get('version')}.0", str(new_item.get("sk")), str(new_item.get("sk", "")).split("#")[-1]}
        if str(new_version.get("new_version")) not in version_labels:
            raise AssertionError("new version response did not match the listed version")
        new_sk = new_item["sk"]
        evidence["program_versions"] = [{"sk": old_sk, "version": old_version}, {"sk": new_sk, "version": new_item.get("version")}]
        evidence["created"]["program_sk"] = new_sk
        if status_after.get("currentProgramSk") != new_sk:
            raise AssertionError("program pointer did not advance")
        current = call("program", "program_get", {"program_sk": new_sk})
        if current.get("meta", {}).get("version_label") != str(new_version.get("new_version")):
            raise AssertionError("program readback is not the new current version")
        call("program", "program_list_full", {"program_sk": new_sk})
        call("program", "export_program_markdown", {})

        planned = {"exercise": "squat", "sets": 3, "reps": 5, "kg": 80.25}
        executed = {"exercise": "squat", "sets": 3, "reps": 5, "kg": 82.5}
        session = call("sessions", "session_create", {"program_sk": new_sk, "session": {"date": "2026-09-13", "day": "Canary", "week_number": 1, "planned_exercises": [planned], "exercises": [], "session_notes": "synthetic"}})
        session_id = session.get("id") or session.get("session_id")
        if not session_id:
            raise AssertionError("session identity missing")
        evidence["created"]["session_id"] = session_id
        read_planned = call("sessions", "session_get", {"program_sk": new_sk, "date": "2026-09-13", "index": 0})
        if read_planned.get("id") != session_id or read_planned.get("planned_exercises") != [planned]:
            raise AssertionError("planned session readback mismatch")
        patched = call("sessions", "session_patch", {"program_sk": new_sk, "date": "2026-09-13", "index": 0, "patch": {"completed": True, "session_rpe": 7, "exercises": [executed]}})
        if patched.get("id") != session_id:
            raise AssertionError("session identity changed")
        read_executed = call("sessions", "session_get", {"program_sk": new_sk, "date": "2026-09-13", "index": 0})
        full = call("sessions", "session_list_full", {"program_sk": new_sk})
        listed_session = next(item for item in full if item.get("date") == "2026-09-13")
        if read_executed.get("id") != session_id or read_executed.get("exercises") != [executed] or not read_executed.get("completed") or listed_session.get("id") != session_id or listed_session.get("exercises") != [executed]:
            raise AssertionError("executed session readback mismatch")

        goal_id = str(uuid.uuid4())
        evidence["created"]["goal_id"] = goal_id
        call("goals", "goals_replace", {"goals": [{"id": goal_id, "title": "Synthetic canary goal", "goal_type": "custom", "priority": "optional"}]})
        evidence["created"]["goal_created"] = True
        call("goals", "goals_list", {})
        call("goals", "health_get_goals", {})
        budget = call("budget", "budget_create_item", {"item": {"name": "Synthetic canary item", "cost": 1.25, "category": "testing", "priority_tier": "OPTIONAL", "currency": "CAD", "recurrence": "ONE_TIME", "date_precision": "exact", "start_date": "2026-09-13", "end_date": None, "comp_linked": False, "competition_id": None, "purchased": False, "purchased_date": None, "notes": "synthetic", "photo_s3_key": None, "cut_by_ai": False}})
        evidence["created"]["budget_id"] = budget.get("id") or budget.get("item", {}).get("id")
        call("budget", "budget_list_items", {})
        call("budget", "budget_get_config", {})
        call("weight-log", "weight_add_entry", {"entry": {"date": "2026-09-13", "kg": 80.25}})
        evidence["created"]["weight_created"] = True
        call("weight-log", "weight_log_get", {})
        call("weight-log", "weight_get_log", {})
    finally:
        if args.cleanup:
            cleanups = []
            if evidence["created"].get("session_id"):
                cleanups.append(("sessions", "session_delete", {"program_sk": evidence["created"].get("program_sk"), "date": "2026-09-13", "index": 0}))
            if evidence["created"].get("goal_created"):
                cleanups.append(("goals", "goals_replace", {"goals": []}))
            if evidence["created"].get("budget_id"):
                cleanups.append(("budget", "budget_delete_item", {"item_id": evidence["created"]["budget_id"]}))
            if evidence["created"].get("weight_created"):
                cleanups.append(("weight-log", "weight_remove_entry", {"date": "2026-09-13"}))
            for service, operation, payload in cleanups:
                try:
                    call(service, operation, payload)
                except Exception as exc:
                    evidence.setdefault("cleanup_errors", []).append(type(exc).__name__)
        Path(args.evidence).write_text(json.dumps(evidence, indent=2) + "\n")
        client.close()
    if evidence.get("cleanup_errors"):
        raise SystemExit("cleanup failed; inspect evidence")
    print(f"PASS synthetic persistence canary calls={calls} evidence={args.evidence}")


if __name__ == "__main__":
    main()
