#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE_REPOSITORY = re.compile(r"^[a-z0-9][a-z0-9./_-]*$")
API_DEPLOYMENT = "if-agent-api"
WORKER_DEPLOYMENT = "if-codex-worker"
ANNOTATION = "rollout.powerlifting.dev/restarted-at"
SERVICE_NAMES = "program sessions competition federation glossary goals budget calculations performance weight-log templates imports profile lift-profiles analytics videos".split()


class RolloutError(RuntimeError):
    pass


def load_manifest(path):
    manifest = json.loads(path.read_text())
    candidate_path = path.parent / manifest["candidate_file"]
    candidates = json.loads(candidate_path.read_text())
    return manifest, candidates


def assert_digest(value, label):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise RolloutError(f"{label} is not an immutable sha256 digest")


def assert_repository(value, label):
    if not isinstance(value, str) or not IMAGE_REPOSITORY.fullmatch(value) or "@" in value or ":" in value:
        raise RolloutError(f"{label} is not an existing image repository")


def parse_time(value):
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RolloutError("candidate generated_at is invalid") from exc


def candidate_images(manifest, candidates, require_acceptance=True):
    if require_acceptance and candidates.get("review_status") != manifest["required_review_status"]:
        raise RolloutError("candidate is not accepted by Terra")
    if require_acceptance and candidates.get("repositories_existing_only") is not True:
        raise RolloutError("candidate does not prove existing repositories")
    generated_at = candidates.get("generated_at")
    if require_acceptance and generated_at != manifest["candidate_generated_at"]:
        raise RolloutError("candidate is stale: generated_at does not match the rollout manifest")
    if require_acceptance:
        age = dt.datetime.now(dt.timezone.utc) - parse_time(generated_at)
        if age.total_seconds() < -60 or age.total_seconds() > manifest["max_candidate_age_hours"] * 3600:
            raise RolloutError("candidate is stale by age")
    if require_acceptance and manifest.get("frontend", {}).get("enabled"):
        frontend = candidates.get("frontend", {})
        if frontend.get("review_status") != manifest["required_review_status"]:
            raise RolloutError("frontend candidate is not accepted by Terra")
        assert_repository(frontend.get("repository"), "frontend candidate repository")
        assert_digest(frontend.get("digest"), "frontend candidate digest")
    source = candidates.get("candidates", {})
    images = {}
    if require_acceptance:
        for name, candidate in source.items():
            repository = candidate.get("repository")
            digest = candidate.get("digest")
            assert_repository(repository, f"candidate {name} repository")
            assert_digest(digest, f"candidate {name} digest")
            images[name] = f"{repository}@{digest}"
        if manifest.get("frontend", {}).get("enabled"):
            frontend = candidates["frontend"]
            images["frontend"] = f"{frontend['repository']}@{frontend['digest']}"
        if images != manifest["candidate_images"]:
            raise RolloutError("candidate digest or repository differs from the reviewed rollout manifest")
    if require_acceptance:
        api = candidates.get("api_candidate", {})
        api_repository = api.get("repository")
        api_digest = api.get("digest")
        assert_repository(api_repository, "API candidate repository")
        assert_digest(api_digest, "API candidate digest")
        if f"{api_repository}@{api_digest}" != manifest["api_image"]:
            raise RolloutError("API candidate differs from the reviewed rollout manifest")
        if manifest.get("frontend", {}).get("enabled"):
            if f"{frontend['repository']}@{frontend['digest']}" != manifest["candidate_images"]["frontend"]:
                raise RolloutError("frontend candidate differs from the reviewed rollout manifest")
    else:
        images = dict(manifest["candidate_images"])
        for name, image in images.items():
            repository, digest = image.rsplit("@", 1)
            assert_repository(repository, f"manifest {name} repository")
            assert_digest(digest, f"manifest {name} digest")
    assert_digest(manifest["api_image"].rsplit("@", 1)[1], "manifest API digest")
    assert_digest(manifest["api_rollback_image"].rsplit("@", 1)[1], "manifest API rollback digest")
    for name, digest in manifest["rollback_digests"].items():
        assert_digest(digest, f"rollback {name} digest")
    return images


def entries(manifest):
    result = [(manifest["gateway"]["deployment"], manifest["gateway"]["container"], manifest["gateway"]["candidate"], manifest["gateway"]["rollback"])] + [
        (item["deployment"], container, candidate, item["rollback"][container])
        for item in manifest["services"]
        for container, candidate in item["containers"].items()
    ]
    if manifest.get("frontend", {}).get("enabled"):
        result.append((manifest["frontend"]["deployment"], "frontend", "frontend", "frontend"))
    return result


