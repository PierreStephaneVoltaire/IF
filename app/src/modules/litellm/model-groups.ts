import type { Tier } from '../langgraph/model-tiers';
import { AgentRole, FlowType } from './types';

// =============================================================================
// Model Group Naming Convention
// Format: {flow-type}-{tier} or {agent-role}-{tier}
// - flow-type: simple, social, proofreader, shell, sequential-thinking, etc.
// - agent-role: python-coder, js-ts-coder, devops-engineer, architect, etc.
// - tier: tier1, tier2, tier3, tier4
// Examples: simple-tier2, python-coder-tier3, social-tier1
// =============================================================================

export type ModelType = 'programming' | 'general' | 'websearch' | 'social' | 'classifier';
export type ModelMode = 'thinking' | 'creative' | '';

export interface ModelGroup {
  type: ModelType;
  tier: Tier;
  mode: ModelMode;
  hasTools: boolean;
}

// Re-export Tier type for convenience
export type { Tier };

// Tier order for escalation
export const TIER_ORDER: readonly Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'] as const;

// =============================================================================
// Flow Type String Type (matches classifier output)
// =============================================================================

export type FlowTypeString =
  | 'simple'
  | 'social'
  | 'proofreader'
  | 'shell'
  | 'sequential-thinking'
  | 'architecture'
  | 'branch'
  | 'dialectic'
  | 'consensus'
  | 'angel-devil'
  | 'adversarial-validation'
  | 'chain-of-verification'
  | 'backcasting'
  | 'delphi-method'
  | 'breakglass';

export type AgentRoleString =
  | 'command-executor'
  | 'python-coder'
  | 'js-ts-coder'
  | 'devops-engineer'
  | 'architect'
  | 'code-reviewer'
  | 'documentation-writer'
  | 'dba'
  | 'researcher'
  | 'shell-commander';

// =============================================================================
// New Tiered Model Group System
// =============================================================================

/**
 * Get the model group name for a flow type at a specific tier
 * Returns the model_name that LiteLLM will use to load-balance
 */
export function getModelGroup(
  flowType: FlowTypeString,
  tier: Tier,
  options?: {
    websearch?: boolean;
    agentRole?: AgentRoleString;
  }
): string {
  switch (flowType) {
    case 'social':
      return 'social-tier1'; // Always tier1 (ignore tier param)

    case 'simple':
      if (options?.websearch) {
        // Websearch available at tier2, tier3, tier4
        // Classifier will never assign tier1 with websearch
        return `simple-websearch-${tier}`;
      }
      // Simple available at tier1, tier2
      return `simple-${tier}`;

    case 'proofreader':
      return 'proofreader-tier1'; // Always tier1

    case 'shell':
      return 'shell-tier2'; // Always tier2

    case 'architecture':
      return 'architecture-tier4'; // Always tier4

    case 'branch':
      // Available at tier3, tier4 (classifier starts at tier3)
      return `branch-${tier}`;

    case 'sequential-thinking':
      // Delegate to agent role function
      return getAgentRoleGroup(options?.agentRole || 'python-coder', tier);

    case 'dialectic':
      return 'dialectic-tier2'; // Always tier2

    case 'consensus':
      // Available at tier2, tier3
      return `consensus-${tier}`;

    case 'angel-devil':
      // Available at tier2, tier3
      return `angel-devil-${tier}`;

    case 'adversarial-validation':
      // Available at tier2, tier3
      return `adversarial-validation-${tier}`;

    case 'chain-of-verification':
      // Available at tier2, tier3
      return `chain-of-verification-${tier}`;

    case 'backcasting':
      // Available at tier2, tier3
      return `backcasting-${tier}`;

    case 'delphi-method':
      // Available at tier2, tier3
      return `delphi-method-${tier}`;

    case 'breakglass':
      return 'breakglass-tier4'; // Always tier4

    default:
      return `simple-${tier}`; // Fallback
  }
}

/**
 * Get the model group name for an agent role at a specific tier
 */
export function getAgentRoleGroup(agentRole: AgentRoleString, tier: Tier): string {
  switch (agentRole) {
    case 'command-executor':
      return 'command-executor-tier2'; // Always tier2

    case 'python-coder':
      // Available at tier2, tier3, tier4
      return `python-coder-${tier}`;

    case 'js-ts-coder':
      // Available at tier2, tier3, tier4
      return `js-ts-coder-${tier}`;

    case 'devops-engineer':
      return 'devops-engineer-tier3'; // Always tier3

    case 'architect':
      return 'architect-role-tier4'; // Always tier4

    case 'code-reviewer':
      // Available at tier3, tier4
      return `code-reviewer-${tier}`;

    case 'documentation-writer':
      return 'documentation-writer-tier3'; // Always tier3

    case 'dba':
      return 'dba-tier3'; // Always tier3

    case 'researcher':
      return 'researcher-tier2'; // Always tier2

    case 'shell-commander':
      return 'shell-commander-tier2'; // Always tier2

    default:
      return `python-coder-${tier}`; // Fallback
  }
}

