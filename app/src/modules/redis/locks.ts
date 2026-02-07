import type { RedisClientType } from 'redis';
import { getRedisClient, withRedisFallback } from './index';
import { createLogger } from '../../utils/logger';
const inMemoryLocks = new Set<string>();
const inMemoryAborts = new Set<string>();

const log = createLogger('REDIS:LOCKS');

const LOCK_TTL_SECONDS = 300; // 5 minutes
const LOCK_KEY_PREFIX = 'lock:';

/**
 * Acquire a distributed lock for a thread
 * Uses Redis SET NX for atomic acquisition with TTL
 * Falls back to in-memory lock if Redis unavailable
 */
export async function acquireLock(
  channelId: string,
  executionId: string
): Promise<boolean> {
  return withRedisFallback(
    async (client) => {
      const lockKey = `${LOCK_KEY_PREFIX}${channelId}`;

      // Atomic SET with NX (only if not exists) and EX (TTL)
      const result = await client.set(lockKey, executionId, {
        NX: true,
        EX: LOCK_TTL_SECONDS,
      });

      const acquired = result === 'OK';

      if (acquired) {
        log.info(`Lock acquired for channel ${channelId}`, { executionId });
      } else {
        log.debug(`Lock not acquired for channel ${channelId} - already locked`);
      }

      return acquired;
    },
    async () => {
      // Fallback: check in-memory lock
      if (inMemoryLocks.has(channelId)) {
        log.debug(`In-memory lock exists for channel ${channelId}`);
        return false;
      }

      // Create in-memory lock
      inMemoryLocks.add(channelId);
      log.info(`In-memory lock created for channel ${channelId}`, { executionId });
      return true;
    },
    'acquireLock'
  );
}

/**
 * Release a distributed lock
 */
export async function releaseLock(channelId: string): Promise<void> {
  const client = await getRedisClient();

  if (client) {
    try {
      const lockKey = `${LOCK_KEY_PREFIX}${channelId}`;
      await client.del(lockKey);
      log.info(`Redis lock released for channel ${channelId}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      log.error(`Failed to release Redis lock for ${channelId}`, { error: errorMessage });
    }
  }

  // Always release in-memory lock for consistency
  inMemoryLocks.delete(channelId);
}

/**
 * Refresh the TTL on an existing lock
 * Only refreshes if we still own the lock
 */
export async function refreshLock(
  channelId: string,
  executionId: string
): Promise<boolean> {
  const client = await getRedisClient();

  if (!client) {
    // In-memory locks don't need refresh
    return inMemoryLocks.has(channelId);
  }

  try {
    const lockKey = `${LOCK_KEY_PREFIX}${channelId}`;

    // Check if we still own the lock
    const currentOwner = await client.get(lockKey);

    if (currentOwner !== executionId) {
      log.warn(`Lock ownership changed for channel ${channelId}`, {
        expected: executionId,
        actual: currentOwner,
      });
      return false;
    }

    // Refresh TTL
    await client.expire(lockKey, LOCK_TTL_SECONDS);
    log.debug(`Lock refreshed for channel ${channelId}`);
    return true;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    log.error(`Failed to refresh lock for ${channelId}`, { error: errorMessage });
    return false;
  }
}

/**
 * Check if a lock exists for a thread
 */
export async function checkLock(channelId: string): Promise<string | null> {
  const client = await getRedisClient();

  if (client) {
    try {
      const lockKey = `${LOCK_KEY_PREFIX}${channelId}`;
      return await client.get(lockKey);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      log.error(`Failed to check lock for ${channelId}`, { error: errorMessage });
    }
  }

  // Fallback to in-memory
  return inMemoryLocks.has(channelId) ? 'in-memory' : null;
}

/**
 * Set abort flag on a lock
 */
export async function setAbortFlag(channelId: string): Promise<void> {
  const client = await getRedisClient();

  if (client) {
    try {
      const abortKey = `abort:${channelId}`;
      await client.set(abortKey, '1', { EX: 600 }); // 10 minute TTL
      log.info(`Abort flag set in Redis for channel ${channelId}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      log.error(`Failed to set abort flag in Redis for ${channelId}`, { error: errorMessage });
    }
  }

  // Always set in-memory abort for immediate effect
  inMemoryAborts.add(channelId);
}

/**
 * Check if abort flag is set
 */
export async function checkAbortFlag(channelId: string): Promise<boolean> {
  const client = await getRedisClient();

  if (client) {
    try {
      const abortKey = `abort:${channelId}`;
      const flag = await client.get(abortKey);
      return flag === '1';
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      log.error(`Failed to check abort flag for ${channelId}`, { error: errorMessage });
    }
  }

  // Fallback to in-memory
  return inMemoryAborts.has(channelId);
}

/**
 * Clear abort flag
 */
export async function clearAbortFlag(channelId: string): Promise<void> {
  const client = await getRedisClient();

  if (client) {
    try {
      const abortKey = `abort:${channelId}`;
      await client.del(abortKey);
      log.debug(`Abort flag cleared in Redis for channel ${channelId}`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      log.error(`Failed to clear abort flag for ${channelId}`, { error: errorMessage });
    }
  }
}
