import type { ExecutionState, ExecutionTurn } from '../litellm/types';
import {
  getNextTier,
  getMaxTier,
  getAgentRoleMaxTier,
  getModelGroup,
  getAgentRoleGroup,
  type Tier,
  type FlowTypeString,
  type AgentRoleString,
} from '../litellm/model-groups';

export interface EscalationDecision {
  shouldEscalate: boolean;
  suggestedModelGroup?: string;
  reason: string;
}

/**
 * Check if escalation should occur based on current model group
 * Returns suggested model group for the next tier, or null if already at max
 */
export function checkEscalationTriggers(
  state: ExecutionState,
  turn: ExecutionTurn,
  currentModelGroup: string,
  consecutiveLowConfidenceTurns: number,
  flowType?: FlowTypeString,
  agentRole?: AgentRoleString
): EscalationDecision {
  // Parse current tier from model group (format: "{type}-{tier}")
  const tierMatch = currentModelGroup.match(/tier[1-4]/);
  const currentTier = (tierMatch?.[0] as Tier) || 'tier2';

  // If we have flowType, use the new tiered system
  if (flowType) {
    const nextTier = getNextTier(currentTier, flowType, agentRole);

    if (!nextTier) {
      return { shouldEscalate: false, reason: 'Already at max tier for this flow' };
    }

    if (consecutiveLowConfidenceTurns >= 3) {
      let suggestedGroup: string;
      if (flowType === 'sequential-thinking' && agentRole) {
        suggestedGroup = getAgentRoleGroup(agentRole, nextTier);
      } else {
        suggestedGroup = getModelGroup(flowType, nextTier, { agentRole });
      }
      return {
        shouldEscalate: true,
        suggestedModelGroup: suggestedGroup,
        reason: 'Low confidence - tier escalation needed',
      };
    }

    if (state.sameErrorCount >= 3) {
      let suggestedGroup: string;
      if (flowType === 'sequential-thinking' && agentRole) {
        suggestedGroup = getAgentRoleGroup(agentRole, nextTier);
      } else {
        suggestedGroup = getModelGroup(flowType, nextTier, { agentRole });
      }
      return {
        shouldEscalate: true,
        suggestedModelGroup: suggestedGroup,
        reason: 'Repeated errors - tier escalation needed',
      };
    }

    if (state.noProgressTurns >= 5) {
      let suggestedGroup: string;
      if (flowType === 'sequential-thinking' && agentRole) {
        suggestedGroup = getAgentRoleGroup(agentRole, nextTier);
      } else {
        suggestedGroup = getModelGroup(flowType, nextTier, { agentRole });
      }
      return {
        shouldEscalate: true,
        suggestedModelGroup: suggestedGroup,
        reason: 'No progress - tier escalation needed',
      };
    }

    if (turn.status === 'stuck') {
      let suggestedGroup: string;
      if (flowType === 'sequential-thinking' && agentRole) {
        suggestedGroup = getAgentRoleGroup(agentRole, nextTier);
      } else {
        suggestedGroup = getModelGroup(flowType, nextTier, { agentRole });
      }
      return {
        shouldEscalate: true,
        suggestedModelGroup: suggestedGroup,
        reason: 'Model reported stuck - tier escalation needed',
      };
    }
  }

  // Legacy fallback: simple tier escalation without flow context
  const tiers: Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const currentIndex = tiers.indexOf(currentTier);
  if (currentIndex >= tiers.length - 1) {
    return { shouldEscalate: false, reason: 'Already at max tier' };
  }

  if (consecutiveLowConfidenceTurns >= 3) {
    const nextTier = tiers[currentIndex + 1];
    const suggestedGroup = currentModelGroup.replace(/tier[1-4]/, nextTier);
    return {
      shouldEscalate: true,
      suggestedModelGroup: suggestedGroup,
      reason: 'Low confidence - tier escalation needed',
    };
  }

  if (state.sameErrorCount >= 3) {
    const nextTier = tiers[currentIndex + 1];
    const suggestedGroup = currentModelGroup.replace(/tier[1-4]/, nextTier);
    return {
      shouldEscalate: true,
      suggestedModelGroup: suggestedGroup,
      reason: 'Repeated errors - tier escalation needed',
    };
  }

  if (state.noProgressTurns >= 5) {
    const nextTier = tiers[currentIndex + 1];
    const suggestedGroup = currentModelGroup.replace(/tier[1-4]/, nextTier);
    return {
      shouldEscalate: true,
      suggestedModelGroup: suggestedGroup,
      reason: 'No progress - tier escalation needed',
    };
  }

  if (turn.status === 'stuck') {
    const nextTier = tiers[currentIndex + 1];
    const suggestedGroup = currentModelGroup.replace(/tier[1-4]/, nextTier);
    return {
      shouldEscalate: true,
      suggestedModelGroup: suggestedGroup,
      reason: 'Model reported stuck - tier escalation needed',
    };
  }

  return { shouldEscalate: false, reason: 'No escalation triggers hit' };
}

/**
 * Check if de-escalation should occur based on high confidence
 * Returns suggested model group for lower tier, or null if at tier1
 */
export function checkDeescalationTriggers(
  confidenceScore: number,
  currentModelGroup: string
): EscalationDecision {
  // Only de-escalate if confidence is very high (85+)
  if (confidenceScore < 85) {
    return { shouldEscalate: false, reason: 'Confidence below de-escalation threshold' };
  }

  // Parse current tier from model group
  const tierMatch = currentModelGroup.match(/tier[1-4]/);
  const currentTier = (tierMatch?.[0] as Tier) || 'tier2';

  const tiers: Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const currentIndex = tiers.indexOf(currentTier);

  if (currentIndex <= 0) {
    return { shouldEscalate: false, reason: 'Already at tier1' };
  }

  const lowerTier = tiers[currentIndex - 1];
  const suggestedGroup = currentModelGroup.replace(/tier[1-4]/, lowerTier);

  return {
    shouldEscalate: true,
    suggestedModelGroup: suggestedGroup,
    reason: 'High confidence - tier de-escalation safe',
  };
}

/**
 * Get the next tier up (for sequential thinking flow)
 * Uses the new tiered model group system
 */
export function getNextTierUp(
  currentTier: Tier,
  flowType: FlowTypeString,
  agentRole?: AgentRoleString
): Tier | null {
  return getNextTier(currentTier, flowType, agentRole);
}

/**
 * Check if we're at maximum tier for a flow
 */
export function isAtMaximumTier(
  currentTier: Tier,
  flowType: FlowTypeString,
  agentRole?: AgentRoleString
): boolean {
  const maxTier = flowType === 'sequential-thinking' && agentRole
    ? getAgentRoleMaxTier(agentRole)
    : getMaxTier(flowType, agentRole);
  return currentTier === maxTier;
}

// Re-export tier helpers for backward compatibility
export { getNextTierUp as getNextModel, isAtMaximumTier as isAtMaxEscalation };
