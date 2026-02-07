import { createLogger } from '../../utils/logger';
import { executeSimple } from '../execute';
import { getModelParams } from '../../modules/langgraph/temperature';
import { FlowType } from '../../modules/litellm/types';
import type { TaskType } from '../../modules/litellm/types';
import type { FlowContext, FlowResult } from './types';

const log = createLogger('FLOW:SIMPLE');

export async function executeSimpleFlow(
  context: FlowContext,
  taskType: TaskType
): Promise<FlowResult> {
  log.info('Phase: SIMPLE_FLOW');

  const params = getModelParams(FlowType.SIMPLE);
  log.info(`Temperature: ${params.temperature}, top_p: ${params.top_p}`);

  const result = await executeSimple({
    channelId: context.channelId,
    history: context.history,
    isTechnical: false,
    taskType,
    modelParams: params,
  });

  return {
    response: result.response,
    model: result.model,
    responseChannelId: context.channelId,
  };
}
