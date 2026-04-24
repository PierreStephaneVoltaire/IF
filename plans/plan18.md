
## Plan 18 — Peaking Readiness Timeline Visualization

**Goal:** Single chart that shows TSB trajectory from Plan 8, projected meet date, expected peak window, and current position. Answers "Am I on track?" visually.

**Depends on:** Plans 8, 11, 14

**Files:**
- `frontend/src/components/analysis/PeakingTimeline.tsx` (new)
- `frontend/src/pages/AnalysisPage.tsx` (mount above Projections)

**Visual elements (single unified chart):**
- X-axis: date, from program start through comp date + 2 weeks
- Y-axis (left): TSB value
- Y-axis (right): Specificity ratio (Plan 14)
- Line: historical TSB (solid)
- Line: projected TSB if athlete follows planned sessions (dashed, simulated forward via Banister with `load_t` from `planned_exercises` dimensional sum)
- Shaded band: expected specificity range by weeks-to-comp
- Scatter: actual weekly SR
- Vertical marker: comp date
- Vertical band: peaking window (TSB +5 to +15 target, shaded green)
- Current-day marker: circle

**Status pill above chart:**
- Green: "On track — peak window lands within ±3 days of comp"
- Yellow: "Peak misaligned — currently projected to peak X days early/late"
- Red: "Significant deviation — adjust deload timing"

Computed by finding the date where projected TSB first enters [+5, +15] and comparing to comp_date.

---
