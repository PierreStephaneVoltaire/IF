import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx

TERMINAL = {"succeeded", "failed", "cancelled", "uncertain"}


def wait_for_api(client):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise TimeoutError("API readiness timeout")


def wait_for_job(client, owner, job_id, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/jobs/{job_id}", headers={"X-Person-Pk": owner})
        response.raise_for_status()
        job = response.json()
        if job["status"] in TERMINAL:
            return job
        time.sleep(1)
    raise TimeoutError(f"job {job_id} did not reach a terminal state")


def cancel_and_wait(client, owner, job_id, timeout):
    response = client.post(f"/v1/jobs/{job_id}/cancel", headers={"X-Person-Pk": owner})
    response.raise_for_status()
    return wait_for_job(client, owner, job_id, timeout)


def synthetic_arguments(owner):
    item = {
        "id": "if-rewrite-canary-item",
        "user_pk": owner,
        "name": "Synthetic meet entry",
        "category": "competition",
        "priority_tier": "MANDATORY",
        "cost": 120,
        "currency": "CAD",
        "recurrence": "one_time",
        "date_precision": "day",
        "start_date": "2026-10-01",
        "end_date": None,
        "comp_linked": True,
        "competition_id": "if-rewrite-canary-meet",
        "purchased": False,
        "purchased_date": None,
        "notes": "Synthetic canary input",
        "photo_s3_key": None,
        "cut_by_ai": False,
        "created_at": "2026-09-13T00:00:00Z",
        "updated_at": "2026-09-13T00:00:00Z",
    }
    return {
        "config": {"monthly_cap": 100, "currency": "CAD", "notes": "Synthetic canary"},
        "items": [item],
        "competitions": [{"id": "if-rewrite-canary-meet", "name": "Synthetic Meet", "date": "2026-10-01"}],
        "spent_this_month": 140,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-url", default="http://127.0.0.1:18080")
    parser.add_argument("--pl-url", default="http://127.0.0.1:18081")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--evidence", default="/tmp/if-domain-canary-evidence.json")
    args = parser.parse_args()
    token = os.environ.get("INTERNAL_API_TOKEN")
    if not token:
        raise RuntimeError("INTERNAL_API_TOKEN is required")
    owner = f"if-rewrite-canary-{os.getpid()}-{uuid.uuid4().hex[:10]}"
    headers = {"X-Internal-Token": token, "X-Athlete-Pk": owner, "X-Person-Pk": owner}
    port_forwards = []
    evidence = {"owner": owner, "job_id": None, "status": None, "result": None, "checks": {}}
    try:
        if args.if_url == "http://127.0.0.1:18080":
            port_forwards.append(subprocess.Popen(["kubectl", "port-forward", "-n", "if-portals", "svc/if-agent-api", "18080:8000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if args.pl_url == "http://127.0.0.1:18081":
            port_forwards.append(subprocess.Popen(["kubectl", "port-forward", "-n", "if-portals", "svc/pl-budget", "18081:8000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        with httpx.Client(base_url=args.pl_url, headers={"X-Internal-Token": token}, timeout=30) as pl, httpx.Client(base_url=args.if_url, headers={"X-Internal-Token": token}, timeout=30) as if_client:
            wait_for_api(pl)
            wait_for_api(if_client)
            response = pl.post("/operations/budget_advisor", headers=headers, json=synthetic_arguments(owner))
            response.raise_for_status()
            submitted = response.json()
            job_id = submitted.get("job_id")
            if not job_id:
                raise AssertionError(f"domain did not submit a job: {submitted}")
            evidence["job_id"] = job_id
            evidence["checks"]["accepted_queued_job"] = submitted.get("status") in {"queued", "running"}
            job = wait_for_job(if_client, owner, job_id, args.timeout)
            evidence["status"] = job["status"]
            result_response = if_client.get(f"/v1/jobs/{job_id}/result", headers={"X-Person-Pk": owner})
            result_response.raise_for_status()
            result = result_response.json()
            evidence["result"] = result.get("result")
            content = str((result.get("result") or {}).get("content", ""))
            parsed = json.loads(content)
            typed = isinstance(parsed, dict) and {"overall_assessment", "locked_in", "suggested_cuts", "gaps", "coach_note"}.issubset(parsed)
            evidence["checks"].update({
                "terminal_success": job["status"] == "succeeded",
                "result_endpoint_success": result.get("status") == "succeeded",
                "typed_final_result": typed,
                "synthetic_item_preserved": typed and any(item.get("item_id") == "if-rewrite-canary-item" for item in parsed["locked_in"]),
                "job_id_evidence": job["job_id"] == job_id,
            })
    except Exception as exc:
        evidence["error"] = type(exc).__name__
        if evidence["job_id"] and evidence["status"] not in TERMINAL:
            try:
                with httpx.Client(base_url=args.if_url, headers={"X-Internal-Token": token}, timeout=10) as cleanup:
                    cancelled = cancel_and_wait(cleanup, owner, evidence["job_id"], 30)
                evidence["status"] = cancelled["status"]
                evidence["checks"]["timeout_cancelled"] = cancelled["status"] == "cancelled"
            except Exception as cancel_error:
                evidence["cancel_error"] = type(cancel_error).__name__
        raise
    finally:
        for process in port_forwards:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        try:
            Path(args.evidence).write_text(json.dumps(evidence, indent=2) + "\n")
        except Exception:
            pass
    print(json.dumps({"job_id": evidence["job_id"], "status": evidence["status"], "checks": evidence["checks"], "evidence": args.evidence}, sort_keys=True))
    raise SystemExit(0 if evidence["checks"] and all(evidence["checks"].values()) else 1)


if __name__ == "__main__":
    main()