/**
 * Get the starting tier for a flow type (matches classifier output)
 */
export function getStartingTier(flowType: FlowTypeString): Tier {
  switch (flowType) {
    // Tier 1 flows
    case 'social':
    case 'proofreader':
      return 'tier1';

    // Tier 2 flows
    case 'simple':
    case 'shell':
    case 'dialectic':
    case 'consensus':
    case 'angel-devil':
    case 'adversarial-validation':
    case 'chain-of-verification':
    case 'backcasting':
    case 'delphi-method':
    case 'sequential-thinking':
      return 'tier2';

    // Tier 3 flows
    case 'branch':
      return 'tier3';

    // Tier 4 flows
    case 'architecture':
    case 'breakglass':
      return 'tier4';

    default:
      return 'tier2';
  }
}

/**
 * Get the maximum tier a flow supports
 */
export function getMaxTier(flowType: FlowTypeString, agentRole?: AgentRoleString): Tier {
  switch (flowType) {
    // Tier-locked flows (no escalation possible)
    case 'social':
    case 'proofreader':
      return 'tier1';
    case 'shell':
    case 'dialectic':
      return 'tier2';
    case 'architecture':
    case 'breakglass':
      return 'tier4';

    // Tier-spanning flows
    case 'simple':
      return 'tier2'; // tier1-2
    case 'consensus':
    case 'angel-devil':
    case 'adversarial-validation':
    case 'chain-of-verification':
    case 'backcasting':
    case 'delphi-method':
      return 'tier3'; // tier2-3
    case 'branch':
      return 'tier4'; // tier3-4

    // Sequential thinking depends on agent role
    case 'sequential-thinking':
      return getAgentRoleMaxTier(agentRole || 'python-coder');

    default:
      return 'tier4';
  }
}

/**
 * Get the maximum tier an agent role supports
 */
export function getAgentRoleMaxTier(agentRole: AgentRoleString): Tier {
  switch (agentRole) {
    case 'command-executor':
    case 'researcher':
    case 'shell-commander':
      return 'tier2'; // Locked to tier2

    case 'devops-engineer':
    case 'documentation-writer':
    case 'dba':
      return 'tier3'; // Locked to tier3

    case 'architect':
      return 'tier4'; // Locked to tier4

    case 'python-coder':
    case 'js-ts-coder':
      return 'tier4'; // tier2-3-4

    case 'code-reviewer':
      return 'tier4'; // tier3-4

    default:
      return 'tier4';
  }
}

/**
 * Get the next tier for escalation
 * Returns null if already at max tier for this flow
 */
export function getNextTier(
  currentTier: Tier,
  flowType: FlowTypeString,
  agentRole?: AgentRoleString
): Tier | null {
  const tiers: Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const maxTier = getMaxTier(flowType, agentRole);
  const currentIndex = tiers.indexOf(currentTier);
  const maxIndex = tiers.indexOf(maxTier);

  if (currentIndex >= maxIndex) {
    return null; // Already at max for this flow
  }

  return tiers[currentIndex + 1];
}

/**
 * Get the classifier model group (load-balanced)
 */
export function getClassifierModel(): string {
  return 'classifier';
}

// =============================================================================
// Legacy Functions (for backward compatibility during migration)
// =============================================================================

/**
 * Parse a model group string back into components
 * @param group - Model group string like "programming-tier2-thinking-tools"
 * @returns ModelGroup object
 * @deprecated Use the new tiered model group system instead
 */
export function parseModelGroup(group: string): ModelGroup {
  const parts = group.split('-');
  const result: ModelGroup = {
    type: 'general',
    tier: 'tier2',
    mode: '',
    hasTools: false,
  };

  // Find tier (starts with 'tier')
  const tierIndex = parts.findIndex((p) => p.startsWith('tier'));
  if (tierIndex !== -1) {
    result.tier = parts[tierIndex] as Tier;
  }

  // Type is first part (before tier)
  if (tierIndex > 0) {
    const typeCandidate = parts[0];
    if (['programming', 'general', 'websearch', 'social', 'classifier'].includes(typeCandidate)) {
      result.type = typeCandidate as ModelType;
    }
  }

  // Check for mode (thinking, creative) between type/tier and tools
  for (let i = tierIndex + 1; i < parts.length; i++) {
    if (parts[i] === 'tools') {
      result.hasTools = true;
    } else if (['thinking', 'creative'].includes(parts[i])) {
      result.mode = parts[i] as ModelMode;
    }
  }

  return result;
}

/**
 * Build a model group name from components
 * Format: {type}-{tier}-{mode}-{tools}
 * Only includes non-empty optional components
 * @deprecated Use getModelGroup() or getAgentRoleGroup() instead
 */
