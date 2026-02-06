import { createLogger } from '../utils/logger';
import { TaskType, FlowType } from '../modules/litellm/types';
import type { FilterContext } from './types';

const log = createLogger('CLASSIFY');

function inferTaskType(isTechnical: boolean): TaskType {
  return isTechnical ? TaskType.CODING_IMPLEMENTATION : TaskType.GENERAL_CONVO;
}

function shouldSkipPlanning(taskType: TaskType): boolean {
  const skipPlanningTasks = new Set([
    TaskType.TECHNICAL_QA,
    TaskType.DOC_SEARCH,
    TaskType.EXPLANATION,
    TaskType.SOCIAL,
    TaskType.GENERAL_CONVO,
    TaskType.SHELL_COMMAND,  // Shell commands don't need planning
  ]);

  return skipPlanningTasks.has(taskType);
}

function isBranchRequest(
  message: string,
  confidenceScore?: number,
  isTechnical?: boolean
): boolean {
  const lower = message.toLowerCase();

  // Branch flow triggers: Architectural exploration, multiple approaches, theoretical discussion
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

  // Also trigger branch flow if confidence is below 60 (only for technical flows)
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

/**
 * Check if message is a moral/ethical dilemma (Angel/Devil flow)
 */
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

/**
 * Check if message is a philosophical/abstract question (Dialectic flow)
 */
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

/**
 * Check if message is a factual/trivia question (Consensus flow)
 */
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
// Determine if a flow needs workspace access
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

export function classifyFlow(
  isTechnical: boolean,
  taskType?: TaskType,
  useAgenticLoop?: boolean,
  filterContext?: FilterContext,
  message?: string,
  confidenceScore?: number
): FlowType {
  log.info(`Classification: is_technical=${isTechnical}, task_type=${taskType || 'undefined'}, use_agentic_loop=${useAgenticLoop || false}`);

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
  // Priority: Angel/Devil (moral) > Dialectic (philosophical) > Consensus (factual)

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

  const effectiveTaskType = taskType || inferTaskType(isTechnical);

  // Map task type to flow type using clean switch statement
  switch (effectiveTaskType) {
    case TaskType.SOCIAL:
      log.info(`Routing to: SOCIAL flow for ${effectiveTaskType}`);
      return FlowType.SOCIAL;
    case TaskType.PROOFREADER:
      log.info(`Routing to: PROOFREADER flow for ${effectiveTaskType}`);
      return FlowType.PROOFREADER;
    case TaskType.SHELL_COMMAND:
      log.info(`Routing to: SHELL flow for shell command suggestions`);
      return FlowType.SHELL;
    case TaskType.ARCHITECTURE_ANALYSIS:
      log.info(`Routing to: ARCHITECTURE flow for ${effectiveTaskType}`);
      return FlowType.ARCHITECTURE;
    case TaskType.CODING_IMPLEMENTATION:
    case TaskType.DEVOPS_IMPLEMENTATION:
    case TaskType.DATABASE_DESIGN:
    case TaskType.CODE_REVIEW:
    case TaskType.DOCUMENTATION_WRITER:
    case TaskType.TOOL_EXECUTION:
    case TaskType.COMMAND_RUNNER:
    case TaskType.TEST_RUNNER:
      log.info(`Routing to: SEQUENTIAL_THINKING flow for ${effectiveTaskType}`);
      return FlowType.SEQUENTIAL_THINKING;
    case TaskType.GENERAL_CONVO:
    case TaskType.TECHNICAL_QA:
    case TaskType.DOC_SEARCH:
    case TaskType.EXPLANATION:
    case TaskType.WRITING:
    default:
      log.info(`Routing to: SIMPLE flow for ${effectiveTaskType}`);
      return FlowType.SIMPLE;
  }
}
