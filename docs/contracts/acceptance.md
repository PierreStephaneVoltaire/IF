# Rewrite verification — 2026-09-13 (final checks 2026-09-14 UTC)

This is the preceding deployment’s acceptance record. New native-host implementation and canary results are recorded separately in [native-conversations.md](native-conversations.md); that protected rollout has not occurred.

The IF and Powerlifting rewrite is implemented and has passed controlled main-node canaries. The operator approved the reviewed targeted API deployment. The final API rollout completed successfully; API startup and deployed runtime hashes were verified. Laptop deployment is deferred at the operator's request.

No Git writes or AWS resource deletions were performed. Existing Authentik/Postgres edits and all databases/PVCs were preserved. Existing Athlete partitions were read only; persistence tests used a new synthetic Athlete. Four obsolete execution Directives were revised atomically, retaining their original versions.

## Offline and image verification

| Check | Result |
| --- | --- |
| IF suite | 35 passed, including strict classifier schemas, gateway lifecycle, slash attachments/autocomplete, authentication/limit errors and background priority |
| Powerlifting suite | 92 passed, plus 7 subtests |
| Backend forwarding | 6 passed, including one-job Specialist inference submission and failed-job propagation |
| Canary evidence parser | 7 passed, including split streaming deltas and bounded EOF handling |
| Backend/frontend typechecks | Passed |
| Required npm run build | Passed, including frontend/PWA |
| Contract coverage | 16 domains, 200 operations, 169 literal backend callers |
| Baseline function mapping | All 3,951 Python functions have current replacement targets |
| Terraform format/validate | Passed; existing ignored settings have obsolete undeclared-variable warnings |
| Images | API, worker, sixteen-domain image, Analytics sidecar and production portal images built |
| Native SDK | Pinned openai-codex==0.154.0; actual Sol subscription completion and distinct Luna/Terra child contexts passed |
| Tool isolation | Allowed scoped MCP calls passed; forbidden cross-role calls and child shell/file calls were denied |
| Filesystem sandbox | Final worker image: workspace writes passed; protected sibling overwrite denied; Tini reaped orphan processes |
| Laptop manifests | Rendered and checked for pinned image, refreshed registry secret, laptop selector and separate login PVC |

The API, final worker and both portal deployments are Ready with zero restarts; all sixteen domain Deployments are Ready. Final node conditions report no memory, disk or PID pressure.

The bounded worker uses 2 CPU and 3 GiB limits, a 2 GiB temporary workspace and a 1 GiB login PVC. Initial local checks measured about 22 GiB available memory on the 32 GiB main node. Live operation and image builds were monitored without stress tests or changes to host security profiles. These measurements establish no laptop capacity claim.

The SDK's per-turn workspace preset resets custom filesystem flags. The worker configures the thread once and inherits its policy for the turn. Landlock permits writes only in the fresh workspace; role credentials stay in a protected sibling file. The native hook and server-side role tokens enforce Specialist tools. Hosted read-only web search remains available. No paid API fallback is configured.

## Final deployed images

| Component | Immutable digest |
| --- | --- |
| IF API | `sha256:d5bd14ff1e1dd67d87ea52cc6347697afd8fc5795757245d430c260cf75f4ffb` |
| Codex worker | `sha256:854cdab74660235823c651a8404569d99211704fa48dff3c848bde03be592879` |
| 16 Powerlifting services | `sha256:7240ef2dfafa7da711fb6cd955058b9ed14a174f020f649037de2cf2edd85358` |
| Analytics sidecar | `sha256:86392cf5556d31f063b83a73cb493cf4c14a1e7cff2d969b2bf70b2a910a502e` |
| Portal backend | `sha256:1dafe860d461f573fc1255dc273a0a08657936ed987f945d803ab5fa677e303e` |
| Portal frontend | `sha256:77ca2a7676531ce8157707610479ddeb11eae3761f3a14950736e9741fc8050d` |

The final worker cancellation job was `d72f25ae8c6f42fca9fba7c7249a5252`. Temporary diagnostic collection was removed after the queue was idle; one worker remains on the main node.

## Main-node evidence

