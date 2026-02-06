import { createLogger } from '../../utils/logger';

const log = createLogger('AGENTIC:LOCK');

export interface ExecutionLock {
  channelId: string;
  abort: boolean;
  currentTurn: number;
  startedAt: Date;
}

// In-memory store of active execution locks
// In production, this could be backed by Redis for distributed scenarios
const executionLocks = new Map<string, ExecutionLock>();

/**
 * Creates a new execution lock for a thread
 */
export function createLock(channelId: string): ExecutionLock {
  const lock: ExecutionLock = {
    channelId,
    abort: false,
    currentTurn: 0,
    startedAt: new Date(),
  };
  
  executionLocks.set(channelId, lock);
  log.info(`Created execution lock for channel ${channelId}`);
  
  return lock;
}

/**
 * Gets an existing lock for a thread
 */
export function getLock(channelId: string): ExecutionLock | undefined {
  return executionLocks.get(channelId);
}

/**
 * Checks if a thread has an active lock
 */
export function hasActiveLock(channelId: string): boolean {
  return executionLocks.has(channelId);
}

/**
 * Updates the current turn for a lock
 */
export function updateLockTurn(channelId: string, turn: number): void {
  const lock = executionLocks.get(channelId);
  if (lock) {
    lock.currentTurn = turn;
  }
}

/**
 * Sets the abort flag on a lock
 */
export function abortLock(channelId: string): void {
  const lock = executionLocks.get(channelId);
  if (lock) {
    lock.abort = true;
    log.warn(`Abort flag set for channel ${channelId}`);
  }
}

/**
 * Releases a lock
 */
export function releaseLock(channelId: string): void {
  const lock = executionLocks.get(channelId);
  if (lock) {
    const duration = Date.now() - lock.startedAt.getTime();
    log.info(`Released execution lock for channel ${channelId} (duration: ${duration}ms, turns: ${lock.currentTurn})`);
    executionLocks.delete(channelId);
  }
}

/**
 * Gets all active locks (for debugging)
 */
export function getAllLocks(): ExecutionLock[] {
  return Array.from(executionLocks.values());
}

/**
 * Checks if a lock has been aborted
 */
export function isAborted(channelId: string): boolean {
  const lock = executionLocks.get(channelId);
  return lock?.abort ?? false;
}
