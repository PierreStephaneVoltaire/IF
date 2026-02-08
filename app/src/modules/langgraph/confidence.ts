import type { ExecutionState, ExecutionTurn } from '../litellm/types';

export function calculateConfidence(state: ExecutionState, turn: ExecutionTurn): number {
  let score = turn.confidence ?? 70;

  if (state.sameErrorCount >= 2) score -= 15;
  if (state.noProgressTurns >= 3) score -= 15;
  if (state.errorCount >= 2) score -= 10;

  return Math.max(0, Math.min(100, score));
}

export function getConfidenceLevel(score: number): 'critical' | 'low' | 'moderate' | 'high' {
  if (score < 50) return 'critical';  // was 30
  if (score < 65) return 'low';       // was 50
  if (score < 80) return 'moderate';  // was 70
  return 'high';
}
