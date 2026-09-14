---
name: sequential_plan
description: Dependency-aware planning for multi-step goals where each step changes the state for the next step.
---

# Sequential Plan

## When To Use

Use this when the operator asks to plan a migration, rollout, investigation, debugging path, or any goal where step N depends on step N-1.

## Protocol

1. Save a plan artifact using the scoped `artifact_write` tool using markdown checkboxes:
   - `[ ]` open
   - `[x]` done
   - `[!]` needs adjustment
   - `[?]` blocked
2. Separate critical-path steps from parallel side work.
3. For each step that requires a different specialist, delegate to that named native Specialist in dependency order.
4. After a child result returns, update the plan artifact with `artifact_write` before continuing.
5. The final response should summarize current state, completed steps, blocked items, and the next executable action.

## Handoff Format

Native delegation task: `coder`; implement step 2 from the supplied plan artifact exactly as scoped, including relevant decisions, files, constraints, and prior step output. The child must return its result to the parent without creating another top-level job.

Do not pretend a downstream specialist ran. Only state completed work that was actually done in the workspace or returned by a handoff.
