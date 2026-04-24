
## Plan 5 — ACWR → EWMA Migration and Zone Relabel

**Goal:** Replace rolling-mean ACWR with EWMA-based ACWR and relabel thresholds so they no longer imply validated injury prediction for powerlifting (which they do not).

**Files:**
- `tools/health/analytics.py` (`compute_acwr`, dimension aggregation)
- `frontend/src/constants/formulaDescriptions.ts` (`acwr` entry)
- `frontend/src/components/analysis/AnalysisPage.tsx` ACWR card copy
- About page ACWR section
- `README.md` "ACWR" section (remove the "older prose says chronic excludes deloads" mismatch note — this plan supersedes it)

**New formulas (per dimension $d$, computed daily):**

$$\text{EWMA}^{\text{acute}}_{d,\ t} = \lambda_a \cdot \text{load}_{d,\ t} + (1 - \lambda_a) \cdot \text{EWMA}^{\text{acute}}_{d,\ t-1}$$

$$\text{EWMA}^{\text{chronic}}_{d,\ t} = \lambda_c \cdot \text{load}_{d,\ t} + (1 - \lambda_c) \cdot \text{EWMA}^{\text{chronic}}_{d,\ t-1}$$

$$\text{ACWR}_d = \frac{\text{EWMA}^{\text{acute}}_{d,\ t}}{\text{EWMA}^{\text{chronic}}_{d,\ t}}$$

**Constants:**
- $\lambda_a = 2/(7 + 1) = 0.25$
- $\lambda_c = 2/(28 + 1) \approx 0.0690$
- Initialize both EWMAs with the mean of the first 7 days of load

**Composite (unchanged):**

$$\text{ACWR}_{\text{composite}} = 0.30 \cdot \text{ACWR}_{\text{axial}} + 0.30 \cdot \text{ACWR}_{\text{neural}} + 0.25 \cdot \text{ACWR}_{\text{peripheral}} + 0.15 \cdot \text{ACWR}_{\text{systemic}}$$

**New zone labels (change copy; don't claim injury prediction):**

| Range | Old label | New label |
|---|---|---|
| < 0.80 | Undertraining | Detraining trend |
| 0.80 – 1.30 | Optimal | Steady load |
| 1.30 – 1.50 | Caution | Rapid increase |
| > 1.50 | Danger | Load spike |

**Phase-aware context:**
- When the current phase's `intent` contains "overreach" or `target_rpe_max >= 9`, append the string "(expected during planned overreach)" to the label.

**Data requirement:** keep the minimum-5-weeks gate but compute off the daily load series now, not weekly rollups.

---
