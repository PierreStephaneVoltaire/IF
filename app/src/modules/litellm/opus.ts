import { chatCompletion, extractContent, extractJsonFromContent } from './index';
import { getConfig } from '../../config/index';
import { loadTemplate, renderTemplate } from '../../templates/loader';
import { createLogger } from '../../utils/logger';
import { shouldUseAgenticLoop } from '../../templates/registry';
import type {
  ShouldRespondContext,
  ShouldRespondResult,
  PlanningContext,
  PlanningResult,
  ClassifyRequestResult,
  TaskType,
  AgentRole,
  TaskComplexity,
} from './types';
import { FlowType } from './types';

const log = createLogger('LITELLM:OPUS');

const DEFAULT_SHOULD_RESPOND: ShouldRespondResult = {
  should_respond: false,
  reason: 'Could not parse response',
};

const DEFAULT_CLASSIFY_REQUEST: ClassifyRequestResult = {
  flow_type: FlowType.SIMPLE,
  starting_tier: 'tier2',
  websearch: false,
};

const DEFAULT_PLANNING: PlanningResult = {
  reformulated_prompt: '',
  topic_slug: 'general-task',
  is_new_topic: true,
  plan_content: '## Objective\nComplete the requested task.',
  instruction_content: '## Rules\nFollow best practices.',
  task_type: 'coding-implementation' as TaskType,
  agent_role: 'python-coder' as AgentRole,
  complexity: 'medium' as TaskComplexity,
  estimated_turns: 15,
  skip_planning: false,
  use_agentic_loop: false,
  confidence_assessment: {
    has_progress: true,
    score: 50,
    reasoning: 'Default',
  },
};

export async function shouldRespond(
  context: ShouldRespondContext,
  messageId: string
): Promise<ShouldRespondResult> {
  log.info(`shouldRespond call for message ${messageId}`);

  const template = loadTemplate('should_respond');
  const systemPrompt = renderTemplate(template, {
    author: context.author,
    force_respond: String(context.force_respond),
    history: context.history,
    message: context.message,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      {
        role: 'user',
        content: `Analyze the message and respond with JSON only.`,
      },
    ],
    metadata: {
      tags: ['tier2', 'general'],
    },
  });

  const content = extractContent(response);
  log.info(`shouldRespond raw response length: ${content.length}`);

  const parsed = extractJsonFromContent<ShouldRespondResult>(content);

  if (!parsed) {
    log.warn('Could not parse shouldRespond response, using defaults');
    return DEFAULT_SHOULD_RESPOND;
  }

  const result: ShouldRespondResult = {
    should_respond: parsed.should_respond === true,
    reason: parsed.reason || 'No reason given',
  };

  log.info(`shouldRespond result: should_respond=${result.should_respond}`);
  log.info(`shouldRespond reason: ${result.reason}`);

  return result;
}

export async function classifyRequest(
  context: ShouldRespondContext,
  messageId: string
): Promise<ClassifyRequestResult> {
  log.info(`classifyRequest call for message ${messageId}`);

  const template = loadTemplate('classify_request');
  const systemPrompt = renderTemplate(template, {
    author: context.author,
    force_respond: String(context.force_respond),
    history: context.history,
    message: context.message,
  });

  const response = await chatCompletion({
    model: 'auto',
    messages: [
      { role: 'system', content: systemPrompt },
      {
        role: 'user',
        content: `Classify this request and respond with JSON only.`,
      },
    ],
    metadata: {
      tags: ['tier1', 'classifier'],
    },
  });

  const content = extractContent(response);
  log.info(`classifyRequest raw response length: ${content.length}`);

  const parsed = extractJsonFromContent<ClassifyRequestResult>(content);

  if (!parsed) {
    log.warn('Could not parse classifyRequest response, using defaults');
    return DEFAULT_CLASSIFY_REQUEST;
  }

  // Validate flow_type
  const validFlowTypes = Object.values(FlowType);
  if (!validFlowTypes.includes(parsed.flow_type)) {
    log.warn(`Invalid flow_type: ${parsed.flow_type}, defaulting to SIMPLE`);
    parsed.flow_type = FlowType.SIMPLE;
  }

  // Validate starting_tier
  const validTiers = ['tier1', 'tier2', 'tier3', 'tier4'];
  if (!validTiers.includes(parsed.starting_tier)) {
    log.warn(`Invalid starting_tier: ${parsed.starting_tier}, defaulting to tier2`);
    parsed.starting_tier = 'tier2';
  }

  const result: ClassifyRequestResult = {
    flow_type: parsed.flow_type,
    starting_tier: parsed.starting_tier,
    websearch: parsed.websearch === true,
    agent_role: parsed.agent_role,
  };

  log.info(`classifyRequest result: flow_type=${result.flow_type}, starting_tier=${result.starting_tier}, websearch=${result.websearch}`);
  if (result.agent_role) {
    log.info(`classifyRequest agent_role: ${result.agent_role}`);
  }

  return result;
}

