
## Plan 13 — Volume Landmarks (MEV / MAV / MRV) per Lift

**Goal:** Empirically estimate per-lift volume landmarks from historical data.

**Files:**
- `tools/health/analytics.py` (new `compute_volume_landmarks`)
- `backend/src/routes/analytics.ts`
- `frontend/src/constants/formulaDescriptions.ts` (new entry)
- `frontend/src/pages/AnalysisPage.tsx` (new card under Per-Lift Breakdown)
- About page (new subsection)
- `README.md` (new subsection)

**Inputs per lift:**
- Weekly history over the whole program (or all programs if template lineage allows): `{week, weekly_sets, e1rm_end_of_week}`
- Exclude deload and break weeks.

**Algorithm:**

1. Bucket historical weeks by `weekly_sets` (bins of 2 sets wide).
2. For each bin, compute average $\Delta e_{\text{1RM, week}}$ across all weeks in that bin.
3. Sort bins by average set count.

$$\text{MV} = \min\{\text{sets} : \overline{\Delta e_{\text{1RM}}} \geq 0\}$$

$$\text{MEV} = \min\{\text{sets} : \overline{\Delta e_{\text{1RM}}} > 0\}$$

$$\text{MAV} = \underset{\text{sets}}{\text{argmax}}\ \overline{\Delta e_{\text{1RM}}}$$

$$\text{MRV} = \min\{\text{sets} : \text{avg}(\text{FI next week}) > 0.60 \text{ OR } \overline{\Delta e_{\text{1RM}}} < 0\}$$

**Data requirement:** need at least 12 weeks of history per lift. Below that, mark landmarks as `insufficient_data` and do not render.

**Response shape:**
```ts
volume_landmarks: {
  squat: { mv: number | null, mev: number | null, mav: number | null, mrv: number | null, confidence: 'low' | 'medium' | 'high' },
  bench: { ... },
  deadlift: { ... }
}
```

---
