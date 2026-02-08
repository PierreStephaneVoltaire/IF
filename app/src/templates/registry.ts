import { TaskType, AgentRole, TaskComplexity } from '../modules/litellm/types';


// Map roles to template files
export const AGENT_TEMPLATE_MAP: Record<AgentRole, string> = {
  [AgentRole.COMMAND_EXECUTOR]: 'command-executor',
  [AgentRole.PYTHON_CODER]: 'python-coder',
  [AgentRole.JS_TS_CODER]: 'js-ts-coder',
  [AgentRole.DEVOPS_ENGINEER]: 'devops-engineer',
  [AgentRole.ARCHITECT]: 'architect',
  [AgentRole.CODE_REVIEWER]: 'code-reviewer',
  [AgentRole.DOCUMENTATION_WRITER]: 'documentation-writer',
  [AgentRole.DBA]: 'dba',
  [AgentRole.RESEARCHER]: 'researcher',
  [AgentRole.SHELL_COMMANDER]: 'shell-command',
};

// Tasks that use agentic loop
export const AGENTIC_TASKS: Set<TaskType> = new Set([
  TaskType.CODING_IMPLEMENTATION,
  TaskType.DEVOPS_IMPLEMENTATION,
  TaskType.DATABASE_DESIGN,
  TaskType.CODE_REVIEW,
]);

// Map task types to prompt categories for simple/technical-simple flows
export const TASK_TYPE_TO_PROMPT: Record<string, string> = {
  // Technical simple (no tools needed)
  [TaskType.TECHNICAL_QA]: 'technical-qa',
  [TaskType.ARCHITECTURE_ANALYSIS]: 'architecture-analysis',
  [TaskType.DOC_SEARCH]: 'doc-search',

  // Non-technical
  [TaskType.EXPLANATION]: 'explanation',
  [TaskType.SOCIAL]: 'social',
  [TaskType.GENERAL_CONVO]: 'general',
  [TaskType.WRITING]: 'general',

  // Shell commands (no tools needed)
  [TaskType.SHELL_COMMAND]: 'shell-command',
};


// Max turns by complexity
export const MAX_TURNS_BY_COMPLEXITY: Record<TaskComplexity, number> = {
  [TaskComplexity.SIMPLE]: 10,
  [TaskComplexity.MEDIUM]: 20,
  [TaskComplexity.COMPLEX]: 35,
};

// Checkpoint intervals by complexity
export const CHECKPOINT_INTERVAL_BY_COMPLEXITY: Record<TaskComplexity, number> = {
  [TaskComplexity.SIMPLE]: 3,
  [TaskComplexity.MEDIUM]: 5,
  [TaskComplexity.COMPLEX]: 5,
};

export function getTemplateForAgent(role: AgentRole): string {
  return AGENT_TEMPLATE_MAP[role] || 'coding';
}


export function shouldUseAgenticLoop(taskType: TaskType): boolean {
  return AGENTIC_TASKS.has(taskType);
}

export function getMaxTurns(complexity: TaskComplexity, estimated?: number): number {
  const base = MAX_TURNS_BY_COMPLEXITY[complexity] || 20;
  return estimated && estimated > 0 ? Math.min(estimated, base) : base;
}

export function getCheckpointInterval(complexity: TaskComplexity): number {
  return CHECKPOINT_INTERVAL_BY_COMPLEXITY[complexity] || 5;
}

export function getPromptForTaskType(taskType: TaskType): string {
  return TASK_TYPE_TO_PROMPT[taskType] || 'general';
}

export function getModelForAgent(_role?: AgentRole): string {
  return 'auto';
}

export function getModelForTaskType(_taskType?: TaskType): string {
  return 'auto';
}

/**
 * Get tags for an agent role (for tag-based model routing)
 * 
 * @param agentRole - The agent role
 * @returns Array of tags for model routing
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
