## Plan 20 — Competition Prep Block Comparison

**Goal:** Flagship feature. Side-by-side visualization of two (or more) historical comp prep blocks aligned on phase intent, not calendar.

**Files:**
- `frontend/src/pages/BlockComparisonPage.tsx` (new route)
- `backend/src/routes/analytics.ts` (new endpoint `GET /api/analytics/block-comparison?blocks=blockA,blockB`)
- `tools/health/block_comparison.py` (new module)
- Menu entry and route wiring
- README new section "Block comparison"
- About page new subsection

**Block definition:** A "block" is a contiguous slice of a program between `program_start` and the meet date (or the current date if the block is in progress). One program can contain multiple blocks if it spans multiple competitions.

**Alignment:**
- Map each block into canonical phases via `Phase.intent` tokens: `hypertrophy`, `strength`, `peaking`, `deload`, `taper`.
- Normalize each phase to the same relative duration so visual comparison is meaningful.

**Metrics computed per block (all from existing data):**
- Duration in weeks
- Starting e1RM per lift (average of first 2 weeks)
- Ending e1RM per lift (competition result if finalized; otherwise projected)
- Total gain kg / total gain % per lift and overall
- Average weekly sets per lift
- Average weekly volume (kg) per lift
- Peak Fatigue Index and peak ACWR
- Taper duration
- Taper Response (Plan 10's TQS equivalent if available)
- Average compliance
- Opener / 2nd / 3rd make rates per lift (when meet results available)
- Average intensity distribution (heavy / moderate / light percentages)
- Final specificity ratio
- Average INOL per lift
- PRR per lift (from Plan 11)

**Per-exercise drill-down:**
- Match exercises across blocks by glossary `id` (canonical name), not label.
- For each matched exercise: weekly volume chart overlay, weekly top e1RM overlay, total sets delta, total volume delta.

**Pattern detection (deterministic, not AI):**
- For each metric with a meaningful delta between blocks, generate a line of prose:
  - e.g. "Block B ran 30% more squat volume and gained 4 kg more on squat."
  - "Block A ran a 2-week taper and realized 96% of projection. Block B ran a 3-week taper and realized 103%."
- Top-N differences surfaced.

**Optional LLM summary at end** — reuse `program_evaluation_ai` with a new prompt variant that accepts two block summaries instead of one program. Small scope extension, not a new AI entry point.

---
