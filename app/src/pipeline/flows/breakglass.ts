import { createLogger } from '../../utils/logger';
import { executeBreakglass } from '../execute';
import { getModelParams } from '../../modules/langgraph/temperature';
import { FlowType } from '../../modules/litellm/types';
import type { FlowContext, FlowResult } from './types';

const log = createLogger('FLOW:BREAKGLASS');

export async function executeBreakglassFlow(
  context: FlowContext,
  modelName: string
): Promise<FlowResult> {
  log.info('Phase: BREAKGLASS_FLOW');
  log.info(`Breakglass model: ${modelName}`);

  const params = getModelParams(FlowType.BREAKGLASS);
  log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

  const result = await executeBreakglass({
    channelId: context.channelId,
    modelName,
    history: context.history,
    modelParams: params,
  });

  return {
    response: result.response,
    model: result.model,
    responseChannelId: context.channelId,
  };
}
