
## Plan 7 — Readiness Score Reconstruction

**Goal:** Fix double-counting of failed reps, remove compliance (wrong construct), add subjective wellness (from Plan 6) and short-term performance trend, make bodyweight component cut-aware.

**Depends on:** Plan 6 (wellness capture)

**Files:**
- `tools/health/analytics.py` (`compute_readiness_score`)
- `frontend/src/constants/formulaDescriptions.ts` (`readiness_score` entry)
- About page readiness section
- `README.md` "Readiness score" section

**New formula:**

$$R = \left(1 - \left(0.30 \cdot F_{\text{norm}} + 0.25 \cdot D_{\text{rpe}} + 0.20 \cdot W_{\text{subj}} + 0.15 \cdot P_{\text{trend}} + 0.10 \cdot S_{\text{bw}}^{*}\right)\right) \cdot 100$$

**Component definitions:**

- $F_{\text{norm}}$ — normalized fatigue index over last 14 days (unchanged from current)
- $D_{\text{rpe}} = \text{clamp}\left(\frac{\text{avg\_rpe}_{14d} - \text{phase\_target\_midpoint}}{2},\ 0,\ 1\right)$ (unchanged)
- $W_{\text{subj}}$ — from Plan 6; fallback 0.5 if no data
- $P_{\text{trend}} = \text{clamp}\left(\frac{-\text{slope}(e_{\text{1RM, 14d}})}{\delta_w^{\text{expected weekly}}},\ 0,\ 1\right)$ — penalize only *negative* slope
- $S_{\text{bw}}^{*}$ — bodyweight deviation from planned trajectory, **not raw CV**

**Cut-aware bodyweight component:**

```
if (weeks_to_comp <= 6 AND meta.weight_class_kg < current_body_weight_kg):
    // Athlete is in weight-cut phase; expect BW to drop
    expected_weekly_change_kg = (meta.weight_class_kg - current_bw) / weeks_to_comp
    actual_weekly_change_kg  = slope(weight_log[last 14d])
    S_bw_star = clamp(|actual - expected| / 0.5, 0, 1)
else:
    // Normal block — stability matters
    S_bw_star = clamp(CV(weight_log[last 7 session bodyweights]) / 0.03, 0, 1)
```

**Removed from formula:**
- `miss_rate` (already inside `F_norm` via `failed_compound_ratio` — was double-counted)
- `compliance_pct` (measures past discipline, not current readiness; still surfaced separately on the Compliance card)

**Fallbacks:**
- No fatigue data → $F_{\text{norm}} = 0.5$
- No recent RPEs → $D_{\text{rpe}} = 0.5$
- No wellness → $W_{\text{subj}} = 0.5$
- No e1RM trend → $P_{\text{trend}} = 0$
- No bodyweight series → $S_{\text{bw}}^{*} = 0.5$

---
