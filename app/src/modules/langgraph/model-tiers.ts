import type { AgentRole } from '../litellm/types';

// Tier order for escalation
export const TIER_ORDER: readonly ('tier1' | 'tier2' | 'tier3' | 'tier4')[] = [
  'tier1',
  'tier2',
  'tier3',
  'tier4',
] as const;

export type Tier = typeof TIER_ORDER[number];

/**
 * Check if we're at the maximum tier
 */
export function isAtMaxTier(tier: Tier): boolean {
  return tier === 'tier4';
}

/**
 * Get the next tier up, or null if already at max
 */
export function getNextTier(tier: Tier): Tier | null {
  const currentIdx = TIER_ORDER.indexOf(tier);
  if (currentIdx >= TIER_ORDER.length - 1) {
    return null;
  }
  return TIER_ORDER[currentIdx + 1];
}

/**
 * Get the reflection tier (one above worker tier)
 */
export function getReflectionTier(workerTier: Tier): Tier {
  return getNextTier(workerTier) || workerTier;
}

/**
 * Escalate tier while preserving capability tags
 * Returns null if already at max tier
 */
export function escalateTier(tags: string[]): string[] | null {
  const currentTier = tags.find(t => t.startsWith('tier'));
  if (!currentTier) {
    return null;
  }

  const tierIndex = TIER_ORDER.indexOf(currentTier as Tier);
  if (tierIndex >= TIER_ORDER.length - 1) {
    return null; // Already at max
  }

  const nextTier = TIER_ORDER[tierIndex + 1];
  return tags.map(t => t.startsWith('tier') ? nextTier : t);
}

/**
 * Build tags for a flow type
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
      return ['tier2', 'general'];
    case 'dialectic':
      return ['tier2', 'websearch'];
    case 'consensus':
      return ['tier2', 'general'];
    case 'angel-devil':
      return ['tier2', 'general'];
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
 */
export function getReflectionTags(workerTags: string[]): string[] {
  const tier = workerTags.find(t => t.startsWith('tier')) as Tier || 'tier2';
  const reflectionTier = getReflectionTier(tier);
  return [reflectionTier, 'thinking'];
}