export async function generatePlan(
  context: PlanningContext,
  channelid: string
): Promise<PlanningResult> {
  log.info(`generatePlan for thread ${channelid}`);

  const template = loadTemplate('planning');
  const systemPrompt = renderTemplate(template, {
    channel_id: context.channel_id,
    branch_name: context.branch_name,
    sub_topics: context.sub_topics,
    history: context.history,
    message: context.message,
    attachments: context.attachments,
    user_added_files: context.user_added_files || '',
    previous_confidence: String(context.previous_confidence || 0),
  });

  const config = getConfig();
  const response = await chatCompletion({
    model: config.PLANNER_MODEL_ID,
    messages: [
      { role: 'system', content: systemPrompt },
      {
        role: 'user',
        content: 'Generate a plan and respond with JSON only.',
      },
    ],
  });

  const content = extractContent(response);
  log.info(`generatePlan raw response length: ${content.length}`);

  const parsed = extractJsonFromContent<PlanningResult>(content);

  if (!parsed) {
    log.warn('Could not parse planning response, using defaults');
    return {
      ...DEFAULT_PLANNING,
      reformulated_prompt: context.message,
    };
  }

  const taskType = parsed.task_type || ('coding-implementation' as TaskType);
  const agentRole = parsed.agent_role || ('python-coder' as AgentRole);
  const complexity = parsed.complexity || ('medium' as TaskComplexity);

  const result: PlanningResult = {
    reformulated_prompt: parsed.reformulated_prompt || context.message,
    topic_slug: parsed.topic_slug || 'general-task',
    is_new_topic: parsed.is_new_topic !== false,
    plan_content: parsed.plan_content || DEFAULT_PLANNING.plan_content,
    instruction_content: parsed.instruction_content || DEFAULT_PLANNING.instruction_content,
    task_type: taskType,
    agent_role: agentRole,
    complexity: complexity,
    estimated_turns: parsed.estimated_turns || 15,
    skip_planning: parsed.skip_planning === true,
    use_agentic_loop: shouldUseAgenticLoop(taskType),
    confidence_assessment: {
      has_progress: parsed.confidence_assessment?.has_progress !== false,
      score: parsed.confidence_assessment?.score ?? 50,
      reasoning: parsed.confidence_assessment?.reasoning || 'No reasoning provided',
    },
  };

  log.info(`generatePlan result: topic_slug=${result.topic_slug}, is_new_topic=${result.is_new_topic}`);
  log.info(`generatePlan task_type=${result.task_type}, agent_role=${result.agent_role}, complexity=${result.complexity}`);
  log.info(`generatePlan estimated_turns=${result.estimated_turns}, skip_planning=${result.skip_planning}, use_agentic_loop=${result.use_agentic_loop}`);
  log.info(`generatePlan confidence: score=${result.confidence_assessment.score}, has_progress=${result.confidence_assessment.has_progress}`);

  return result;
}

export async function generateThreadName(content: string): Promise<string> {
  log.info(`generateThreadName, input length: ${content.length}`);

  const template = loadTemplate('thread_name');

  const response = await chatCompletion({
    model: 'deepseek-v3.2-speciale',
    messages: [
      { role: 'system', content: template },
      { role: 'user', content: content.substring(0, 500) },
    ],
  });

  const name = extractContent(response).trim();
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .split(/\s+/)
    .slice(0, 4)
    .join('-')
    .substring(0, 100);

  const fallback = content
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .split(/\s+/)
    .slice(0, 4)
    .join('-')
    .substring(0, 100);

  log.info(`generateThreadName result: ${slug || fallback || name}`);

  return slug || fallback || name || content.substring(0, 50);
}
