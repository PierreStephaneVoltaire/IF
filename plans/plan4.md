
## Plan 4 — Theil-Sen Fit Quality Metric Fix

**Goal:** Replace the mathematically incorrect R² on Theil-Sen slopes with a rank-based fit statistic. Report **Kendall's τ** and **Normalized MAD** alongside the slope.

**Files:**
- `tools/health/analytics.py` (`progression_rate`, `rpe_drift`)
- `frontend/src/constants/formulaDescriptions.ts` (`progression_rate`, `rpe_drift`)
- All per-lift breakdown components that show R²
- About page progression section
- `README.md` "Progression rate" and "RPE drift" sections

**New computed fields returned by backend:**

$$\tau = \text{Kendall's tau between effective\_week\_index and weekly\_best\_e1RM}$$

$$\text{NMAD} = 1 - \frac{\text{MAD}(\text{residuals to Theil-Sen line})}{\text{MAD}(\text{series})}$$

**API response additions:**
- `kendall_tau: number`        — rank correlation, range [-1, 1]
- `fit_quality: number`        — NMAD, range [0, 1]; label shown in UI
- Keep `r_squared` for one release with a deprecation note, then remove.

**UI label change:** rename column "R²" → "Fit Quality" throughout per-lift breakdown. Show Kendall τ as a secondary number on hover.

---
