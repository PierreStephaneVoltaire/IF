
## Plan 9 — Foster Monotony & Strain

**Goal:** Add Foster (1998) monotony and strain as low-cost overreaching flags. Orthogonal to ACWR — catches "same moderate load every day" patterns that ACWR misses.

**Files:**
- `tools/health/analytics.py` (new `compute_monotony_strain`)
- `backend/src/routes/analytics.ts` (weekly analysis response)
- `frontend/src/constants/formulaDescriptions.ts` (new entry `monotony_strain`)
- `frontend/src/components/analysis/WeeklyData.tsx` (add row in per-week table)
- About page (new subsection)
- `README.md` (new subsection)

**Formulas:**

$$\text{Monotony}_{\text{week}} = \frac{\text{mean}(\text{daily load}_{\text{week}})}{\text{SD}(\text{daily load}_{\text{week}}) + \epsilon}, \quad \epsilon = 1\text{e-}6$$

$$\text{Strain}_{\text{week}} = \text{weekly load} \cdot \text{Monotony}_{\text{week}}$$

Daily load is the same composite used by Plan 8.

**Flag thresholds:**
- Monotony > 2.0 → flag `high_monotony`
- Strain > (rolling 4-week median strain × 1.5) → flag `strain_spike`

**Response shape:**
```ts
{
  monotony_strain: {
    weekly: { week_start: string; monotony: number; strain: number; flags: string[] }[]
  }
}
```

---
