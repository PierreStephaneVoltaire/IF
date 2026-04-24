
## Plan 8 — Banister Fitness-Fatigue Model (CTL / ATL / TSB)

**Goal:** Introduce the classic Banister impulse-response model as a new deterministic peaking layer. Produces three time-series (Fitness, Fatigue, Form) and a single "Form" number for the Analysis page.

**Files:**
- `tools/health/analytics.py` (new `compute_banister_ffm` function; called inside `weekly_analysis`)
- `backend/src/routes/analytics.ts` (expose in weekly analysis response)
- `frontend/src/constants/formulaDescriptions.ts` (new `banister_ffm` entry)
- `frontend/src/components/analysis/AnalysisPage.tsx` (new card "Form / Peaking Readiness")
- About page (new "Banister Fitness-Fatigue Model" subsection)
- `README.md` (new subsection under "Deterministic Formulas")

**Daily load input:**
- Use the daily composite fatigue total from Plan 1's dimensional math:
  $\text{load}_t = 0.30 F_{\text{axial}} + 0.30 F_{\text{neural}} + 0.25 F_{\text{peripheral}} + 0.15 F_{\text{systemic}}$
- Rest days contribute `load_t = 0`.

**Formulas:**

$$\text{CTL}_t = \lambda_1 \cdot \text{load}_t + (1 - \lambda_1) \cdot \text{CTL}_{t-1}$$

$$\text{ATL}_t = \lambda_2 \cdot \text{load}_t + (1 - \lambda_2) \cdot \text{ATL}_{t-1}$$

$$\text{TSB}_t = \text{CTL}_t - \text{ATL}_t$$

**Constants:**
- $\lambda_1 = 2/(42 + 1) \approx 0.0465$ (CTL, "Fitness")
- $\lambda_2 = 2/(7 + 1) = 0.25$ (ATL, "Fatigue")
- Initial values: `CTL_0 = ATL_0 = mean(load first 14 days)`

**Interpretation thresholds (for UI badge):**

| TSB | Label |
|---|---|
| < −30 | Deep overload |
| −30 to −10 | Productive overreach |
| −10 to +5 | Building |
| +5 to +15 | Peaking window |
| > +15 | Detraining risk |

**Response shape:**
```ts
{
  banister: {
    ctl_today: number,
    atl_today: number,
    tsb_today: number,
    tsb_label: string,
    series: { date: string; ctl: number; atl: number; tsb: number }[]
  }
}
```

**UI:** three-line chart (CTL, ATL, TSB) with comp date marker when a competition exists.

---
