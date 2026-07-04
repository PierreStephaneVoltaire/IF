# IF — Intelligent Agent Service

Personal FastAPI agent: a planner routes each request to a Specialist, keeps
durable memory across conversations, and delivers via Discord / OpenWebUI / HTTP.
Domain terms are in [CONTEXT.md](CONTEXT.md); decisions in [docs/adr/](docs/adr/).
Read both before working here — this file is only the operating rules.

## Run

```bash
cd app && pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```
Needs `OPENROUTER_API_KEY`, `opencode` on `PATH`, AWS/DynamoDB access.

## Infra

Bare-metal k3s (single node). Root `terraform/` is applied **locally** against the
k3s kubeconfig — there is no CI deploy pipeline. The app is live. See ADR-0002.

## Operating rules

1. **Diagnose from the live env, not the code.** Before theorizing about a runtime
   issue, check `kubectl logs`, `kubectl describe`, `kubectl get events`, and the
   AWS resources. The live cluster is the source of truth — never guess behavior
   from code alone.
2. **Protect the live IF agent API.** Non-targeted `terraform apply` and all
   `terraform destroy` are hook-blocked. `kubectl cordon/drain` are blocked
   (single-node cluster — they take down everything). Destructive kubectl verbs
   (delete/apply/patch/edit/replace/scale/rollout) are blocked **only** when they
   target the IF agent API (`if-agent-*` / `app=if-agent-api`) or a broad `all`/
   `--all` blast in `if-portals`; portal backends/frontends may be mutated freely.
   `terraform apply -target=...` is the only apply exception and needs explicit
   operator approval. Otherwise, give the operator the command to run. Read-only
   `kubectl get/describe/logs/events/top` and `terraform fmt/validate/plan` are fine.
3. **Never delete AWS resources** (CLI/SDK/console). Give the operator the command.
4. **No git writes.** Never `git commit/push/merge/rebase/reset`. Give the operator
   the command.
5. **Code first; don't over-plan.** Start implementing. Breaking a problem into
   parts is fine — plan part 1, implement, then plan part 2, implement. Do not burn
   hours of planning before any code.
6. **No comments in code.** Write self-documenting code. Default to zero comments;
   the only exception is a note a future reader genuinely could not derive.
7. **Prefer modules over stuffing one file.** Don't add unrelated concerns to a
   single `.tf` file (or any file) — split by concern.
8. **When stuck, hand off and move on.** If you enter a "but wait" / "let me
   reconsider" loop (more than ~4 cycles on the same problem), stop. Write the
   stuck point to `HANDOFF.md` (what you tried, where you're blocked), then move to
   the next task. Come back only when the task queue is done.
9. **Stay in scope — no rabbit holes.** An unrelated bug you notice goes in
   `bug.md`; do not chase it. An unrelated instruction dropped mid-task goes in
   `todo.md`; do not start it now.
10. **"Pivot" means full pivot.** If the operator says pivot, drop the current
    requirements entirely and do the new ones. Do not combine old + new.

## Powerlifting app (subrepo)

`utils/powerlifting-app/` is a separate Git repo (see `.meta`). It has its own
`CONTEXT.md` — read it when working on anything powerlifting-related, and use
that context's vocabulary (Athlete, Session, Competition Event, etc.), not this
repo's.

The powerlifting tools run as Fission nano-functions. Cline has a Fission MCP
(`fission-powerlifting` in MCP settings) that discovers and calls them — use it
to test functions as you develop them. When Fission is disabled the MCP will fail
to start; that's expected until it's turned on.

## Technical note

DynamoDB rejects Python `float`. Convert floats to `Decimal(str(value))` before
any write — reuse `ProgramStore._floats_to_decimals` or
`tools/health/core.py::_floats_to_decimals`.
