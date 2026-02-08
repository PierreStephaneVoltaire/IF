import { createLogger } from '../utils/logger';
import { classifyRequest as opusClassifyRequest } from '../modules/litellm/opus';
import { buildTags } from '../modules/langgraph/model-tiers';
import { FlowType, type AgentRole } from '../modules/litellm/types';
import type { FilterContext } from './types';

const log = createLogger('CLASSIFY');

export interface ClassifyInput {
  filter: FilterContext;
  history: {
    formatted_history: string;
    current_author: string;
    current_message: string;
  };
  messageId: string;
}

export interface ClassifyOutput {
  flow_type: FlowType;
  starting_tier: 'tier1' | 'tier2' | 'tier3' | 'tier4';
  websearch: boolean;
  tags: string[];
  agent_role?: AgentRole;
}

export interface ClassifyRequestContext {
  author: string;
  force_respond: boolean;
  history: string;
  message: string;
}

/**
 * Determine if a flow needs workspace access
 */
export function flowNeedsWorkspace(flowType: FlowType): boolean {
  switch (flowType) {
    case FlowType.SEQUENTIAL_THINKING:
      return true;
    case FlowType.SOCIAL:
    case FlowType.PROOFREADER:
    case FlowType.SHELL:
    case FlowType.SIMPLE:
    case FlowType.BREAKGLASS:
    case FlowType.ARCHITECTURE:
    case FlowType.BRANCH:
    case FlowType.DIALECTIC:
    case FlowType.CONSENSUS:
    case FlowType.ANGEL_DEVIL:
    default:
      return false;
  }
}

/**
 * Classify the request using LLM (Phase 2 of the new flow)
 */
export async function classifyRequest(input: ClassifyInput): Promise<ClassifyOutput> {
  log.info(`Classifying request for message ${input.messageId}`);

  // Bypass for breakglass flow
  if (input.filter.is_breakglass) {
    log.info(`Breakglass flow detected, bypassing classification`);
    const tags = ['tier4', 'tools'];
    return {
      flow_type: FlowType.BREAKGLASS,
      starting_tier: 'tier4',
      websearch: false,
      tags,
    };
  }

  // Call the LLM classifier
  const context: ClassifyRequestContext = {
    author: input.history.current_author,
    force_respond: input.filter.force_respond,
    history: input.history.formatted_history,
    message: input.history.current_message,
  };

  const classifyResult = await opusClassifyRequest(context, input.messageId);

  // Build tags from the classification result
  const tags = buildTags(classifyResult.flow_type, classifyResult.starting_tier, {
    websearch: classifyResult.websearch,
    agentRole: classifyResult.agent_role,
  });

  log.info(`Classification result: flow=${classifyResult.flow_type}, tier=${classifyResult.starting_tier}, websearch=${classifyResult.websearch}`);
  log.info(`Built tags: ${tags.join(', ')}`);

  return {
    flow_type: classifyResult.flow_type,
    starting_tier: classifyResult.starting_tier,
    websearch: classifyResult.websearch,
    tags,
    agent_role: classifyResult.agent_role,
  };
}

/**
 * Legacy function - kept for backward compatibility
 * Maps task type to flow type using deterministic switch
 * @deprecated Use classifyRequest() instead for new flows
 */