The operator's Meta-channel greeting exposed an invalid `decisions.items` schema after the original acceptance checks. The corrected schema passed a regression that failed on the original code, live greeting/task worker canaries, and a post-deployment greeting through the actual classifier, subscription queue and DynamoDB execution store. Batch `182ddd67-7c10-4b2e-a15c-b1be6dcaa30d` returned `social_response` with “Greetings.” and its completed batch/intent were read back consistently. The synthetic records have the store's normal TTL; no Discord test message was sent. Evidence: `/tmp/if-meta-acceptance.json`, `/tmp/if-meta-deployed-canary.log`, `/tmp/if-classifier-live-evidence.json`, `/tmp/if-meta-regression-tests.log`.

The first image build triggered disk pressure and API eviction. Operator-requested Docker pruning reclaimed 36.96 GB; the API/worker recovered after pressure cleared. Image publishing was retried after concurrent cleanup caused a missing layer. The final image was checked in a bounded pod before the targeted rollout. The node now reports no memory, disk or PID pressure. Details and private logs are in [the deployment review](../../deploy/rewrite/api-plan-review.md).

| Live check | Result / evidence |
| --- | --- |
| Sixteen services | All Ready; health, OpenAPI, HTTP/MCP inventory, authenticated discovery and unauthenticated rejection passed |
| Deterministic parity | Exact HTTP/MCP lb_to_kg and estimate_1rm results; 20/20 aggregate service checks |
| Existing data | Scoped Program/version, Session, Profile, Federation, Glossary and Competition reads passed |
| Program/Session repair | Correct full-Program result schema; omitted/current/program#current Session queries each return the same 453 Sessions |
| Synthetic persistence | 27 calls: Program v001→v002/current pointer/export, stable Session ID, planned 80.25 vs executed 82.5, Goals/Budget/Weight read/write |
| Queue | Foreground priority, one active claim, idempotency, queued cancellation, lost lease→uncertain, no replay, late result 409 |
| Running cancellation | Final worker: actual streamed SDK marker, cancel_requested→uncertain/cancelled_during_execution and owner rejection; 7/7 checks, PID 1 Tini, zero defunct processes. Earlier post-cancellation native calculation returned 114.3 kg |
| General IF | Actual streamed subscription response and completion marker passed |
| Native Specialist | Powerlifting child executed scoped deterministic 1RM calculation successfully |
| Report | Native calculation results for 90/95/100 kg, report artifact download, job status/result, owner 404 and queued cancellation; 13/13 aggregate checks |
| Domain AI continuation | Budget advisor returned a typed report through exactly one top-level IF job, native inference and domain_resume |
| Technical work + memory | Sol created add.py, a distinct Terra child reviewed it, authenticated artifact/hash/assertions passed; scoped synthetic Fact add/search passed |
| Directives | Four v001 originals retained; v002 versions active, all metadata/scope retained, live loader verified |
| Subscription failure | Actual SDK preflight with an isolated empty login home returned subscription_required; real login PVC unchanged |
| Backgrounds | Reflection completed its periodic cycle; Heartbeat started; all three background callers have offline priority checks |
| Discord | Shared gateway connected; restart/channel routing and slash import/autocomplete tests passed; autocomplete also read five templates from the authenticated live service |
| Portal | Authenticated Program/Session gateway reads and unauthenticated write rejection passed; HTML/PWA/media configuration passed |
| Browser | Chromium loaded /, /designer, /sessions, /analysis and /designer/templates with the read-only banner; no mutation requests |
| MCP providers | Yahoo initialize/list_tools passed with 10 tools; Alpha wrapper passed with a dummy key, but usable Alpha credentials are absent |

The persistence canary used `if-rewrite-canary-e7644afda0d4415f82f8c4455360c172`. Its Session, Goal, Budget item and Weight entry were cleaned through domain operations, and follow-up reads confirmed zero remaining test entries. Its two Program versions remain because there is no Program-delete operation. A separate synthetic Conversation retains the requested test Fact. No existing Athlete partition was mutated.

The IF report canary initially reported three failures in its evidence parser: it required the literal string e1rm in prose, and mismatched an inner MCP UUID with the SDK's outer call ID. The parser was fixed and independently tested against positive/negative fixtures. The same completed live jobs were rechecked: all 13 checks passed. The running-cancellation harness also needed to concatenate streamed marker chunks; its corrected parser has split-chunk, nondelta and stream-end checks, and the live rerun passed. This is a correction of evidence matching, not a claim that the original script invocation exited successfully.

