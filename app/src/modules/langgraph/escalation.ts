import type { ExecutionState, ExecutionTurn } from '../litellm/types';
import { MODEL_CAPABILITY_ORDER, getNextModel, isAtMaxEscalation } from './model-tiers';

export interface EscalationDecision {
  shouldEscalate: boolean;
  suggestedModel?: string;
  reason: string;
}

export function checkEscalationTriggers(
  state: ExecutionState,
  turn: ExecutionTurn,
  currentModel: string,
  consecutiveLowConfidenceTurns: number
): EscalationDecision {
  if (isAtMaxEscalation(currentModel)) {
    return { shouldEscalate: false, reason: 'Already at max model tier' };
  }

  if (consecutiveLowConfidenceTurns >= 2) {
    return { shouldEscalate: true, suggestedModel: getNextModel(currentModel) || undefined, reason: 'Low confidence' };
  }

  if (state.sameErrorCount >= 3) {
    return { shouldEscalate: true, suggestedModel: getNextModel(currentModel) || undefined, reason: 'Repeated errors' };
  }

  if (state.noProgressTurns >= 5) {
    return { shouldEscalate: true, suggestedModel: getNextModel(currentModel) || undefined, reason: 'No progress' };
  }

  if (turn.status === 'stuck') {
    return { shouldEscalate: true, suggestedModel: getNextModel(currentModel) || undefined, reason: 'Model reported stuck' };
  }

  return { shouldEscalate: false, reason: 'No escalation triggers hit' };
}

export { MODEL_CAPABILITY_ORDER, getNextModel, isAtMaxEscalation };
