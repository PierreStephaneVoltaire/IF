/**
 * LangGraph Graphs Index
 *
 * Exports all LangGraph StateGraph implementations for flow execution.
 * Each flow type has its own graph with nodes for logging, Mermaid generation, etc.
 *
 * @see plans/langgraph-migration-plan.md
 */

// ============================================================================
// Single-Node Graphs (Simple flows)
// ============================================================================

export { simpleGraph, createSimpleGraph } from './simple';
export { socialGraph, createSocialGraph } from './social';
export { proofreaderGraph, createProofreaderGraph } from './proofreader';
export { shellGraph, createShellGraph } from './shell';
export { breakglassGraph, createBreakglassGraph } from './breakglass';

// ============================================================================
// Parallel Graphs (Multi-model flows)
// ============================================================================

export { branchGraph, createBranchGraph } from './branch';
export { dialecticGraph, createDialecticGraph } from './dialectic';
export { consensusGraph, createConsensusGraph } from './consensus';
export { angelDevilGraph, createAngelDevilGraph } from './angel-devil';

// ============================================================================
// Multi-Node Graphs
// ============================================================================

export { architectureGraph, createArchitectureGraph } from './architecture';
export { sequentialThinkingGraph, createSequentialThinkingGraph } from './sequential';

// ============================================================================
// Types
// ============================================================================

export * from './types';

// ============================================================================
// Graph Factory
// ============================================================================

import { FlowType } from '../../litellm/types';
import type { GraphResult, GraphInvokeOptions } from './types';
import { simpleGraph } from './simple';
import { socialGraph } from './social';
import { proofreaderGraph } from './proofreader';
import { shellGraph } from './shell';
import { breakglassGraph } from './breakglass';
import { branchGraph } from './branch';
import { dialecticGraph } from './dialectic';
import { consensusGraph } from './consensus';
import { angelDevilGraph } from './angel-devil';
import { architectureGraph } from './architecture';
import { sequentialThinkingGraph } from './sequential';

/**
 * Get the appropriate graph for a given flow type.
 */
export function getGraphForFlow(flowType: FlowType): {
  name: string;
  invoke: (options: GraphInvokeOptions) => Promise<GraphResult>;
} {
  switch (flowType) {
    case FlowType.SIMPLE:
      return simpleGraph;
    case FlowType.SOCIAL:
      return socialGraph;
    case FlowType.PROOFREADER:
      return proofreaderGraph;
    case FlowType.SHELL:
      return shellGraph;
    case FlowType.BREAKGLASS:
      return breakglassGraph;
    case FlowType.BRANCH:
      return branchGraph;
    case FlowType.DIALECTIC:
      return dialecticGraph;
    case FlowType.CONSENSUS:
      return consensusGraph;
    case FlowType.ANGEL_DEVIL:
      return angelDevilGraph;
    case FlowType.ARCHITECTURE:
      return architectureGraph;
    case FlowType.SEQUENTIAL_THINKING:
      return sequentialThinkingGraph;
    default:
      return simpleGraph;
  }
}

/**
 * Invoke a graph for a given flow type.
 */
export async function invokeGraph(
  flowType: FlowType,
  options: GraphInvokeOptions
): Promise<GraphResult> {
  const graph = getGraphForFlow(flowType);
  return graph.invoke(options);
}

/**
 * Get all available graph names.
 */
export function getAvailableGraphs(): string[] {
  return [
    'SimpleGraph',
    'SocialGraph',
    'ProofreaderGraph',
    'ShellGraph',
    'BreakglassGraph',
    'BranchGraph',
    'DialecticGraph',
    'ConsensusGraph',
    'AngelDevilGraph',
    'ArchitectureGraph',
    'SequentialThinkingGraph',
  ];
}
