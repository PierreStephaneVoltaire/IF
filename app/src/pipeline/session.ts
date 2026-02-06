import { getOrCreateSession, updateSession } from '../modules/dynamodb/sessions';
import { createLogger } from '../utils/logger';
import type { Session, SessionUpdate, SubTopic } from '../modules/dynamodb/types';
import type { PlanningResult } from '../modules/litellm/types';

const log = createLogger('SESSION');

export async function setupSession(
  workspaceId: string | null,
  channelId: string
): Promise<{ session: Session; branchName: string; isNew: boolean }> {
  const effectiveId = workspaceId || channelId;
  log.info(`Looking up session for channel ${effectiveId}`);

  const branchName = `channel-${effectiveId}`;
  log.info(`Branch name: ${branchName}`);

  const existingSession = await getOrCreateSession(effectiveId, branchName);
  const isNew = existingSession.created_at === existingSession.last_discord_timestamp;

  log.info(`Session exists: ${!isNew}`);
  log.info(`Existing sub_topics: ${Object.keys(existingSession.sub_topics || {}).length}`);

  return {
    session: existingSession,
    branchName,
    isNew,
  };
}

export async function updateSessionAfterExecution(
  channelId: string,
  planning: PlanningResult | null,
  currentMessage: string,
  timestamp: string,
  currentSession?: Session
): Promise<void> {
  log.info(`Updating session after execution: ${channelId}`);

  const updates: SessionUpdate = {
    last_discord_timestamp: timestamp,
    last_message: currentMessage.substring(0, 500),
  };

  if (planning) {
    updates.has_progress = planning.confidence_assessment.has_progress;
    updates.confidence_score = planning.confidence_assessment.score;

    if (planning.topic_slug) {
      log.info(`Updating sub_topics with: ${planning.topic_slug}`);
      
      const subTopics = currentSession?.sub_topics || {};
      subTopics[planning.topic_slug] = {
        plan_file: `plans/${planning.topic_slug}.md`,
        instruction_file: `instructions/${planning.topic_slug}.md`,
        status: 'in_progress',
      };
      
      updates.sub_topics = subTopics;
    }
  }

  await updateSession(channelId, updates);
  log.info('Session updated successfully');
}