def validate_manifest(manifest, candidates, require_acceptance=True):
    if manifest.get("namespace") != "if-portals":
        raise RolloutError("namespace is fixed to if-portals")
    images = candidate_images(manifest, candidates, require_acceptance=require_acceptance)
    expected_services = {f"pl-{name}" for name in SERVICE_NAMES}
    expected = {"powerlifting-app-backend", *expected_services}
    if manifest.get("frontend", {}).get("enabled"):
        expected.add(manifest["frontend"]["deployment"])
    actual = {deployment for deployment, _, _, _ in entries(manifest)}
    if actual != expected or len(manifest["services"]) != 16 or [item["deployment"] for item in manifest["services"]] != ["pl-analytics", *(f"pl-{name}" for name in SERVICE_NAMES if name != "analytics")]:
        raise RolloutError("manifest must contain exactly gateway plus sixteen pl-* Deployments")
    if API_DEPLOYMENT in actual or WORKER_DEPLOYMENT in actual or any(name in actual for name in ("all", "--all")):
        raise RolloutError("protected API, worker, and broad targets are forbidden")
    if manifest["gateway"]["deployment"] != "powerlifting-app-backend" or any(not item["deployment"].startswith("pl-") for item in manifest["services"]):
        raise RolloutError("manifest contains a deployment outside the portal allowlist")
    for deployment, container, candidate, rollback in entries(manifest):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", deployment) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", container):
            raise RolloutError("manifest contains an invalid deployment or container name")
        if candidate not in images or rollback not in manifest["rollback_digests"]:
            raise RolloutError(f"{deployment}/{container} has no manifest digest")
    for item in manifest["services"]:
        expected_containers = {"analytics", "reports"} if item["deployment"] == "pl-analytics" else {item["deployment"][3:]}
        if set(item["containers"]) != expected_containers or set(item["rollback"]) != expected_containers:
            raise RolloutError(f"{item['deployment']} container allowlist mismatch")
    return images


def kubectl(namespace, *args, input_text=None):
    command = ["kubectl", "-n", namespace, *args]
    return subprocess.run(command, input=input_text, text=True, check=True, capture_output=True).stdout


def live_preflight(manifest, rollback=False):
    namespace = manifest["namespace"]
    kubectl(namespace, "rollout", "status", f"deployment/{API_DEPLOYMENT}", "--timeout=300s")
    kubectl(namespace, "exec", f"deployment/{API_DEPLOYMENT}", "--", "python", "-c", "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status == 200")
    api_state = json.loads(kubectl(namespace, "get", "deployment", API_DEPLOYMENT, "-o", "json"))
    api_containers = {item["name"]: item["image"] for item in api_state["spec"]["template"]["spec"]["containers"]}
    api_image = api_containers.get(manifest["api_precondition"]["container"])
    expected_api_images = {manifest["api_image"], manifest["api_rollback_image"]} if rollback else {manifest["api_image"]}
    if set(api_containers) != {manifest["api_precondition"]["container"]} or api_image not in expected_api_images:
        raise RolloutError("API is not the expected immutable digest for this protocol state")
    replicas = api_state["spec"].get("replicas", 1)
    status = api_state.get("status", {})
    if any(status.get(key) != replicas for key in ("readyReplicas", "availableReplicas", "updatedReplicas")) or status.get("observedGeneration") != api_state["metadata"].get("generation"):
        raise RolloutError("API is not Ready before the portal cutover")
    secret = json.loads(kubectl(namespace, "get", "secret", manifest["secrets"]["name"], "-o", "json"))
    data = secret.get("data", {})
    missing = {key for key in manifest["secrets"]["required_keys"] if not data.get(key)}
    if missing:
        raise RolloutError(f"{manifest['secrets']['name']} is missing {', '.join(sorted(missing))}; create once through the reviewed protected Terraform plan")
    for deployment in [manifest["gateway"]["deployment"], *(item["deployment"] for item in manifest["services"]), *([manifest["frontend"]["deployment"]] if manifest.get("frontend", {}).get("enabled") else [])]:
        state = json.loads(kubectl(namespace, "get", "deployment", deployment, "-o", "json"))
        names = {item["name"] for item in state["spec"]["template"]["spec"]["containers"]}
        expected = {c for d, c, _, _ in entries(manifest) if d == deployment}
        if names != expected:
            raise RolloutError(f"{deployment} container allowlist mismatch: expected {sorted(expected)}, got {sorted(names)}")


def patch_payload(manifest, images, deployment, rollback, timestamp):
    grouped = [(d, c, candidate, old) for d, c, candidate, old in entries(manifest) if d == deployment]
    if not grouped:
        raise RolloutError(f"deployment is outside the allowlist: {deployment}")
    containers = []
    for _, container, candidate, old in grouped:
        key = old if rollback else candidate
        image = f"{images[candidate].split('@', 1)[0]}@{manifest['rollback_digests'][key]}" if rollback else images[key]
        containers.append({"name": container, "image": image})
    return {"spec": {"template": {"metadata": {"annotations": {ANNOTATION: timestamp}}, "spec": {"containers": containers}}}}


def validate_selection(manifest, selected):
    if selected and any(deployment not in {d for d, _, _, _ in entries(manifest)} for deployment in selected):
        raise RolloutError("deployment is outside the allowlist")


