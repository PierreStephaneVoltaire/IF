
## Plan 14 — Specificity Periodization Curve

**Goal:** Extend the existing Specificity Ratio with expected ranges by weeks-to-competition and flag deviation.

**Files:**
- `tools/health/analytics.py` (extend `compute_specificity_ratio`)
- `frontend/src/constants/formulaDescriptions.ts` (`specificity_ratio` entry)
- `frontend/src/pages/AnalysisPage.tsx` Specificity card
- About page
- `README.md` "Specificity ratio" section

**Expected bands (narrow SR):**

| Weeks out | Narrow SR min | Narrow SR max | Broad SR min | Broad SR max |
|---|---|---|---|---|
| 16+ | 0.30 | 0.50 | 0.60 | 0.75 |
| 12–16 | 0.40 | 0.55 | 0.65 | 0.80 |
| 8–12 | 0.50 | 0.65 | 0.75 | 0.85 |
| 4–8 | 0.60 | 0.75 | 0.80 | 0.90 |
| 0–4 (peak) | 0.70 | 0.85 | 0.85 | 0.95 |

**Flags:**
- `specificity_below_expected` if narrow SR < band.min
- `specificity_above_expected` if narrow SR > band.max (usually means over-specializing early)

Only activates when `weeks_to_comp` is finite (at least one upcoming competition).

---
