/**
 * DialecticGraph - Parallel Flow
 *
 * A parallel graph for philosophical exploration.
 * - Thesis → Antithesis → Synthesis
 * - 2 tier2 models for thesis/antithesis
 * - 1 tier4 synthesizer
 *
 * Flow: start → thesis → antithesis → synthesize → finalize
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

const log = createLogger('GRAPH:DIALECTIC');

// ============================================================================
// Helper Functions
// ============================================================================

function getRandomModelsFromTier(tier: keyof typeof MODEL_TIERS, count: number): string[] {
  const tierModels = [...MODEL_TIERS[tier]];
  // Shuffle array
  for (let i = tierModels.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [tierModels[i], tierModels[j]] = [tierModels[j], tierModels[i]];
  }
  return tierModels.slice(0, Math.min(count, tierModels.length));
}

function getRandomModelFromTier(tier: keyof typeof MODEL_TIERS): string {
  const tierModels = MODEL_TIERS[tier];
  const randomIndex = Math.floor(Math.random() * tierModels.length);
  return tierModels[randomIndex];
}

// ============================================================================
// Graph State
// ============================================================================

interface DialecticGraphState {
  channelId: string;
  executionId: string;
  flowType: FlowType;
  userQuestion: string;
  thesisModel: string;
  antithesisModel: string;
  synthesizerModel: string;
  thesis: string;
  antithesis: string;
  synthesis: string;
  status: 'running' | 'complete' | 'error';
  traversedNodes: string[];
}

// ============================================================================
// Node Functions
// ============================================================================

async function thesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('start');
  logger.recordNode('thesis');

  log.info(`DialecticGraph: Generating thesis for channel ${state.channelId}`);

  const params = getModelParams(state.flowType);

  const thesisPrompt = `You are a philosopher presenting the strongest possible THESIS on the following question.

## User's Question
"${state.userQuestion}"

## Your Task
Present the strongest, most compelling THESIS (one philosophical position) on this question.

## Guidelines
- Present the strongest case for ONE coherent philosophical position
- Use rigorous reasoning and clear argumentation
- Acknowledge complexities but defend your position firmly
- This is the "thesis" that will be countered by an antithesis

## Format
1. **Position Statement**: Clear statement of your philosophical position (2-3 sentences)
2. **Core Arguments**: 3-5 key arguments supporting this position
3. **Underlying Assumptions**: What assumptions does this position rest on?
4. **Philosophical Tradition**: What school of thought does this represent?`;

  const response = await chatCompletion({
    model: state.thesisModel,
    messages: [{ role: 'user', content: thesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const thesis = extractContent(response);
  log.info(`Thesis generated: ${thesis.length} chars`);

  return {
    ...state,
    thesis,
    traversedNodes: ['start', 'thesis'],
  };
}

async function antithesisNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({ channelId: state.channelId, executionId: state.executionId });
  logger.recordNode('antithesis');

  log.info(`DialecticGraph: Generating antithesis`);

  const params = getModelParams(state.flowType);

  const antithesisPrompt = `You are a philosopher presenting the strongest possible ANTITHESIS to the following thesis.

## User's Original Question
"${state.userQuestion}"

## The Thesis You Must Counter
${state.thesis}

## Your Task
Present the strongest, most compelling ANTITHESIS (opposing philosophical position) to the thesis above.

## Guidelines
- This must be a genuine philosophical counter-position, not just nitpicking
- Attack the core assumptions and reasoning of the thesis
- Present an alternative framework that leads to different conclusions
- Be rigorous and persuasive

## Format
1. **Counter-Position Statement**: Clear statement of your opposing position (2-3 sentences)
2. **Critique of Thesis**: What are the fundamental flaws in the thesis?
3. **Alternative Arguments**: 3-5 key arguments for your counter-position`;

  const response = await chatCompletion({
    model: state.antithesisModel,
    messages: [{ role: 'user', content: antithesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const antithesis = extractContent(response);
  log.info(`Antithesis generated: ${antithesis.length} chars`);

  return {
    ...state,
    antithesis,
    traversedNodes: [...state.traversedNodes, 'antithesis'],
  };
}

async function synthesizeNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({ channelId: state.channelId, executionId: state.executionId });
  logger.recordNode('synthesize');

  log.info(`DialecticGraph: Generating synthesis`);

  const params = getModelParams(state.flowType);

  const synthesisPrompt = `You are a master philosopher tasked with synthesizing a thesis and antithesis into a higher-order understanding.

## User's Original Question
"${state.userQuestion}"

## The Thesis
${state.thesis}

## The Antithesis
${state.antithesis}

## Your Task
Create a SYNTHESIS that transcends both the thesis and antithesis.

## Guidelines
- Do not simply compromise or average the two positions
- Find a higher-order framework that incorporates the valid insights from both
- Show how the apparent contradiction can be resolved or reframed

## Format
1. **Summary of Positions**: Brief summary of both positions
2. **Key Tension**: What is the fundamental tension between these positions?
3. **The Synthesis**: Your higher-order resolution (3-5 paragraphs)
4. **Remaining Questions**: What aspects remain unresolved?`;

  const response = await chatCompletion({
    model: state.synthesizerModel,
    messages: [{ role: 'user', content: synthesisPrompt }],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const synthesis = extractContent(response);
  log.info(`Synthesis generated: ${synthesis.length} chars`);

  return {
    ...state,
    synthesis,
    traversedNodes: [...state.traversedNodes, 'synthesize'],
  };
}

async function finalizeNode(state: DialecticGraphState): Promise<DialecticGraphState> {
  const logger = createExecutionLogger({
    channelId: state.channelId,
    executionId: state.executionId,
  });

  logger.recordNode('finalize');

  // Generate Mermaid diagram
  const generator = getMermaidGenerator();
  const mermaidSource = generator.generate({
    flowType: state.flowType,
    traversedNodes: ['start', 'thesis', 'antithesis', 'synthesize', 'finalize'],
    turns: [],
    finalStatus: 'complete',
  });

  await logger.uploadMermaid(mermaidSource);

  const metadata = {
    flowType: state.flowType,
    channelId: state.channelId,
    executionId: state.executionId,
    status: 'complete',
    nodeCount: 5,
    thesisModel: state.thesisModel,
    antithesisModel: state.antithesisModel,
    synthesizerModel: state.synthesizerModel,
    timestamp: new Date().toISOString(),
  };

  await logger.uploadMetadata(metadata);
  await logger.flush();

  return {
    ...state,
    traversedNodes: [...state.traversedNodes, 'finalize'],
  };
}

// ============================================================================
// Graph Factory
// ============================================================================

export function createDialecticGraph() {
  return {
    name: 'DialecticGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking DialecticGraph for channel ${options.channelId}`);

      // Select models
      const [thesisModel, antithesisModel] = getRandomModelsFromTier('tier2', 2);
      const synthesizerModel = getRandomModelFromTier('tier4');

      log.info(`Using thesis model: ${thesisModel}`);
      log.info(`Using antithesis model: ${antithesisModel}`);
      log.info(`Using synthesizer model: ${synthesizerModel}`);

      let state: DialecticGraphState = {
        channelId: options.channelId,
        executionId: options.executionId,
        flowType: FlowType.DIALECTIC,
        userQuestion: options.initialPrompt,
        thesisModel,
        antithesisModel,
        synthesizerModel,
        thesis: '',
        antithesis: '',
        synthesis: '',
        status: 'running',
        traversedNodes: [],
      };

      // Execute sequential nodes
      state = await thesisNode(state);
      state = await antithesisNode(state);
      state = await synthesizeNode(state);
      state = await finalizeNode(state);

      return {
        response: state.synthesis,
        model: state.synthesizerModel,
        traversedNodes: state.traversedNodes,
        error: state.status === 'error' ? state.synthesis : undefined,
      };
    },
  };
}

// Export singleton
export const dialecticGraph = createDialecticGraph();
