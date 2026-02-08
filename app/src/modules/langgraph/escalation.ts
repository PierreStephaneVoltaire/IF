import type { ExecutionState, ExecutionTurn } from '../litellm/types';
import { escalateTier, deescalateTier, getNextTier, isAtMaxTier, type Tier } from './model-tiers';

export interface EscalationDecision {
  shouldEscalate: boolean;
  suggestedTags?: string[];
  reason: string;
}

/**
 * Check if escalation should occur based on current tags (tier-based)
 * Returns suggested tags for the next tier, or null if already at max
 */
export function checkEscalationTriggers(
  state: ExecutionState,
  turn: ExecutionTurn,
  currentTags: string[],
  consecutiveLowConfidenceTurns: number
): EscalationDecision {
  // Try to escalate tier while preserving capability tags
  const nextTags = escalateTier(currentTags);
  
  if (!nextTags) {
    return { shouldEscalate: false, reason: 'Already at max tier' };
  }

  if (consecutiveLowConfidenceTurns >= 3) {
    return { shouldEscalate: true, suggestedTags: nextTags, reason: 'Low confidence - tier escalation needed' };
  }

  if (state.sameErrorCount >= 3) {
    return { shouldEscalate: true, suggestedTags: nextTags, reason: 'Repeated errors - tier escalation needed' };
  }

  if (state.noProgressTurns >= 5) {
    return { shouldEscalate: true, suggestedTags: nextTags, reason: 'No progress - tier escalation needed' };
  }

  if (turn.status === 'stuck') {
    return { shouldEscalate: true, suggestedTags: nextTags, reason: 'Model reported stuck - tier escalation needed' };
  }

  return { shouldEscalate: false, reason: 'No escalation triggers hit' };
}

/**
 * Check if de-escalation should occur based on high confidence
 * Returns suggested tags for lower tier, or null if at tier1
 */
export function checkDeescalationTriggers(
  confidenceScore: number,
  currentTags: string[]
): EscalationDecision {
  // Only de-escalate if confidence is very high (85+)
  if (confidenceScore < 85) {
    return { shouldEscalate: false, reason: 'Confidence below de-escalation threshold' };
  }

  // Try to de-escalate tier while preserving capability tags
  const lowerTags = deescalateTier(currentTags);

  if (!lowerTags) {
    return { shouldEscalate: false, reason: 'Already at tier1' };
  }

  return {
    shouldEscalate: true,
    suggestedTags: lowerTags,
    reason: 'High confidence - tier de-escalation safe',
  };
}

/**
 * Get the next tier up (for sequential thinking flow)
 */
export function getNextTierUp(currentTier: Tier): Tier | null {
  return getNextTier(currentTier);
}

/**
 * Check if we're at maximum tier
 */
export function isAtMaximumTier(tier: Tier): boolean {
  return isAtMaxTier(tier);
}

// Re-export tier helpers for backward compatibility
export { getNextTierUp as getNextModel, isAtMaximumTier as isAtMaxEscalation };
