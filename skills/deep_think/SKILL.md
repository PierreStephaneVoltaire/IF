---
name: deep_think
description: Extended reasoning for one hard question, with optional native Specialist delegation for evidence or domain checks.
---

# Deep Think

## When To Use

Use this when the operator explicitly asks IF to think deeply, reason before answering, pressure-test a conclusion, find a root cause, or analyze one difficult question.

Do not use it for routine social replies, simple single-domain lookups, or implementation work that should go directly to a technical/domain specialist.

## Protocol

1. Restate the core question in one sentence.
2. Identify assumptions, unknowns, and the domain evidence needed.
3. If one domain specialist must inspect data or tools, delegate to one named native Specialist and include the relevant evidence request in its task.
4. If the reasoning can be completed locally, save useful concise findings with `artifact_write`.
5. Produce the final answer in IF's voice, preserving caveats and risks.

## Handoff Format

Delegate to native Specialist `dialectic` with the question, assumptions and relevant evidence. Ask for the strongest objections and a synthesis; wait for its result.

Use `dialectic` for adversarial reasoning, `decision_analyst` for weighted tradeoffs, and a named native Specialist when tools or domain data are required. A child returns its result to the parent; it does not submit another top-level job.
