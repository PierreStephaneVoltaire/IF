---
name: parallel_analysis
description: Multi-perspective analysis of one artifact or decision, using native Specialist delegation for independent lenses.
---

# Parallel Analysis

## When To Use

Use this when the operator explicitly asks for multiple angles, adversarial review, security/performance/architecture review, or independent perspectives on the same artifact.

## Protocol

1. Identify two or three independent lenses. Do not exceed three unless the operator asked for more.
2. Delegate one named native Specialist per lens, ordered by importance, with no more than two children.
3. Ask each child Specialist to return findings to the parent, which can save them with `artifact_write` when the output is long.
4. Synthesize returned findings into: agreement, disagreement, risk ranking, and recommended action.
5. Preserve severe findings exactly; do not smooth them into vague advice.

## Common Lenses

- Security: `secops`
- Performance: `performance_analyst`
- Architecture: `architect`
- Code correctness: `code_reviewer`
- Product/user impact: `product_owner` or `product_manager`
- Training/nutrition: `powerlifting_coach`

## Handoff Format

Native delegation task: `secops`; review the attached plan for concrete security risks and missing controls using the same artifact and constraints as the parent request.