export function classifyFlow(
  isTechnical: boolean,
  taskType?: string,
  useAgenticLoop?: boolean,
  filterContext?: FilterContext,
  message?: string,
  confidenceScore?: number
): FlowType {
  log.info(`Legacy classification: is_technical=${isTechnical}, task_type=${taskType || 'undefined'}`);

  // 1. Check for breakglass flow
  if (filterContext?.is_breakglass) {
    log.info(`Routing to: BREAKGLASS flow`);
    return FlowType.BREAKGLASS;
  }

  // 2. Check for branch flow (multi-solution brainstorming or low confidence)
  if (message && isBranchRequest(message, confidenceScore, isTechnical)) {
    log.info(`Routing to: BRANCH flow (detected multi-solution request or low confidence)`);
    return FlowType.BRANCH;
  }

  // 3. Check for thinking flows (Angel/Devil, Dialectic, Consensus)
  if (message && isAngelDevilRequest(message)) {
    log.info(`Routing to: ANGEL_DEVIL flow (detected moral/ethical dilemma)`);
    return FlowType.ANGEL_DEVIL;
  }

  if (message && isDialecticRequest(message)) {
    log.info(`Routing to: DIALECTIC flow (detected philosophical/abstract question)`);
    return FlowType.DIALECTIC;
  }

  if (message && isConsensusRequest(message)) {
    log.info(`Routing to: CONSENSUS flow (detected factual/trivia question)`);
    return FlowType.CONSENSUS;
  }

  // Default flow mapping based on task type
  const effectiveTaskType = taskType || (isTechnical ? 'coding-implementation' : 'general-convo');

  switch (effectiveTaskType) {
    case 'social':
      return FlowType.SOCIAL;
    case 'proofreader':
      return FlowType.PROOFREADER;
    case 'shell-command':
      return FlowType.SHELL;
    case 'architecture-analysis':
      return FlowType.ARCHITECTURE;
    case 'coding-implementation':
    case 'devops-implementation':
    case 'database-design':
    case 'code-review':
    case 'documentation-writer':
    case 'tool-execution':
    case 'command-runner':
    case 'test-runner':
      return FlowType.SEQUENTIAL_THINKING;
    default:
      return FlowType.SIMPLE;
  }
}

// ============================================================================
// Helper Functions (kept for legacy compatibility)
// ============================================================================

function isBranchRequest(
  message: string,
  confidenceScore?: number,
  isTechnical?: boolean
): boolean {
  const lower = message.toLowerCase();

  const branchTriggers = [
    'multiple solutions',
    'explore options',
    'what are my options',
    'different approaches',
    'different ways',
    'brainstorm',
    'think of alternatives',
    'alternative approaches',
    'architectural options',
    'compare approaches',
    'pros and cons',
    'tradeoffs',
    'trade-offs',
    'which approach',
    'explore architectures',
    'design options',
  ];

  const hasTrigger = branchTriggers.some(trigger => lower.includes(trigger));

  const normalizedConfidence = confidenceScore !== undefined && confidenceScore <= 1
    ? confidenceScore * 100
    : confidenceScore;
  const lowConfidence =
    isTechnical === true &&
    normalizedConfidence !== undefined &&
    normalizedConfidence < 60;

  if (lowConfidence) {
    log.info(`Branch flow triggered due to low confidence: ${confidenceScore}`);
  }

  return hasTrigger || lowConfidence;
}

function isAngelDevilRequest(message: string): boolean {
  const lower = message.toLowerCase();

  const angelDevilTriggers = [
    'should i',
    'is it right to',
    'is it wrong to',
    'ethical',
    'moral',
    'dilemma',
    'dilemna',
    'morally',
    'ethically',
    'right or wrong',
    'good or bad',
    'ought i',
    'would it be wrong',
    'would it be right',
  ];

  return angelDevilTriggers.some(trigger => lower.includes(trigger));
}

function isDialecticRequest(message: string): boolean {
  const lower = message.toLowerCase();

  const dialecticTriggers = [
    'meaning of',
    'nature of',
    'philosophically',
    'philosophy',
    'existential',
    'what is the purpose',
    'what is life',
    'what is consciousness',
    'what is reality',
    'what is truth',
    'what is justice',
    'what is beauty',
    'what is good',
    'what is evil',
    'what is free will',
    'what is identity',
    'what is the self',
    'in theory',
    'theoretically',
    'abstractly',
    'metaphysical',
    'ontological',
    'epistemological',
    'aesthetics',
  ];

  return dialecticTriggers.some(trigger => lower.includes(trigger));
}

function isConsensusRequest(message: string): boolean {
  const lower = message.toLowerCase();

  const consensusTriggers = [
    'is it true that',
    'fact check',
    'fact-check',
    'verify',
    'actually true',
    'really true',
    'how many',
    'when did',
    'where is',
    'who was',
    'what is the capital',
    'what year',
    'what date',
    'is it correct that',
    'can you confirm',
    'tell me if',
    'is this accurate',
    'is this correct',
    'what happened',
    'did you know',
    'trivia',
    'population of',
    'height of',
    'distance to',
  ];

  return consensusTriggers.some(trigger => lower.includes(trigger));
}
