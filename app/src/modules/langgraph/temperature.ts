/**
 * Temperature & Top-P Variance System
 *
 * Per-flow base temperature/top_p with ±0.1 pseudo-random variance
 * for natural variation in LLM responses.
 *
 * Algorithm:
 *   75% of the time → exact base value
 *   25% of the time → ±0.1 variance (50/50 split up/down)
 *
 * @see plans/langgraph-migration-plan.md §6
 */

import { FlowType } from '../litellm/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ModelParams {
  temperature: number;
  top_p: number;
}

interface FlowTemperatureConfig {
  baseTemperature: number;
  baseTopP: number;
}

// ---------------------------------------------------------------------------
// Base configuration per flow type
// ---------------------------------------------------------------------------

const FLOW_TEMPERATURE_CONFIG: Record<FlowType, FlowTemperatureConfig> = {
  [FlowType.SEQUENTIAL_THINKING]: { baseTemperature: 0.3, baseTopP: 0.9 },
  [FlowType.ARCHITECTURE]:       { baseTemperature: 0.4, baseTopP: 0.9 },
  [FlowType.SHELL]:              { baseTemperature: 0.2, baseTopP: 0.85 },
  [FlowType.SIMPLE]:             { baseTemperature: 0.5, baseTopP: 0.95 },
  [FlowType.SOCIAL]:             { baseTemperature: 0.8, baseTopP: 0.95 },
  [FlowType.PROOFREADER]:        { baseTemperature: 0.2, baseTopP: 0.85 },
  [FlowType.DIALECTIC]:          { baseTemperature: 0.7, baseTopP: 0.95 },
  [FlowType.CONSENSUS]:          { baseTemperature: 0.4, baseTopP: 0.9 },
  [FlowType.ANGEL_DEVIL]:        { baseTemperature: 0.7, baseTopP: 0.95 },
  [FlowType.BREAKGLASS]:         { baseTemperature: 0.5, baseTopP: 0.95 },
  [FlowType.BRANCH]:             { baseTemperature: 0.5, baseTopP: 0.95 },
};

// ---------------------------------------------------------------------------
// Variance helpers
// ---------------------------------------------------------------------------

/**
 * Apply ±0.1 variance to a base value.
 *
 * - 75 % of calls return the exact base value (deterministic).
 * - 25 % of calls return base ± 0.1 (50/50 up or down).
 * - Result is always clamped to [0, 1].
 */
export function applyVariance(base: number): number {
  if (Math.random() < 0.75) {
    return base;
  }
  const delta = Math.random() < 0.5 ? 0.1 : -0.1;
  return Math.max(0, Math.min(1, base + delta));
}

/**
 * Return a temperature value with optional variance applied.
 *
 * @param baseTemp - The base temperature for the flow type (0–1).
 * @returns Temperature with variance applied per the 75/25 algorithm.
 */
export function getTemperatureWithVariance(baseTemp: number): number {
  return applyVariance(baseTemp);
}

/**
 * Return a top_p value with optional variance applied.
 *
 * @param baseTopP - The base top_p for the flow type (0–1).
 * @returns top_p with variance applied per the 75/25 algorithm.
 */
export function getTopPWithVariance(baseTopP: number): number {
  return applyVariance(baseTopP);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Get temperature and top_p model parameters for a given flow type,
 * with pseudo-random variance applied.
 *
 * Usage:
 * ```ts
 * const params = getModelParams(FlowType.SOCIAL);
 * const response = await chatCompletion({ model, messages, ...params });
 * ```
 */
export function getModelParams(flowType: FlowType): ModelParams {
  const config = FLOW_TEMPERATURE_CONFIG[flowType];
  if (!config) {
    // Fallback to SIMPLE defaults for unknown flow types
    return {
      temperature: applyVariance(0.5),
      top_p: applyVariance(0.95),
    };
  }
  return {
    temperature: applyVariance(config.baseTemperature),
    top_p: applyVariance(config.baseTopP),
  };
}

/**
 * Get the raw (no-variance) base configuration for a flow type.
 * Useful for logging / debugging what the "intended" values are.
 */
export function getBaseConfig(flowType: FlowType): FlowTemperatureConfig {
  return FLOW_TEMPERATURE_CONFIG[flowType] ?? { baseTemperature: 0.5, baseTopP: 0.95 };
}