export function buildModelGroup(
  type: ModelType,
  tier: Tier,
  mode: ModelMode = '',
  hasTools: boolean = false
): string {
  const parts: string[] = [type, tier];

  if (mode) {
    parts.push(mode);
  }

  if (hasTools) {
    parts.push('tools');
  }

  return parts.join('-');
}

/**
 * Convert legacy tags to model group name
 * Legacy tags: ['tier2', 'tools', 'programming']
 * New format: 'programming-tier2-tools'
 * @deprecated Use getModelGroup() instead
 */
export function tagsToModelGroup(tags: string[]): string {
  const tier = (tags.find((t) => t.startsWith('tier')) as Tier) || 'tier2';
  const hasTools = tags.includes('tools');
  const mode = tags.includes('thinking') ? 'thinking' : tags.includes('creative') ? 'creative' : '';

  // Determine type from tags
  let type: ModelType = 'general';
  if (tags.includes('programming')) {
    type = 'programming';
  } else if (tags.includes('websearch')) {
    type = 'websearch';
  } else if (tags.includes('social')) {
    type = 'social';
  } else if (tags.includes('classifier')) {
    type = 'classifier';
  }

  return buildModelGroup(type, tier, mode, hasTools);
}

/**
 * Get model group for a flow type (legacy compatibility)
 * @deprecated Use getModelGroup() instead
 */
export function getModelGroupForFlow(
  flowType: FlowType,
  startingTier: Tier,
  options?: {
    websearch?: boolean;
    agentRole?: AgentRole;
  }
): string {
  // Map FlowType enum to FlowTypeString
  const flowTypeMap: Record<FlowType, FlowTypeString> = {
    [FlowType.SIMPLE]: 'simple',
    [FlowType.SEQUENTIAL_THINKING]: 'sequential-thinking',
    [FlowType.BRANCH]: 'branch',
    [FlowType.BREAKGLASS]: 'breakglass',
    [FlowType.SHELL]: 'shell',
    [FlowType.ARCHITECTURE]: 'architecture',
    [FlowType.SOCIAL]: 'social',
    [FlowType.PROOFREADER]: 'proofreader',
    [FlowType.DIALECTIC]: 'dialectic',
    [FlowType.CONSENSUS]: 'consensus',
    [FlowType.ANGEL_DEVIL]: 'angel-devil',
    [FlowType.ADVERSARIAL_VALIDATION]: 'adversarial-validation',
    [FlowType.CHAIN_OF_VERIFICATION]: 'chain-of-verification',
    [FlowType.BACKCASTING]: 'backcasting',
    [FlowType.DELPHI_METHOD]: 'delphi-method',
  };

  const flowTypeString = flowTypeMap[flowType];
  if (!flowTypeString) {
    return `simple-${startingTier}`;
  }

  // Map AgentRole enum to AgentRoleString if provided
  let agentRoleString: AgentRoleString | undefined;
  if (options?.agentRole) {
    agentRoleString = options.agentRole as unknown as AgentRoleString;
  }

  return getModelGroup(flowTypeString, startingTier, {
    websearch: options?.websearch,
    agentRole: agentRoleString,
  });
}

/**
 * Get model group for an agent role (legacy compatibility)
 * @deprecated Use getAgentRoleGroup() instead
 */
export function getModelGroupForAgentRole(agentRole?: AgentRole): string {
  if (!agentRole) {
    return 'python-coder-tier2';
  }
  return getAgentRoleGroup(agentRole as unknown as AgentRoleString, 'tier2');
}

/**
 * Get reflection model group (one tier above, add thinking mode)
 * @deprecated Use getNextTier() and getAgentRoleGroup() instead
 */
export function getReflectionModelGroup(workerModelGroup: string): string {
  const parsed = parseModelGroup(workerModelGroup);
  const tierOrder: Tier[] = ['tier1', 'tier2', 'tier3', 'tier4'];
  const currentIndex = tierOrder.indexOf(parsed.tier);
  const reflectionTier =
    currentIndex < tierOrder.length - 1 ? tierOrder[currentIndex + 1] : parsed.tier;

  return buildModelGroup(parsed.type, reflectionTier, 'thinking', parsed.hasTools);
}

/**
 * Get classifier model group (always tier1)
 * @deprecated Use getClassifierModel() instead
 */
export function getClassifierModelGroup(): string {
  return buildModelGroup('classifier', 'tier1', '', false);
}

/**
 * Get all possible model group variants for a base model
 * For models with multiple tier support, generate all combinations
 * Format on LiteLLM side will be: {base_model}_{group}
 */
export function getModelGroupVariants(baseModel: string, group: string): string[] {
  // Return the mapped model name for the group
  // The LiteLLM proxy will handle the routing based on the group name
  return [`${baseModel}_${group}`];
}
