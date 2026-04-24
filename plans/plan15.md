## Plan 15 — Formula Accordion, About Page, and README Prose Mismatch Cleanup

**Goal:** Before adding anything new to the UI, fix the stale prose identified in README "Known Mismatches" section. Align the three sources of truth.

**Scope** (no formula changes — this plan is documentation-only, but must run after Plans 1–14 so all updated formulas are captured):

**Files:**
- `frontend/src/constants/formulaDescriptions.ts`
- `frontend/src/pages/AboutPage.tsx` (or wherever About lives)
- `README.md`

**Specific fixes:**

1. **Projection ceiling** — remove "10% fixed" language; describe the dynamic ceiling from Plan 11 (now capped at 20% after PRR introduction).
2. **ACWR chronic baseline** — replace with Plan 5's EWMA description; remove the "previous 4 non-deload weeks" line.
3. **RPE drift regression** — change "OLS" → "Theil-Sen" wherever it appears; reference Plan 4's Kendall τ fit metric.
4. **Compliance window** — clarify that all weeks count, including deloads and breaks; still surfaced on the Compliance card but no longer a readiness input (per Plan 7).
5. **AI surface area on About page** — expand to list all seven AI entry points currently in the codebase: fatigue-profile estimation, lift-profile review/rewrite/stimulus, ROI correlation, program evaluation, accessory e1RM backfill, template evaluation, spreadsheet import. Remove any language suggesting "only three narrow AI tools."
6. **Supplement usage** — update About to reflect that `program_evaluation_ai` currently includes supplement summary context.
7. **Backend `estimated_dots` fragility** —  `meta.bodyweight_kg` and `current_body_weight_kg` should be either synced or we should only rely on `meta.bodyweight_kg` 
remove settingsstore.sex and use meta.sex for the frontend calculations the ui should update meta.sex directly. 


8. **Top max card** — document that it uses local Epley trend maxima when available, with backend `current_maxes` as fallback.

**Consistency rule going forward:** every formula-touching plan must include a README + About + formulaDescriptions update in the same PR.

---
