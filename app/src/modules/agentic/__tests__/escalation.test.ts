import { checkEscalationTriggers, getNextModel, isAtMaxEscalation } from '../../langgraph/escalation';
import { ExecutionState, ExecutionTurn } from '../../litellm/types';

describe('Escalation Logic', () => {
  const createMockState = (overrides?: Partial<ExecutionState>): ExecutionState => ({
    turnNumber: 5,
    confidenceScore: 50,
    lastError: null,
    errorCount: 0,
    sameErrorCount: 0,
    fileChanges: [],
    testResults: [],
    userInterrupts: [],
    userCorrectionCount: 0,
    noProgressTurns: 0,
    escalations: [],
    ...overrides,
  });

  const createMockTurn = (overrides?: Partial<ExecutionTurn>): ExecutionTurn => ({
    turnNumber: 5,
    input: 'test',
    toolCalls: [],
    toolResults: [],
    response: 'test response',
    confidence: 50,
    status: 'continue',
    modelUsed: 'gemini-3-pro',
    ...overrides,
  });

  test('should escalate on low confidence for 2 consecutive turns', () => {
    const state = createMockState({ confidenceScore: 25 });
    const turn = createMockTurn({ confidence: 25 });
    
    const result = checkEscalationTriggers(state, turn, ['tier2', 'tools', 'programming'], 2);
    
    expect(result.shouldEscalate).toBe(true);
    expect(result.reason).toContain('Low confidence');
    expect(result.suggestedTags).toEqual(['tier3', 'tools', 'programming']);
  });

  test('should escalate on same error repeated 3 times', () => {
    const state = createMockState({ sameErrorCount: 3 });
    const turn = createMockTurn();
    
    const result = checkEscalationTriggers(state, turn, ['tier2', 'tools', 'programming'], 0);
    
    expect(result.shouldEscalate).toBe(true);
    expect(result.reason).toContain('Same error repeated');
  });

  test('should escalate on no progress for 5 turns', () => {
    const state = createMockState({ noProgressTurns: 5 });
    const turn = createMockTurn();
    
    const result = checkEscalationTriggers(state, turn, ['tier2', 'tools', 'programming'], 0);
    
    expect(result.shouldEscalate).toBe(true);
    expect(result.reason).toContain('No progress');
  });

  test('should escalate when model reports stuck', () => {
    const state = createMockState();
    const turn = createMockTurn({ status: 'stuck' });
    
    const result = checkEscalationTriggers(state, turn, ['tier2', 'tools', 'programming'], 0);
    
    expect(result.shouldEscalate).toBe(true);
    expect(result.reason).toContain('stuck');
  });

  test('should not escalate when no triggers met', () => {
    const state = createMockState({ confidenceScore: 75 });
    const turn = createMockTurn({ confidence: 75 });
    
    const result = checkEscalationTriggers(state, turn, ['tier2', 'tools', 'programming'], 0);
    
    expect(result.shouldEscalate).toBe(false);
  });

  test('should follow escalation ladder correctly', () => {
    expect(getNextModel('tier1')).toBe('tier2');
    expect(getNextModel('tier2')).toBe('tier3');
    expect(getNextModel('tier3')).toBe('tier4');
    expect(getNextModel('tier4')).toBeNull();
  });

  test('should detect max escalation', () => {
    expect(isAtMaxEscalation('tier4')).toBe(true);
    expect(isAtMaxEscalation('tier3')).toBe(false);
    expect(isAtMaxEscalation('tier2')).toBe(false);
  });
});
