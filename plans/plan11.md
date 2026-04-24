## Plan 11 — Peak Realization Ratio (PRR) + Personal Lambda Calibration

**Goal:** Close the feedback loop on the projection formula. After every competition, compute how much of the projected max was actually realized, and use that to calibrate future projections per athlete.

**Files:**
- `packages/types/index.ts` (extend `Competition.results` with `projected_at_t_minus_1w: { squat_kg, bench_kg, deadlift_kg, total_kg }`, add `prr: { squat, bench, deadlift, total }`)
- `tools/health/analytics.py` (`meet_projection` enhancement; new `compute_prr`; new `personal_lambda` lookup)
- `backend/src/routes/analytics.ts`
- Cron/hook that snapshots projection 7 days before any `comp_date` and writes it to the competition record
- `frontend/src/components/analysis/AnalysisPage.tsx` (Projections card shows "calibrated to your history" badge when ≥2 PRRs exist)
- About page (new "Peak Realization and Personal Calibration" subsection)
- `README.md` "Meet projection" section

**T-1 week snapshot:**
- On the day when `today = comp_date - 7`, snapshot the current projected_comp_max per lift into the competition record.

**PRR computation (run when competition `results` are written):**

$$\text{PRR}_{\text{lift}} = \frac{\text{best\_successful\_attempt}_{\text{lift}}}{\text{projected\_at\_t\_minus\_1w}_{\text{lift}}}$$

Store per-lift and total. Ignore lifts with zero successful attempts (bomb-out on a lift).

**Personal lambda override:**

After 2+ completed competitions with PRR data:

$$\lambda_{\text{personal}} = \text{median}(\text{PRR}_{\text{last 3 meets}})$$

Apply as a multiplier to the DOTS-tier lambda for the athlete:

$$\lambda_{\text{effective}} = \lambda_{\text{tier}} \cdot \lambda_{\text{personal, normalized}}$$

Where $\lambda_{\text{personal, normalized}} = \text{clamp}(\text{PRR}_{\text{median}},\ 0.92,\ 1.05)$. A historical underperformer gets a more conservative lambda; a historical overperformer gets a less-aggressive decay.

**Dynamic ceiling also reduces to 20%** (was 30%) as part of this plan, since PRR now supplies personalization.

$$\text{ceiling\_pct} = \min\left(0.20,\ 0.10 + 0.005 \cdot \max(0, \text{weeks\_to\_comp} - 8)\right)$$

**UI badge:** "Calibrated from X meets" when PRR data exists.

---
