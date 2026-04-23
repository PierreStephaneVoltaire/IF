export interface FormulaDescription {
  id: string
  title: string
  summary: string
  formula: string
  variables: { name: string; description: string }[]
  thresholds?: { label: string; value: string; flag?: string }[]
}

export const FORMULA_DESCRIPTIONS: FormulaDescription[] = [
  {
    id: 'estimated_1rm',
    title: 'Estimated 1RM',
    summary: 'Estimated one-rep max from RPE table (reps <= 6) or conservative table (reps <= 5). 90th percentile of qualifying sets over 6 weeks. No Epley/Brzycki.',
    formula: `E1RM = weight / pct(reps, rpe)

-- RPE table (reps <= 6, RPE 6-10)
-- Conservative table (reps <= 5, no RPE)
-- Final = P90(all qualifying estimates, last 42 days)`,
    variables: [
      { name: 'weight', description: 'Load lifted in kg' },
      { name: 'reps', description: 'Repetitions performed' },
      { name: 'rpe', description: 'Rate of Perceived Exertion (6-10)' },
      { name: 'pct', description: 'RPE-based or conservative % of 1RM' },
    ],
  },
  {
    id: 'progression_rate',
    title: 'Progression Rate',
    summary: 'Theil-Sen regression on e1RM per effective training week. Deloads and break weeks excluded.',
    formula: `slope = theilsen_median(e1RM ~ effective_week)
r² = 1 - SS_res / SS_tot`,
    variables: [
      { name: 'e1RM', description: 'Estimated 1RM per session' },
      { name: 'effective_week', description: 'Week index excluding deloads/breaks' },
      { name: 'slope', description: 'kg per week rate of change' },
      { name: 'r²', description: 'Goodness of fit (0-1)' },
    ],
  },
  {
    id: 'competition_projection',
    title: 'Competition Projection',
    summary: 'Diminishing-returns projection from current maxes. Clamped to [E_now, E_now * 1.10].',
    formula: `C_max = [E_now + delta_w * lambda * (1 - lambda^n) / (1 - lambda)] * P
clamped to [E_now, E_now * 1.10]

lambda: DOTS < 300 -> 0.96, 300-400 -> 0.90, >= 400 -> 0.85
P (peak): DOTS < 300 -> 1.01, 300-400 -> 1.03, >= 400 -> 1.05
n = weeks_remaining - taper_weeks - planned_deloads`,
    variables: [
      { name: 'E_now', description: 'Current estimated 1RM' },
      { name: 'delta_w', description: 'Progression rate (kg/week)' },
      { name: 'lambda', description: 'Diminishing returns decay factor' },
      { name: 'P', description: 'Peaking factor based on DOTS level' },
      { name: 'n', description: 'Effective training weeks remaining' },
    ],
  },
  {
    id: 'attempt_selection',
    title: 'Attempt Selection',
    summary: 'Competition attempts calculated from projected maxes with user-configurable percentages.',
    formula: `attempt_k = round_to_2.5(C_max * pct_k)
total = sum of all third attempts

round_to_2.5(v) = round(v / 2.5) * 2.5`,
    variables: [
      { name: 'C_max', description: 'Competition projected max' },
      { name: 'pct_k', description: 'Attempt percentage (opener/second/third)' },
      { name: 'total', description: 'Sum of third attempts' },
    ],
    thresholds: [
      { label: 'Opener', value: '90% (default)', flag: 'Should feel easy under worst conditions' },
      { label: 'Second', value: '95.5% (default)', flag: 'A confident single, builds momentum' },
      { label: 'Third', value: '100% (default)', flag: 'Your projected max' },
    ],
  },
  {
    id: 'fatigue_model',
    title: 'Fatigue Model',
    summary: '4 dimensions (axial, neural, peripheral, systemic) per exercise. AI-estimated or manual. Per-set fatigue calculation.',
    formula: `F_d = profile.d * weight * reps  (axial, peripheral, systemic)
F_neural = profile.neural * reps * phi(I)
phi(I) = (max(0, I - 0.60) / 0.40)^2
I = weight / E_now (intensity ratio)`,
    variables: [
      { name: 'profile.d', description: 'Exercise fatigue coefficient per dimension (0-1)' },
      { name: 'weight', description: 'Load in kg' },
      { name: 'reps', description: 'Repetitions in the set' },
      { name: 'I', description: 'Intensity ratio (weight / estimated max)' },
      { name: 'phi(I)', description: 'Neural scaling function, zero below 60% intensity' },
    ],
  },
  {
    id: 'fatigue_index',
    title: 'Fatigue Index',
    summary: 'Composite fatigue score from failed compounds, volume spikes, and session skip rate.',
    formula: `FI = 0.40 * failed_compound_ratio
   + 0.35 * composite_spike
   + 0.25 * rpe_stress

rpe_stress = clamp((avg_session_rpe − 6.0) / 4.0, 0, 1)
  RPE 6 → 0.0 | RPE 8 → 0.5 | RPE 10 → 1.0

Note: skip_rate excluded — resting reduces fatigue, not increases it.`,
    variables: [
      { name: 'failed_compound_ratio', description: 'Failed compound sets / total compound sets' },
      { name: 'composite_spike', description: 'Weighted dimensional fatigue spike (axial/neural/peripheral/systemic)' },
      { name: 'rpe_stress', description: 'Normalized session RPE — captures weeks of RPE 9-10 grinding without failures' },
    ],
    thresholds: [
      { label: 'Low', value: '< 0.30', flag: 'Normal' },
      { label: 'Moderate', value: '0.30 - 0.59', flag: 'Caution' },
      { label: 'High', value: '>= 0.60', flag: 'Overreaching risk' },
    ],
  },
  {
    id: 'inol',
    title: 'INOL',
    summary: 'Stimulus-adjusted intensity and volume load metric per lift per week. Flags low stimulus and overreaching.',
    formula: `raw_INOL = sum(reps / (100 * (1 - I)))
adjusted_INOL = raw_INOL * lift_stimulus_coefficient
I = weight / E_now (per set)`,
    variables: [
      { name: 'reps', description: 'Repetitions in the set' },
      { name: 'I', description: 'Intensity ratio (weight / estimated max)' },
      { name: 'lift_stimulus_coefficient', description: 'Lift-profile multiplier from 1 to 2; baseline is 1.0' },
    ],
    thresholds: [
      { label: 'Low stimulus', value: '< 2.0', flag: 'Insufficient training stress' },
      { label: 'Productive', value: '2.0 - 4.0', flag: 'Optimal range' },
      { label: 'Overreaching', value: '> 4.0', flag: 'Excessive stress' },
    ],
  },
  {
    id: 'acwr',
    title: 'ACWR (Acute:Chronic Workload Ratio)',
    summary: 'Per-dimension workload ratio with weighted composite. Compares this week to 4-week chronic average.',
    formula: `ACWR_d = F_d_week / mean(F_d previous 4 non-deload weeks)
Composite = 0.30*axial + 0.30*neural + 0.25*peripheral + 0.15*systemic`,
    variables: [
      { name: 'F_d_week', description: 'Fatigue in dimension d for current week' },
      { name: 'F_d_prev', description: 'Fatigue in dimension d for previous weeks' },
    ],
    thresholds: [
      { label: 'Undertraining', value: '< 0.80', flag: 'Detraining risk' },
      { label: 'Optimal', value: '0.80 - 1.30', flag: 'Sweet spot' },
      { label: 'Caution', value: '1.30 - 1.50', flag: 'Elevated injury risk' },
      { label: 'Danger', value: '> 1.50', flag: 'High injury risk' },
    ],
  },
  {
    id: 'ri_distribution',
    title: 'Relative Intensity Distribution',
    summary: 'Buckets working sets by ratio of weight to current estimated max.',
    formula: `RI = weight / E_now
Heavy: RI > 0.85
Moderate: 0.70 <= RI <= 0.85
Light: RI < 0.70`,
    variables: [
      { name: 'weight', description: 'Load in kg' },
      { name: 'E_now', description: 'Current estimated 1RM for that lift' },
      { name: 'RI', description: 'Relative intensity ratio' },
    ],
  },
  {
    id: 'specificity_ratio',
    title: 'Specificity Ratio',
    summary: 'Measures how much training is directly sport-specific (SBD) vs general.',
    formula: `SR_narrow = SBD sets / total sets
SR_broad = (SBD + secondary category) / total sets`,
    variables: [
      { name: 'SBD sets', description: 'Sets of squat, bench, or deadlift' },
      { name: 'secondary', description: 'Same-category exercises (e.g. close-grip bench)' },
      { name: 'total sets', description: 'All working sets across all exercises' },
    ],
  },
  {
    id: 'readiness_score',
    title: 'Readiness Score',
    summary: 'Composite score predicting training readiness from fatigue, RPE drift, bodyweight stability, and compliance.',
    formula: `R = (1 - (0.30*F_norm + 0.25*D_rpe + 0.20*S_bw
         + 0.15*M_rate + 0.10*(1 - C_pct/100))) * 100`,
    variables: [
      { name: 'F_norm', description: 'Normalized fatigue index (0-1)' },
      { name: 'D_rpe', description: 'RPE drift from phase target' },
      { name: 'S_bw', description: 'Bodyweight coefficient of variation' },
      { name: 'M_rate', description: 'Failed sets / total sets' },
      { name: 'C_pct', description: 'Session compliance percentage' },
    ],
    thresholds: [
      { label: 'Green', value: '> 75', flag: 'Ready to train' },
      { label: 'Yellow', value: '50 - 75', flag: 'Proceed with caution' },
      { label: 'Red', value: '< 50', flag: 'Recovery priority' },
    ],
  },
  {
    id: 'dots_score',
    title: 'DOTS Score',
    summary: 'Strength-to-bodyweight coefficient using polynomial formula with sex-specific coefficients.',
    formula: `DOTS = 500 * total / (a + b*bw + c*bw^2 + d*bw^3 + e*bw^4)`,
    variables: [
      { name: 'total', description: 'Squat + Bench + Deadlift total (kg)' },
      { name: 'bw', description: 'Bodyweight in kg' },
      { name: 'a-e', description: 'Sex-specific polynomial coefficients' },
    ],
  },
  {
    id: 'ipf_gl_score',
    title: 'IPF GL Score',
    summary: 'IPF relative scoring coefficient for classic powerlifting totals or classic bench-only results.',
    formula: `GL = result * 100 / (A - B * e^(-C * bw))`,
    variables: [
      { name: 'result', description: 'SBD total for classic powerlifting, or bench result for bench-only scoring' },
      { name: 'bw', description: 'Bodyweight in kg' },
      { name: 'A-C', description: 'Sex- and discipline-specific coefficients' },
    ],
  },
  {
    id: 'rpe_drift',
    title: 'RPE Drift',
    summary: 'Residual regression comparing actual RPE to phase target midpoint. Detects fatigue or adaptation trends.',
    formula: `residual = avg_rpe - phase_target_midpoint
slope = OLS(residual ~ week)
slope >= 0.1 -> fatigue
slope <= -0.1 -> adaptation`,
    variables: [
      { name: 'avg_rpe', description: 'Average session RPE' },
      { name: 'phase_target_midpoint', description: '(target_rpe_min + target_rpe_max) / 2' },
      { name: 'slope', description: 'OLS regression slope over time' },
    ],
    thresholds: [
      { label: 'Fatigue', value: 'slope >= 0.1', flag: 'RPE rising at same loads' },
      { label: 'Adaptation', value: 'slope <= -0.1', flag: 'Getting stronger at same loads' },
      { label: 'Stable', value: '|slope| < 0.1', flag: 'No significant trend' },
    ],
  },
  {
    id: 'compliance',
    title: 'Compliance',
    summary: 'Completed vs planned session ratio. All weeks counted — deloads and programmed breaks are NOT excluded.',
    formula: `compliance = (completed_sessions / planned_sessions) * 100
All weeks included. A week with no planned sessions contributes nothing.`,
    variables: [
      { name: 'completed', description: 'Sessions with status logged or completed' },
      { name: 'planned', description: 'Total sessions minus deload/break weeks' },
    ],
  },
]
