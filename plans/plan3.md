## Plan 3 — INOL Singularity Smoothing + Per-Lift Productive Ranges

**Goal:** Remove the discontinuity at $I \geq 1.0$ and replace global INOL thresholds (2.0 / 4.0) with per-lift productive ranges.

**Files:**
- `tools/health/analytics.py` (`compute_inol`)
- `packages/types/index.ts` (extend `LiftProfile` with optional `inol_low_threshold`, `inol_high_threshold`)
- `frontend/src/constants/formulaDescriptions.ts` (`inol` entry)
- `frontend/src/components/analysis/WeeklyData.tsx` (flag thresholds)
- About page INOL section
- `README.md` "INOL" section

**New per-set INOL formula:**

$$\text{INOL}_{\text{set}} = \frac{r}{100 \cdot \sqrt{(1 - \min(I, 0.995))^2 + \epsilon^2}}, \quad \epsilon = 0.02$$

$$\text{INOL}_{\text{raw, weekly}} = \sum_{\text{sets}} \text{INOL}_{\text{set}} \cdot \text{sets}$$

$$\text{INOL}_{\text{adjusted}} = \text{INOL}_{\text{raw}} \cdot \text{stimulus\_coefficient}$$

**Per-lift productive ranges (defaults when profile thresholds are not set):**

| Lift | Low stimulus | Productive | Overreaching |
|---|---|---|---|
| Squat | < 1.6 | 1.6 – 3.5 | > 3.5 |
| Bench | < 2.0 | 2.0 – 5.0 | > 5.0 |
| Deadlift | < 1.0 | 1.0 – 2.5 | > 2.5 |

Each `LiftProfile` gets optional overrides `inol_low_threshold` and `inol_high_threshold`. If unset, fall back to the per-lift defaults above.

---
