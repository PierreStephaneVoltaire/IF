import { createLogger } from '../utils/logger';
import { TaskType, FlowType } from '../modules/litellm/types';
import type { FilterContext } from './types';

const log = createLogger('CLASSIFY');

export function inferTaskType(isTechnical: boolean): TaskType {
  return isTechnical ? TaskType.CODING_IMPLEMENTATION : TaskType.GENERAL_CONVO;
}

export function shouldSkipPlanning(taskType: TaskType): boolean {
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

export function isBranchRequest(message: string, confidenceScore?: number): boolean {
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
  
  // Also trigger branch flow if confidence is below 60
  const lowConfidence = confidenceScore !== undefined && confidenceScore < 60;
  
  if (lowConfidence) {
    log.info(`Branch flow triggered due to low confidence: ${confidenceScore}`);
  }
  
  return hasTrigger || lowConfidence;
}
// Determine if a flow needs workspace access
export function flowNeedsWorkspace(flowType: FlowType): boolean {
  switch (flowType) {
    case FlowType.SEQUENTIAL_THINKING:
    case FlowType.ARCHITECTURE:
    case FlowType.BRANCH:
      return true;
    case FlowType.SOCIAL:
    case FlowType.PROOFREADER:
    case FlowType.SHELL:
    case FlowType.SIMPLE:
    case FlowType.BREAKGLASS:
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
  if (message && isBranchRequest(message, confidenceScore)) {
    log.info(`Routing to: BRANCH flow (detected multi-solution request or low confidence)`);
    return FlowType.BRANCH;
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
