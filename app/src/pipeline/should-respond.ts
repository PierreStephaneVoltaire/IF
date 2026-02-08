import { shouldRespond as opusShouldRespond } from '../modules/litellm/opus';
import { streamProgressToDiscord } from '../modules/agentic/progress';
import { createLogger } from '../utils/logger';
import type { FilterContext, FormattedHistory } from './types';

const log = createLogger('SHOULD_RESPOND');

export interface ShouldRespondInput {
  filter: FilterContext;
  history: FormattedHistory;
  messageId: string;
}

export interface ShouldRespondOutput {
  should_respond: boolean;
  reason: string;
}

export async function checkShouldRespond(
  input: ShouldRespondInput
): Promise<ShouldRespondOutput> {
  log.info(`Checking if bot should respond`);
  log.info(`Force respond: ${input.filter.force_respond}`);

  // Bypass for breakglass flow
  if (input.filter.is_breakglass) {
    log.info(`Breakglass flow detected: model=${input.filter.breakglass_model}`);
    return {
      should_respond: true,
      reason: `Breakglass invocation with @${input.filter.breakglass_model}`,
    };
  }

  if (input.filter.force_respond) {
    const reason = input.filter.is_mentioned
      ? 'User @mentioned the bot'
      : 'Forced response';
    log.info(`Force respond triggered: ${reason}`);

    return {
      should_respond: true,
      reason,
    };
  }

  log.info('Calling Opus for decision');

  // Show progress in Discord
  await streamProgressToDiscord(input.messageId, {
    type: 'should_respond',
    model: 'kimi-k2.5',
    phase: 'deciding'
  });

  const opusResult = await opusShouldRespond(
    {
      author: input.history.current_author,
      force_respond: input.filter.force_respond,
      history: input.history.formatted_history,
      message: input.history.current_message,
    },
    input.messageId
  );

  log.info(`Opus raw result: should_respond=${opusResult.should_respond}`);
  log.info(`Opus reason: ${opusResult.reason}`);

  log.info(`Final decision: should_respond=${opusResult.should_respond}, reason=${opusResult.reason}`);

  return {
    should_respond: opusResult.should_respond,
    reason: opusResult.reason,
  };
}
