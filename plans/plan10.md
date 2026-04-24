## Plan 10 — Strength-Fatigue Decoupling + Taper Quality Score

**Goal:** Two new composite indicators that only activate inside specific contexts. Decoupling runs continuously; Taper Quality Score only runs in the last 3 weeks before a competition.

**Files:**
- `tools/health/analytics.py` (`compute_decoupling`, `compute_taper_quality`)
- `backend/src/routes/analytics.ts`
- `frontend/src/constants/formulaDescriptions.ts` (two new entries)
- `frontend/src/components/analysis/AnalysisPage.tsx` (Decoupling always visible; TQS renders only when `weeks_to_comp <= 3`)
- About page (two new subsections)
- `README.md` (two new subsections)

**Decoupling formula (over trailing 3 weeks):**

$$\text{Decoupling} = \text{slope}(e_{\text{1RM}}, \text{3wk}) - \text{slope}(\text{FI}, \text{3wk})$$

Both slopes normalized to per-week units. Negative value for 3+ consecutive weeks → flag `decoupling_fatigue_dominant`.

**Taper Quality Score (only when `weeks_to_comp <= 3`):**

$$\text{TQS} = 0.30 \cdot V_{\text{reduction}} + 0.25 \cdot I_{\text{maintained}} + 0.25 \cdot F_{\text{trend}} + 0.20 \cdot T_{\text{SB}}$$

**Component definitions:**
- $V_{\text{reduction}} = \text{clamp}\left(\frac{\text{pre\_taper\_peak\_volume} - \text{taper\_weekly\_volume}}{\text{pre\_taper\_peak\_volume} \cdot 0.5},\ 0,\ 1\right)$ — targets 40–60% reduction
- $I_{\text{maintained}} = 1$ if max top-set intensity during taper ≥ 0.95 × pre-taper; else linear falloff
- $F_{\text{trend}}$ = 1 if fatigue index trending down during taper, 0 if flat, negative if rising
- $T_{\text{SB}} = \text{clamp}\left(\frac{\text{TSB}_{\text{today}} + 5}{20},\ 0,\ 1\right)$ — reward TSB in peaking window (+5 to +15)

**Output:** 0–100 score + label (`poor / acceptable / good / excellent`).

"Pre-taper peak volume" = max weekly volume in the 4 weeks immediately preceding taper start. Taper start is `min(phase with name containing "taper" start, 3 weeks before comp)`.

---