Private evidence is retained on the main host:

- `/tmp/if-live-canary-evidence.json` and original parser report
- `/tmp/if-domain-canary-evidence.json`
- `/tmp/if-technical-canary-evidence.json`
- `/tmp/if-persistence-canary-evidence.json`
- `/tmp/if-queue-canary-evidence.json`
- `/tmp/if-running-cancel-evidence.json` and `/tmp/if-final-scoped-canary-evidence.json`
- `/tmp/if-execution-directive-migration-v3.json` and its guarded migration/rollback script
- `/tmp/if-final-images.json`, `/tmp/if-final-main-node-acceptance.json`, build/test logs and independent Terra reviews

## Retirement and retained state

After successful live replacement checks, the exact 35 Fission Functions, 35 HTTPTriggers, one Package and one Environment were removed, followed by 71 independently reviewed Fission compute objects. Function-owned generated workloads disappeared. The Fission namespace, CRDs, Helm release archive and Bound 5 GiB storage PVC/PV remain. Helm uninstall was not used because it would remove that PVC. All AWS resources remain.

Obsolete OpenCode/Fission execution and packaging source was removed from the working trees into the recoverable `/tmp/if-legacy-retired-20260913/` quarantine. Domain handlers, layers, historical data and both Git repositories remain. Terraform retains the namespace/AWS addresses and records `removed { lifecycle { destroy = false } }` for the old Helm release; reconciling unrelated retirement bookkeeping is outside the approved API targets.

The API uses Recreate and an image-build checksum so a rollout has one writer for conversation/LanceDB storage and one Discord gateway. The historical rollout bookkeeping now waits for rollout status instead of triggering a second restart. The worker/domain/portal workloads use the existing refreshed `ecr-registry` pull secret.

## Limits and deferred acceptance

A test Discord destination has not been authorized, so an actual test message's reception/delivery is not claimed. Full OAuth login and all browser mutation workflows were not exercised. Real subscription exhaustion was not forced; its explicit error mapping is covered offline. Reflection/Heartbeat startup and priority are verified, but no forced proactive delivery was sent. Alpha Vantage needs a usable credential; its finance operations remain unavailable until configured.

Laptop join, SSH access, persistent login, cross-node DNS/API/MCP/artifacts/cancellation, restart behavior and resource headroom remain untested. Follow [the laptop operator steps](../../deploy/laptop/README.md) and `/tmp/if-laptop-handoff.md`. Main-node conversation, memory, queue and outbox data stay on the main node.

## Reproduce

From the root with the existing Python 3.12 verification environment:

```bash
PYTHONPATH=app/src /tmp/if-rewrite-venv/bin/python -m pytest app/tests -q
PYTHONPATH=utils/powerlifting-app /tmp/if-rewrite-venv/bin/python -m pytest utils/powerlifting-app/services/tests -q
npm --prefix utils/powerlifting-app/backend run test:forwarding
npm --prefix utils/powerlifting-app run typecheck
npm --prefix utils/powerlifting-app run build
python3 scripts/map_rewrite_functions.py
node scripts/check_rewrite_contract.cjs
/tmp/if-rewrite-venv/bin/python -m pytest scripts/test_if_live_canary_parser.py -q
python3 scripts/test_worker_sandbox.py
terraform -chdir=terraform fmt -check
terraform -chdir=terraform validate
kubectl kustomize deploy/laptop
kubectl exec -i -n if-portals deployment/pl-calculations -- python - < scripts/test_powerlifting_services_live.py
```

Subscription canaries run sequentially with the internal token supplied privately. `scripts/test_if_live_canary.py` additionally needs temporary worker diagnostics to verify native call identities. Remove diagnostics only after the worker is idle. `scripts/test_if_domain_live.py` checks actual domain continuation; `scripts/test_if_running_cancel.py` checks cancellation after an SDK delta. Do not run these against existing Athlete records or an undesignated Discord channel.

With the internal token supplied privately, run `PYTHONPATH=app/src /tmp/if-rewrite-venv/bin/python scripts/test_if_classifier_live.py` to verify the classifier's greeting/task schema through the live worker. The deployed persistence check is retained at `/tmp/if-meta-deployed-canary.py` and was run with `kubectl exec -i -n if-portals deployment/if-agent-api -- python - < /tmp/if-meta-deployed-canary.py`.
