import type { AgentRole } from '../litellm/types';

// Define Tier type locally first
export type Tier = 'tier1' | 'tier2' | 'tier3' | 'tier4';

// Re-export all model group functions from litellm module
// These provide the new tiered model group system
export {
  // New tiered model group system
  getModelGroup,
  getAgentRoleGroup,
  getStartingTier,
  getMaxTier,
  getAgentRoleMaxTier,
  getNextTier,
  getClassifierModel,
  // Legacy functions (for backward compatibility)
  buildModelGroup,
  parseModelGroup,
  tagsToModelGroup,
  getModelGroupForFlow,
  getModelGroupForAgentRole,
  getReflectionModelGroup,
  getClassifierModelGroup,
  // Types (excluding Tier which is defined above)
  type ModelType,
  type ModelMode,
  type FlowTypeString,
  type AgentRoleString,
  TIER_ORDER,
} from '../litellm/model-groups';

/**
 * Check if we're at the maximum tier
 * @deprecated Use getMaxTier() from litellm/model-groups instead
 */
export function isAtMaxTier(tier: Tier): boolean {
  return tier === 'tier4';
}

/**
 * Get the next tier up, or null if already at max
 * @deprecated Use getNextTier() from litellm/model-groups instead
 */
export function getNextTierOld(tier: Tier): Tier | null {
  const TIER_ORDER: readonly Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const currentIdx = TIER_ORDER.indexOf(tier);
  if (currentIdx >= TIER_ORDER.length - 1) {
    return null;
  }
  return TIER_ORDER[currentIdx + 1];
}

/**
 * Get the reflection tier (one above worker tier)
 * @deprecated Use getNextTier() from litellm/model-groups instead
 */
export function getReflectionTier(workerTier: Tier): Tier {
  return getNextTierOld(workerTier) || workerTier;
}

/**
 * Escalate tier while preserving capability tags
 * Returns null if already at max tier
 * @deprecated This function is for legacy tag-based routing. Use getNextTier() instead.
 */
export function escalateTier(tags: string[]): string[] | null {
  const TIER_ORDER: readonly Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const currentTier = tags.find((t) => t.startsWith('tier'));
  if (!currentTier) {
    return null;
  }

  const tierIndex = TIER_ORDER.indexOf(currentTier as Tier);
  if (tierIndex >= TIER_ORDER.length - 1) {
    return null; // Already at max
  }

  const nextTier = TIER_ORDER[tierIndex + 1];
  return tags.map((t) => (t.startsWith('tier') ? nextTier : t));
}

/**
 * De-escalate tier (one level down) while preserving capability tags
 * Returns null if already at tier1
 * @deprecated This function is for legacy tag-based routing.
 */
export function deescalateTier(tags: string[]): string[] | null {
  const TIER_ORDER: readonly Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const currentTier = tags.find((t) => t.startsWith('tier'));
  if (!currentTier) {
    return null;
  }

  const tierIndex = TIER_ORDER.indexOf(currentTier as Tier);
  if (tierIndex <= 0) {
    return null; // Already at tier1
  }

  const prevTier = TIER_ORDER[tierIndex - 1];
  return tags.map((t) => (t.startsWith('tier') ? prevTier : t));
}

/**
 * Build tags for a flow type
 * @deprecated Use getModelGroup() from litellm/model-groups instead
 */
export function buildTags(
  flowType: string,
  startingTier: Tier,
  options?: {
    websearch?: boolean;
    agentRole?: AgentRole;
  }
): string[] {
  switch (flowType) {
    case 'social':
      return ['tier1', 'social'];
    case 'proofreader':
      return ['tier1', 'general'];
    case 'simple':
      return options?.websearch
        ? [startingTier, 'websearch']
        : [startingTier, 'general'];
    case 'shell':
      return ['tier2', 'programming'];
    case 'dialectic':
      return ['tier2', 'websearch'];
    case 'consensus':
      return ['tier2', 'general'];
    case 'angel-devil':
      return ['tier2', 'general'];
    case 'adversarial-validation':
      return ['tier2', 'general']; // Generator starts at tier2, red-team at tier3, judge at tier3
    case 'chain-of-verification':
      return ['tier2', 'general']; // Baseline/verifier at tier2, reviser at tier3
    case 'backcasting':
      return ['tier2', 'thinking']; // Goal definition at tier2, milestones/feasibility at tier3
    case 'delphi-method':
      return ['tier2', 'thinking']; // Experts at tier2, judge at tier3
    case 'branch':
      return ['tier3', 'thinking'];
    case 'architecture':
      return ['tier4', 'tools', 'programming'];
    case 'sequential-thinking':
      return options?.agentRole
        ? getAgentRoleTags(options.agentRole)
        : ['tier2', 'tools', 'programming'];
    case 'breakglass':
      return ['tier4', 'tools'];
    default:
      return [startingTier, 'general'];
  }
}

/**
 * Get tags for specific agent role (Sequential Thinking)
 * @deprecated Use getAgentRoleGroup() from litellm/model-groups instead
 */
export function getAgentRoleTags(agentRole: AgentRole): string[] {
  switch (agentRole) {
    case 'command-executor':
      return ['tier2', 'tools', 'general'];
    case 'python-coder':
    case 'js-ts-coder':
      return ['tier2', 'tools', 'programming'];
    case 'devops-engineer':
    case 'documentation-writer':
    case 'dba':
      return ['tier3', 'tools', 'general'];
    case 'architect':
      return ['tier4', 'tools', 'thinking'];
    case 'code-reviewer':
      return ['tier3', 'tools', 'programming'];
    case 'researcher':
      return ['tier2', 'tools', 'general'];
    case 'shell-commander':
      return ['tier2', 'general'];
    default:
      return ['tier2', 'tools', 'general'];
  }
}

/**
 * Get reflection tags (one tier above worker, add thinking)
 * @deprecated Use getNextTier() and getAgentRoleGroup() instead
 */
export function getReflectionTags(workerTags: string[]): string[] {
  const tier = (workerTags.find((t) => t.startsWith('tier')) as Tier) || 'tier2';
  const reflectionTier = getReflectionTier(tier);
  return [reflectionTier, 'thinking'];
}
