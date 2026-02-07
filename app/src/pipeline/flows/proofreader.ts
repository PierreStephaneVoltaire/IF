import { createLogger } from '../../utils/logger';
import { chatCompletion } from '../../modules/litellm/index';
import { getModelFromTier } from '../../templates/registry';
import { loadPrompt } from '../../templates/loader';
import { getModelParams } from '../../modules/langgraph/temperature';
import { FlowType } from '../../modules/litellm/types';
import type { FlowContext, FlowResult } from './types';

const log = createLogger('FLOW:PROOFREADER');

/**
 * Proofreader Flow
 *
 * For grammar and spellcheck only.
 * - Always uses Tier 1 models (cheapest, fastest)
 * - ONLY fixes grammar and spelling
 * - NEVER alters the intent, tone, or style unless explicitly requested
 * - Preserves the user's voice and message meaning
 */
export async function executeProofreaderFlow(
  context: FlowContext
): Promise<FlowResult> {
  log.info('Phase: PROOFREADER_FLOW');

  // Always use tier 1 model for proofreading
  const model = getModelFromTier('tier1', 0);
  log.info(`Using tier 1 model for proofreading: ${model}`);

  // Load prompt from template file
  const systemPrompt = loadPrompt('proofreader');

  const params = getModelParams(FlowType.PROOFREADER);
  log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

  const response = await chatCompletion({
    model,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: context.history.current_message },
    ],
    temperature: params.temperature,
    top_p: params.top_p,
  });

  const content = response.choices?.[0]?.message?.content || 'No errors found.';

  return {
    response: content,
    model,
    responseChannelId: context.channelId,
  };
}
