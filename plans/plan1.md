## Plan 1 — Fatigue Model Physics Refinement

**Goal:** Move the axial/peripheral/neural per-set fatigue computations away from pure `weight * reps` linear scaling. Axial and peripheral fatigue scale non-linearly with load; neural fatigue needs a steeper curve near maximal and a modest absolute-load term.

**Files:**
- `tools/health/analytics.py` (per-set fatigue computation, `_weekly_fatigue_by_dimension`)
- `frontend/src/constants/formulaDescriptions.ts` (`fatigue_model` entry)
- About page fatigue model section
- `README.md` "Fatigue model and fatigue dimensions" section

**New formulas:**

$$F_{\text{axial}} = p_{\text{axial}} \cdot w^{\alpha_{\text{axial}}} \cdot r$$

$$F_{\text{peripheral}} = p_{\text{peripheral}} \cdot w^{\alpha_{\text{periph}}} \cdot r$$

$$F_{\text{systemic}} = p_{\text{systemic}} \cdot w \cdot r \cdot (1 + \beta \cdot I)$$

$$F_{\text{neural}} = p_{\text{neural}} \cdot r \cdot \phi(I) \cdot \left(\frac{w}{100}\right)^{0.5}$$

$$\phi(I) = \left(\frac{\max(0,\; I - 0.60)}{0.40}\right)^{3}$$

**Constants:**
- $\alpha_{\text{axial}} = 1.30$
- $\alpha_{\text{periph}} = 1.15$
- $\beta = 0.30$
- Neural exponent on $\phi$: cubic (was quadratic)
- Absolute-load scaler: $\sqrt{w/100}$, where $w$ is kg

**Backward compatibility:**
- Keep the existing `profile.axial / profile.neural / profile.peripheral / profile.systemic` glossary coefficients unchanged; this plan only changes the *aggregation* math, not the glossary coefficients.
- Fallback profile remains `axial=0.3, neural=0.3, peripheral=0.5, systemic=0.3`.
- Non-SBD exercises without a current max still fall back to $I = 0.70$ for neural.

**Expected behavior change:**
- A single at 95% produces meaningfully more neural fatigue than 90% (spread widens).
- Heavy triples at 90% produce more axial fatigue than equivalent volume-load at 70%.

---
