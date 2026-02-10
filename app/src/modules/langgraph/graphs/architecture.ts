/**
 * ArchitectureGraph - Multi-Node Flow
 *
 * A multi-node graph for theoretical/design tasks.
 * Uses tag-based routing: tier4 + tools + programming
 *
 * Flow: start → plan → evaluate → finalize
 */

import { createLogger } from '../../../utils/logger';
import { setupSession } from '../../../pipeline/session';
import { createPlan } from '../../../pipeline/planning';
import { trajectoryEvaluator } from '../../reflexion/evaluator';
import { streamProgressToDiscord } from '../../agentic/progress';
import { addReflectionToHistory, addKeyInsight } from '../../reflexion/memory';
import { updateSession } from '../../../modules/dynamodb/sessions';
import { getModelParams } from '../temperature';
import { FlowType } from '../../litellm/types';
import { createExecutionLogger } from '../logger';
import { getMermaidGenerator } from '../mermaid';
import type { GraphResult, GraphInvokeOptions } from './types';

const log = createLogger('GRAPH:ARCHITECTURE');

// ============================================================================
// Graph Factory
// ============================================================================

export function createArchitectureGraph() {
  return {
    name: 'ArchitectureGraph',
    invoke: async (options: GraphInvokeOptions): Promise<GraphResult> => {
      log.info(`Invoking ArchitectureGraph for channel ${options.channelId}`);

      // Use tier4 + tools + programming tags
      const tags = options.tags || ['tier4', 'tools', 'programming'];

      const workspacePath = options.workspacePath || options.channelId;
      const logger = createExecutionLogger({
        channelId: options.channelId,
        executionId: options.executionId,
      });

      logger.recordNode('start');

      try {
        // Setup session
        logger.recordNode('plan');
        log.info('Setting up session');
        const sessionResult = await setupSession(workspacePath, options.channelId);
        const branchName = sessionResult.branchName;

        // Create plan with simplified history
        log.info('Creating architectural plan');
        const planning = await createPlan({
          channelId: workspacePath,
          branchName: sessionResult.branchName,
          session: sessionResult.session,
          history: {
            formatted_history: options.history?.formatted_history || '',
            current_message: options.initialPrompt,
            current_author: options.history?.current_author || 'User',
            current_attachments: {
              images: [],
              textFiles: [],
              otherFiles: [],
            },
            poll_entries: [],
          },
          processedAttachments: [],
          userAddedFilesMessage: '',
          previousConfidence: sessionResult.session.confidence_score,
        });

        log.info('Architecture plan generated');

        // Evaluate plan
        logger.recordNode('evaluate');
        const mockTurns = [{
          turnNumber: 1,
          input: planning.reformulated_prompt,
          toolCalls: [],
          toolResults: [],
          response: planning.plan_content + '\n\n' + planning.instruction_content,
          thinking: planning.plan_content,
          confidence: planning.confidence_assessment.score,
          status: 'complete' as const,
          modelUsed: 'opus-planner',
        }];

        const evaluation = await trajectoryEvaluator.evaluateArchitectureTrajectory(
          mockTurns,
          planning.reformulated_prompt,
          planning.estimated_turns
        );

        log.info(`Architecture evaluation: score=${evaluation.score}`);

        // Build reflection
        const reflection = {
          timestamp: new Date().toISOString(),
          score: evaluation.score,
          what_worked: planning.reflection?.what_worked || 'N/A',
          what_failed: planning.reflection?.what_failed || 'N/A',
          root_cause: planning.reflection?.root_cause || 'N/A',
          strategy_change: planning.reflection?.strategy_change || 'N/A',
          key_insight: planning.reflection?.key_insight || 'N/A',
        };

        // Update session
        await updateSession(workspacePath, {
          reflections: addReflectionToHistory(
            sessionResult.session.reflections,
            reflection
          ),
          key_insights: addKeyInsight(
            sessionResult.session.key_insights,
            reflection.key_insight
          ),
          confidence_score: evaluation.score,
          last_trajectory_summary: `Architecture plan for ${planning.topic_slug}: ${planning.plan_content.substring(0, 100)}...`,
        });

        // Stream completion
        await streamProgressToDiscord(workspacePath, {
          type: 'reflection',
          checkpointData: {
            score: evaluation.score,
            hasProgress: evaluation.has_progress,
            keyInsight: reflection.key_insight,
          },
        });

        // Construct final response
        const finalResponse = `# ${planning.topic_slug}\n\n` +
          `**Task Type:** ${planning.task_type}\n` +
          `**Agent Role:** ${planning.agent_role}\n` +
          `**Complexity:** ${planning.complexity}\n` +
          `**Confidence:** ${evaluation.score}%\n\n` +
          `---\n\n` +
          `${planning.plan_content}\n\n` +
          `---\n\n` +
          `${planning.instruction_content}\n\n` +
          `---\n\n` +
          `*To implement this plan, say "implement this" or ask me to execute a specific part.*`;

        logger.recordNode('finalize');

        // Generate Mermaid diagram
        const generator = getMermaidGenerator();
        const mermaidSource = generator.generate({
          flowType: FlowType.ARCHITECTURE,
          traversedNodes: ['start', 'plan', 'evaluate', 'finalize'],
          turns: [],
          finalStatus: 'complete',
        });

        await logger.uploadMermaid(mermaidSource);

        // Try to render PNG, but don't let it fail the whole request
        try {
          const mermaidPng = await generator.renderPng(mermaidSource);
          await logger.uploadDiagramPng(mermaidPng);
        } catch (diagramError) {
          log.warn(`Failed to render Mermaid diagram: ${diagramError}`);
          // Continue - diagram is optional, user still gets their response
        }

        // Upload metadata
        const metadata = {
          flowType: FlowType.ARCHITECTURE,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'complete',
          nodeCount: 4,
          model: 'planning-model',
          tags,
          topicSlug: planning.topic_slug,
          confidenceScore: evaluation.score,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: finalResponse,
          model: 'architecture-planner',
          traversedNodes: ['start', 'plan', 'evaluate', 'finalize'],
        };
      } catch (error) {
        log.error(`ArchitectureGraph error: ${error}`);

        const metadata = {
          flowType: FlowType.ARCHITECTURE,
          channelId: options.channelId,
          executionId: options.executionId,
          status: 'error',
          error: String(error),
          tags,
          timestamp: new Date().toISOString(),
        };

        await logger.uploadMetadata(metadata);
        await logger.flush();

        return {
          response: `Error: ${error instanceof Error ? error.message : String(error)}`,
          model: '',
          traversedNodes: ['start', 'plan', 'evaluate', 'finalize'],
          error: String(error),
        };
      }
    },
  };
}

// Export singleton
export const architectureGraph = createArchitectureGraph();
