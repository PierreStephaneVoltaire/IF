## Plan 2 — RPE Stress Curve Recalibration

**Goal:** Shift the RPE-stress baseline so that RPE 7–7.5 (normal productive training) is not already at 25–37% stress. Only RPE 8+ should register meaningful stress.

**Files:**
- `tools/health/analytics.py` (`fatigue_index` → `rpe_stress`)
- `frontend/src/constants/formulaDescriptions.ts` (`fatigue_index` entry)
- About page fatigue index section
- `README.md` "Fatigue index" section

**New formula:**

$$\text{rpe\_stress} = \text{clamp}\left(\frac{\text{avg\_session\_rpe} - 7.5}{2.5},\ 0,\ 1\right)$$

**Mapping table to include in `formulaDescriptions.ts` summary:**

| RPE | rpe_stress |
|---|---|
| ≤ 7.5 | 0.00 |
| 8.0 | 0.20 |
| 8.5 | 0.40 |
| 9.0 | 0.60 |
| 9.5 | 0.80 |
| 10.0 | 1.00 |

Weights of `failed_compound_ratio` (0.40), `composite_spike` (0.35), and `rpe_stress` (0.25) remain unchanged.

---
