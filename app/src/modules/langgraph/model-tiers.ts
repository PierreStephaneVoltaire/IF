import type { AgentRole } from '../litellm/types';

// Centralized model tiers for LangGraph flows (migrated from agentic/escalation).
export const MODEL_TIERS: Record<string, string[]> = {
  tier1: ['gemini-2.5-flash-lite'],
  tier2: ['gemini-3-flash', 'gpt-4o-mini'],
  tier3: ['claude-sonnet-4.5', 'gpt-4o'],
  tier4: ['claude-opus-4.5', 'o1'],
};

export const MODEL_CAPABILITY_ORDER = [
  ...MODEL_TIERS.tier1,
  ...MODEL_TIERS.tier2,
  ...MODEL_TIERS.tier3,
  ...MODEL_TIERS.tier4,
];

export function isAtMaxEscalation(model: string): boolean {
  return MODEL_CAPABILITY_ORDER.indexOf(model) >= MODEL_CAPABILITY_ORDER.length - 1;
}

export function getNextModel(currentModel: string): string | null {
  const idx = MODEL_CAPABILITY_ORDER.indexOf(currentModel);
  if (idx < 0) return MODEL_CAPABILITY_ORDER[0] || null;
  return MODEL_CAPABILITY_ORDER[idx + 1] || null;
}

export function getModelFromTier(tier: keyof typeof MODEL_TIERS, index: number): string {
  const models = MODEL_TIERS[tier];
  if (!models || models.length === 0) {
    throw new Error(`No models available for tier ${tier}`);
  }
  return models[Math.max(0, Math.min(index, models.length - 1))];
}

export function getModelForAgent(agentRole: AgentRole): string {
  // Fallback for agent role-specific selection; reuse tier2 index 0 by default.
  return getModelFromTier('tier2', 0);
}
