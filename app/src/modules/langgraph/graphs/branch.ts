/**
 * BranchGraph - Parallel Flow
 *
 * A parallel graph for exploring multiple architectural approaches.
 * - 3 random tier3 models for brainstorming
 * - 1 tier4 aggregator model for poll creation
 * - Creates Discord poll for user selection
 *
 * Flow: start → branch_1 → branch_2 → branch_3 → aggregate → finalize
 *
 * @see plans/langgraph-migration-plan.md
 */

import { createLogger } from '../../../utils/logger';
import { MODEL_TIERS } from '../../agentic/escalation';
import { chatCompletion, extractContent } from '../../litellm/index';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:BRANCH');

// ============================================================================
// Helper Functions
// ============================================================================

function getRandomTier3Models(): string[] {
  const tier3Models = [...MODEL_TIERS.tier3];
  // Shuffle array
  for (let i = tier3Models.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [tier3Models[i], tier3Models[j]] = [tier3Models[j], tier3Models[i]];
  }
  // Return first 3 (or all if less than 3)
  return tier3Models.slice(0, 3);
}

function getRandomTier4Model(): string {
  const tier4Models = MODEL_TIERS.tier4;
  const randomIndex = Math.floor(Math.random() * tier4Models.length);
  return tier4Models[randomIndex];
}

// ============================================================================
// Graph State
// ============================================================================

interface BranchGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  branchModels: string[];
  aggregatorModel: string;
  responses: string[];
  finalResponse: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

/**
 * Branch nodes - parallel exploration by multiple models
 */
async function branchNodes(state: BranchGraphState): Promise<BranchGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');

  log.info(`BranchGraph: Starting execution for channel ${state.channelId}`);

  try {
    // Select models
    const branchModels = getRandomTier3Models();
    const aggregatorModel = getRandomTier4Model();

    log.info(`Using tier3 models: ${branchModels.join(', ')}`);
    log.info(`Using tier4 aggregator: ${aggregatorModel}`);

    // Get temperature params
    const params = getModelParams(state.flowType);
    log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

    // Brainstorming prompt
    const brainstormingPrompt = `
You are an expert architect and technical strategist exploring multiple solutions to a problem.

## Objective
${state.userQuestion}

## Your Task
Suggest **3 distinct architectural approaches** to achieve this goal.

## CRITICAL RULES
- **NO CODE**: Do not write any code, code blocks, or implementation snippets.
- **THEORY ONLY**: Focus exclusively on theory, architecture, strategy, and high-level design.
- **Think Step-by-Step**: Explain your reasoning for why each approach works.
- **Be Distinct**: Each approach should be fundamentally different from the others.

## Format for Each Approach
1. **Title**: Clear name for the approach
2. **Overview**: 2-3 sentence description
3. **Rationale**: Why this approach makes sense (step-by-step reasoning)
4. **Architecture**: High-level components and how they interact (describe, don't diagram)
5. **Pros**: 3-5 bullet points
6. **Cons**: 3-5 bullet points
7. **Best For**: When this approach is the right choice

Keep each approach concise but thorough. Focus on the "what" and "why", not the "how to code it".
    `.trim();

    // Record branch nodes
    logger.recordNode('branch_1');
    logger.recordNode('branch_2');
    logger.recordNode('branch_3');

    // Execute branches in parallel
    const [response1, response2, response3] = await Promise.all([
      chatCompletion({
        model: branchModels[0],
        messages: [{ role: 'user', content: brainstormingPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
      chatCompletion({
        model: branchModels[1],
        messages: [{ role: 'user', content: brainstormingPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
      chatCompletion({
        model: branchModels[2],
        messages: [{ role: 'user', content: brainstormingPrompt }],
        temperature: params.temperature,
        top_p: params.top_p,
      }),
    ]);

    const content1 = extractContent(response1);
    const content2 = extractContent(response2);
    const content3 = extractContent(response3);

    log.info(`Branch responses generated: ${content1.length}, ${content2.length}, ${content3.length} chars`);

    // Record aggregate node
    logger.recordNode('aggregate');

    // Aggregator prompt
    const aggregatorPrompt = `
You are consolidating multiple architectural approaches into a poll.

## User's Original Question
"${state.userQuestion}"

## Input Approaches

### Model 1 (${branchModels[0]}) Approaches:
${content1}

### Model 2 (${branchModels[1]}) Approaches:
${content2}

### Model 3 (${branchModels[2]}) Approaches:
${content3}

## Your Task
Analyze these approaches and create a poll with 3 distinct options.

## Output Format (JSON)
{
  "question": "Which architectural approach best addresses your needs?",
  "options": [
    {"id": "A", "label": "Approach Name", "description": "Brief description of this approach"}
  ]
}

Provide exactly 3 options representing the best approaches from all models.
    `.trim();

    // Execute aggregator
    const aggregatorResponse = await chatCompletion({
      model: aggregatorModel,
      messages: [{ role: 'user', content: aggregatorPrompt }],
      temperature: params.temperature,
      top_p: params.top_p,
    });

    const aggregatorContent = extractContent(aggregatorResponse);
    log.info(`Aggregator response generated: ${aggregatorContent.length} chars`);

    // Generate Mermaid diagram
    const generator = getMermaidGenerator();
    const mermaidSource = generator.generate({
      flowType: state.flowType,
      traversedNodes: ['start', 'branch_1', 'branch_2', 'branch_3', 'aggregate'],
      turns: [],
      finalStatus: 'complete',
    });

    await logger.uploadMermaid(mermaidSource);

    // Upload metadata
    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'complete',
      nodeCount: 5,
      branchModels,
      aggregatorModel,
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);

    // Flush logs
    await logger.flush();

    return {
      ...state,
      branchModels,
      aggregatorModel,
      responses: [content1, content2, content3],
      finalResponse: aggregatorContent,
      status: 'complete',
      traversedNodes: ['start', 'branch_1', 'branch_2', 'branch_3', 'aggregate'],
    };
  } catch (error) {
    log.error(`BranchGraph error: ${error}`);

    const metadata = {
      flowType: state.flowType,
      channelId: state.channelId,
      executionId: state.executionId,
      status: 'error',
      error: String(error),
      timestamp: new Date().toISOString(),
    };

    await logger.uploadMetadata(metadata);
    await logger.flush();

    return {
      ...state,
      status: 'error',
      finalResponse: `Error: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createBranchGraph() {
  return {
    name: 'BranchGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking BranchGraph for channel ${options.channelId}`);

      const initialState: BranchGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.BRANCH,
        userQuestion: options.initialPrompt,
        branchModels: [],
        aggregatorModel: '',
        responses: [],
        finalResponse: '',
        status: 'running',
        traversedNodes: [],
      };

      const finalState = await branchNodes(initialState);

      return {
        response: finalState.finalResponse,
        model: finalState.aggregatorModel,
        traversedNodes: finalState.traversedNodes,
        error: finalState.status === 'error' ? finalState.finalResponse : undefined,
      };
    },
  };
}

// Export singleton
export const branchGraph = createBranchGraph();
