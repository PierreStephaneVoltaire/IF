import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("rollout_powerlifting.py")
SPEC = importlib.util.spec_from_file_location("rollout_powerlifting", MODULE_PATH)
rollout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rollout)
MANIFEST, CANDIDATES = rollout.load_manifest(MODULE_PATH.with_name("domain-rollout-manifest.json"))


def ready_state(image):
    return {
        "metadata": {"generation": 4},
        "spec": {"replicas": 1, "template": {"spec": {"containers": [{"name": "api", "image": image}]}}},
        "status": {"observedGeneration": 4, "readyReplicas": 1, "availableReplicas": 1, "updatedReplicas": 1},
    }


class RolloutRegressions(unittest.TestCase):
    def test_namespace_is_fixed_before_candidate_gate(self):
        bad = json.loads(json.dumps(MANIFEST))
        bad["namespace"] = "other"
        with self.assertRaisesRegex(rollout.RolloutError, "namespace"):
            rollout.validate_manifest(bad, CANDIDATES)
        with self.assertRaisesRegex(rollout.RolloutError, "allowlist"):
            rollout.validate_selection(MANIFEST, ["if-agent-api"])

    def test_api_preflight_requires_exact_digest_and_ready_state(self):
        deployment_names = {deployment: {container for d, container, _, _ in rollout.entries(MANIFEST) if d == deployment} for deployment, _, _, _ in rollout.entries(MANIFEST)}
        current_api = {"image": MANIFEST["api_image"], "ready": True}

        def fake_kubectl(namespace, *args, input_text=None):
            if args[:2] == ("rollout", "status") or args[:1] == ("exec",):
                return ""
            if args[:2] == ("get", "secret"):
                return json.dumps({"data": {key: "value" for key in MANIFEST["secrets"]["required_keys"]}})
            if args[:2] == ("get", "deployment"):
                deployment = args[2]
                if deployment == "if-agent-api":
                    state = ready_state(current_api["image"])
                    if not current_api["ready"]:
                        state["status"]["readyReplicas"] = 0
                    return json.dumps(state)
                return json.dumps({"spec": {"template": {"spec": {"containers": [{"name": name, "image": "image@sha256:" + "0" * 64} for name in deployment_names[deployment]]}}}})
            raise AssertionError(args)

        with patch.object(rollout, "kubectl", side_effect=fake_kubectl):
            rollout.live_preflight(MANIFEST)
            current_api["image"] = MANIFEST["api_rollback_image"]
            with self.assertRaisesRegex(rollout.RolloutError, "expected immutable digest"):
                rollout.live_preflight(MANIFEST)
            current_api["image"] = MANIFEST["api_image"]
            current_api["ready"] = False
            with self.assertRaisesRegex(rollout.RolloutError, "not Ready"):
                rollout.live_preflight(MANIFEST)
            current_api["image"] = MANIFEST["api_rollback_image"]
            current_api["ready"] = True
            rollout.live_preflight(MANIFEST, rollback=True)

    def test_analytics_patch_is_one_atomic_two_container_change(self):
        images = rollout.validate_manifest(MANIFEST, CANDIDATES, require_acceptance=False)
        payload = rollout.patch_payload(MANIFEST, images, "pl-analytics", False, "2026-09-14T00:00:00Z")
        containers = {item["name"]: item["image"] for item in payload["spec"]["template"]["spec"]["containers"]}
        self.assertEqual(set(containers), {"analytics", "reports"})
        self.assertEqual(payload["spec"]["template"]["metadata"]["annotations"][rollout.ANNOTATION], "2026-09-14T00:00:00Z")
        commands = rollout.command_lines(MANIFEST, images, selected=["pl-analytics"], timestamp="2026-09-14T00:00:00Z")
        self.assertEqual(sum(" patch deployment/pl-analytics " in command for command in commands), 1)
        self.assertFalse(any("set image" in command or "annotate" in command for command in commands))

    def test_dry_run_describes_every_execute_preflight_target_without_secret_values(self):
        images = rollout.validate_manifest(MANIFEST, CANDIDATES, require_acceptance=False)
        lines = rollout.command_lines(MANIFEST, images)
        output = "\n".join(lines)
        self.assertIn("exact recorded API candidate digest", output)
        self.assertIn("Ready state", output)
        self.assertIn("key presence only", output)
        self.assertIn("values withheld", output)
        for deployment, container, _, _ in rollout.entries(MANIFEST):
            self.assertIn(f"{deployment}/{container}", output)
        self.assertEqual(sum(" patch deployment/" in command for command in lines), 18)
        self.assertFalse(any(".data" in command for command in lines))

    def test_frontend_candidate_requires_immutable_existing_repository(self):
        bad = json.loads(json.dumps(CANDIDATES))
        bad["frontend"]["repository"] = "if-powerlifting-app-frontend:latest"
        with self.assertRaisesRegex(rollout.RolloutError, "frontend candidate repository"):
            rollout.validate_manifest(MANIFEST, bad)
        bad = json.loads(json.dumps(CANDIDATES))
        bad["frontend"]["digest"] = "latest"
        with self.assertRaisesRegex(rollout.RolloutError, "frontend candidate digest"):
            rollout.validate_manifest(MANIFEST, bad)

    def test_live_preflight_rejects_wrong_frontend_container(self):
        deployment_names = {deployment: {container for d, container, _, _ in rollout.entries(MANIFEST) if d == deployment} for deployment, _, _, _ in rollout.entries(MANIFEST)}
        def fake_kubectl(namespace, *args, input_text=None):
            if args[:2] == ("rollout", "status") or args[:1] == ("exec",):
                return ""
            if args[:2] == ("get", "secret"):
                return json.dumps({"data": {key: "value" for key in MANIFEST["secrets"]["required_keys"]}})
            if args[:2] == ("get", "deployment"):
                deployment = args[2]
                if deployment == "if-agent-api":
                    return json.dumps(ready_state(MANIFEST["api_image"]))
                containers = [{"name": name, "image": "image@sha256:" + "0" * 64} for name in deployment_names[deployment]]
                if deployment == MANIFEST["frontend"]["deployment"]:
                    containers = [{"name": "wrong", "image": containers[0]["image"]}]
                return json.dumps({"spec": {"template": {"spec": {"containers": containers}}}})
            raise AssertionError(args)
        with patch.object(rollout, "kubectl", side_effect=fake_kubectl), self.assertRaisesRegex(rollout.RolloutError, "container allowlist mismatch"):
            rollout.live_preflight(MANIFEST)

    def test_partial_failure_rollback_execute_emits_manifest_patch_without_real_mutation(self):
        calls = []

        def fake_kubectl(namespace, *args, input_text=None):
            calls.append((namespace, args, input_text))
            if args[:2] == ("patch", "deployment/pl-analytics"):
                raise RuntimeError("simulated partial rollout failure")
            return ""

        with patch.object(rollout, "live_preflight"), patch.object(rollout, "kubectl", side_effect=fake_kubectl), self.assertRaisesRegex(RuntimeError, "partial rollout"):
            rollout.main(["--rollback", "--execute", "--deployment", "pl-analytics"])
        patch_call = next(args for _, args, _ in calls if args[:2] == ("patch", "deployment/pl-analytics"))
        payload = json.loads(patch_call[4])
        images = {item["name"]: item["image"] for item in payload["spec"]["template"]["spec"]["containers"]}
        self.assertTrue(images["analytics"].endswith(MANIFEST["rollback_digests"]["services"]))
        self.assertTrue(images["reports"].endswith(MANIFEST["rollback_digests"]["analytics_sidecar"]))
        self.assertFalse(any(args[:2] == ("set", "image") for _, args, _ in calls))

    def test_execute_and_dry_run_emit_the_same_rollback_patches(self):
        images = rollout.validate_manifest(MANIFEST, CANDIDATES, require_acceptance=False)
        calls = []

        def fake_kubectl(namespace, *args, input_text=None):
            calls.append(args)
            return ""

        with patch.object(rollout, "live_preflight"), patch.object(rollout, "verify_gateway"), patch.object(rollout, "verify_services"), patch.object(rollout, "kubectl", side_effect=fake_kubectl):
            rollout.execute(MANIFEST, images, rollback=True)
        def normalize(payload):
            payload["spec"]["template"]["metadata"]["annotations"][rollout.ANNOTATION] = "<timestamp>"
            return payload

        actual = [(args[1].split("/", 1)[1], normalize(json.loads(args[4]))) for args in calls if args[0] == "patch"]
        dry_run = [(command.split("deployment/", 1)[1].split(" ", 1)[0], normalize(json.loads(command.split("--patch '", 1)[1].rsplit("'", 1)[0]))) for command in rollout.command_lines(MANIFEST, images, rollback=True) if " patch deployment/" in command]
        self.assertEqual(actual, dry_run)


if __name__ == "__main__":
    unittest.main()