def preflight_summary(manifest, rollback=False):
    api_state = "recorded API candidate or rollback digest" if rollback else "recorded API candidate digest"
    targets = ", ".join(f"{deployment}/{container}" for deployment, container, _, _ in entries(manifest))
    return [
        f"preflight summary: rollout status, /health, exact {api_state}, and Ready state for if-agent-api",
        f"preflight summary: key presence only for {manifest['secrets']['name']} ({', '.join(manifest['secrets']['required_keys'])}); values withheld",
        f"preflight summary: live container allowlist for {targets}",
    ]


def command_lines(manifest, images, rollback=False, selected=None, timestamp=None):
    namespace = manifest["namespace"]
    timestamp = timestamp or dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    wanted = selected or [manifest["gateway"]["deployment"], *(item["deployment"] for item in manifest["services"]), *([manifest["frontend"]["deployment"]] if manifest.get("frontend", {}).get("enabled") else [])]
    lines = preflight_summary(manifest, rollback=rollback) + [
        f"kubectl -n {namespace} rollout status deployment/{API_DEPLOYMENT} --timeout=300s",
        f"kubectl -n {namespace} exec deployment/{API_DEPLOYMENT} -- python -c \"import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status == 200\"",
        f"kubectl -n {namespace} get deployment {API_DEPLOYMENT} -o jsonpath='{{.spec.template.spec.containers[?(@.name==\"api\")].image}}'",
        f"kubectl -n {namespace} get secret {manifest['secrets']['name']} -o name",
    ]
    for deployment in wanted:
        payload = json.dumps(patch_payload(manifest, images, deployment, rollback, timestamp), separators=(",", ":"))
        lines.append(f"kubectl -n {namespace} patch deployment/{deployment} --type=strategic --patch '{payload}'")
        lines.append(f"kubectl -n {namespace} rollout status deployment/{deployment} --timeout=300s")
        if deployment == manifest["gateway"]["deployment"]:
            lines.append(f"kubectl -n {namespace} exec deployment/{deployment} -- node -e \"fetch('http://127.0.0.1:3005/health').then(response => {{ if (!response.ok) process.exit(1) }})\"")
    lines.append(f"kubectl -n {namespace} exec -i deployment/{manifest['verification']['service_probe_deployment']} -- python - < scripts/test_powerlifting_services_live.py")
    return lines


def execute(manifest, images, rollback=False, selected=None):
    live_preflight(manifest, rollback=rollback)
    namespace = manifest["namespace"]
    wanted = selected or [manifest["gateway"]["deployment"], *(item["deployment"] for item in manifest["services"]), *([manifest["frontend"]["deployment"]] if manifest.get("frontend", {}).get("enabled") else [])]
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    for deployment in wanted:
        payload = json.dumps(patch_payload(manifest, images, deployment, rollback, timestamp), separators=(",", ":"))
        kubectl(namespace, "patch", f"deployment/{deployment}", "--type=strategic", "--patch", payload)
        kubectl(namespace, "rollout", "status", f"deployment/{deployment}", "--timeout=300s")
        if deployment == manifest["gateway"]["deployment"]:
            verify_gateway(manifest)
    verify_services(manifest)


def verify_gateway(manifest):
    kubectl(manifest["namespace"], "exec", "deployment/powerlifting-app-backend", "--", "node", "-e", "fetch('http://127.0.0.1:3005/health').then(response => { if (!response.ok) process.exit(1) })")


def verify_services(manifest):
    hook = Path(__file__).resolve().parents[3] / "scripts/test_powerlifting_services_live.py"
    with hook.open() as handle:
        kubectl(manifest["namespace"], "exec", "-i", "deployment/" + manifest["verification"]["service_probe_deployment"], "--", "python", "-", input_text=handle.read())


def self_test(manifest):
    assert len(entries(manifest)) == 19
    assert {entry[0] for entry in entries(manifest)} == {"powerlifting-app-backend", *(item["deployment"] for item in manifest["services"]), "powerlifting-app-frontend"}
    assert DIGEST.fullmatch("sha256:" + "0" * 64)
    try:
        assert_digest("latest", "test")
    except RolloutError:
        pass
    else:
        raise AssertionError("mutable digest accepted")
    print("rollout self-test passed")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("domain-rollout-manifest.json"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--deployment", action="append")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    manifest, candidates = load_manifest(args.manifest)
    if args.self_test:
        self_test(manifest)
        return 0
    images = validate_manifest(manifest, candidates, require_acceptance=not args.rollback)
    if args.rollback and not args.deployment:
        raise RolloutError("--rollback requires at least one --deployment")
    if args.deployment and not args.rollback:
        raise RolloutError("--deployment is only valid with --rollback")
    validate_selection(manifest, args.deployment)
    if args.execute:
        execute(manifest, images, rollback=args.rollback, selected=args.deployment)
        print("powerlifting rollout complete")
    else:
        print("dry-run; no Kubernetes mutation")
        for line in command_lines(manifest, images, rollback=args.rollback, selected=args.deployment):
            print(line)
        print("rerun with --execute after protected approval")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, RolloutError, subprocess.CalledProcessError) as exc:
        print(f"rollout refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
