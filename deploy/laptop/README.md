# Laptop worker handoff

Laptop deployment is intentionally stopped. The [native main-node rollout](../rewrite/native-rollout.md) passed live acceptance. Prepared laptop manifests now use the same native host image; no laptop deployment has occurred. The updated handoff is `/tmp/if-laptop-handoff.md`; it includes state migration and acceptance requirements. API listeners, history, Facts, Directives and delivery remain on `sirsimpalot-g5-5000`; native thread state and its Conversation mapping move with the host.

## Join and inspect

On the laptop, check `free -h`, `df -h`, and `nproc`. Allow room for the worker's 3 GiB memory limit, 5 GiB persistent state/workspace volume, 1 GiB login/native-state volume, k3s and the operating system. Prevent suspend while it is a worker. The laptop must reach `192.168.2.56:6443`; cluster networking must work in both directions.

Transfer the main node's `/var/lib/rancher/k3s/server/agent-token` privately to `/etc/rancher/k3s/agent-token` on the laptop, owned by root with mode `0600`. Do not paste the token into this document or shell history. Install the same version as the main node, checking the current version first with `kubectl get nodes -o wide`:

```bash
curl -sfL https://get.k3s.io -o /tmp/install-k3s.sh
sudo env INSTALL_K3S_VERSION='v1.34.5+k3s1' \
  K3S_URL='https://192.168.2.56:6443' \
  K3S_TOKEN_FILE='/etc/rancher/k3s/agent-token' \
  sh /tmp/install-k3s.sh agent
```

These options follow the [K3s agent reference](https://docs.k3s.io/cli/agent) and [installation configuration](https://docs.k3s.io/installation/configuration). If the main-node address/version changes, use its actual values.

On the main node, set the joined node's actual name and label it:

```bash
export LAPTOP_NODE='replace-with-joined-node-name'
kubectl wait --for=condition=Ready "node/$LAPTOP_NODE" --timeout=120s
kubectl label node "$LAPTOP_NODE" if.codex/worker=laptop --overwrite
kubectl top nodes
kubectl kustomize deploy/laptop > /tmp/if-laptop-worker.yaml
```

## Persistent subscription login

`login.yaml` prepares a separate laptop login PVC and a laptop-pinned login Pod. Verify its native worker pin against the accepted main-node digest before use. The main-node local-path PVCs cannot move between nodes. Preserve existing Conversations by securely copying BOTH the quiesced login/native-state and host-state volumes to their laptop PVCs, with UID/GID 10001. A fresh subscription login alone does not migrate thread history or mappings. Never run both copies at once.

```bash
kubectl apply -f deploy/laptop/login.yaml
kubectl wait -n if-portals --for=condition=Ready pod/if-codex-login-laptop --timeout=180s
kubectl logs -f -n if-portals pod/if-codex-login-laptop
```

Complete the displayed device-code login using the existing ChatGPT subscription. Its final log must say that subscription authentication and Sol availability were verified. Keep login contents private. For a later login attempt, use a fresh Pod name; retain both login PVCs.

## Move execution and verify

Finish both active native Conversations and drain delivery. Stop the sole host and copy a consistent snapshot of both state trees to `if-codex-login-laptop` and `if-codex-state-laptop`. Verify the laptop overlay pins the accepted native digest. Applying it leaves the host at zero replicas; complete migration and permissions checks before activating it:

```bash
kubectl apply -k deploy/laptop
kubectl scale -n if-portals deployment/if-codex-worker --replicas=1
kubectl rollout status -n if-portals deployment/if-codex-worker --timeout=180s
kubectl get pods -n if-portals -l app=if-codex-worker -o wide
kubectl logs -n if-portals deployment/if-codex-worker --tail=60
kubectl top pod -n if-portals -l app=if-codex-worker
```

Confirm the worker is on the laptop and the existing Conversation resumes on the SAME native thread. Verify cross-node DNS and authenticated HTTP/MCP in both directions, scoped attachments/artifacts, SSE reconnect, native steering/cancellation while full, two active Conversations plus a busy rejection, Luna/Terra delegation, report generation/cache, and login/state survival across an actual Pod restart. Use synthetic Athlete inputs and bounded tests; do not stress test. The former queue canary scripts do not establish native-host acceptance. The local real-SDK harness is `scripts/test_native_conversation_canary.py`; deployed tests must exercise the actual API/host endpoints.

## Rollback

Finish active turns, stop the host, and securely copy BOTH current laptop state trees back to the retained main PVCs before applying the main-node native manifests. Restoring stale state can lose accepted inputs and replay work. With state synchronized and the accepted native image pins in `deploy`, restore placement:

```bash
kubectl scale -n if-portals deployment/if-codex-worker --replicas=0
kubectl apply -k deploy
kubectl scale -n if-portals deployment/if-codex-worker --replicas=1
kubectl rollout status -n if-portals deployment/if-codex-worker --timeout=180s
```

Interrupted or unconfirmed work becomes `uncertain`; inspect side effects before an explicit retry. Preserve all four PVCs and historical databases. Rolling back the execution protocol itself requires the coordinated API/domain rollback in `deploy/rewrite/native-rollout.md`. No Git writes, AWS deletion or Terraform destroy is needed.
