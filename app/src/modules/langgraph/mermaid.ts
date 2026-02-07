/**
 * Mermaid Diagram Generator for LangGraph
 *
 * Generates execution diagrams from traversed nodes and renders them to PNG.
 * Uses mermaid-cli for PNG rendering.
 *
 * @see plans/langgraph-migration-plan.md §3
 */

import { createLogger } from '../../utils/logger';
import type { GraphState, ExecutionTurn } from './state';

const log = createLogger('MERMAID');

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MermaidGenerationOptions {
  flowType: string;
  traversedNodes: string[];
  turns: ExecutionTurn[];
  finalStatus: string;
}

/**
 * Result of Mermaid generation.
 */
export interface MermaidResult {
  mermaidSource: string;
  nodeCount: number;
  turnCount: number;
}

// ---------------------------------------------------------------------------
// Mermaid Generator
// ---------------------------------------------------------------------------

export class MermaidGenerator {
  /**
   * Generate Mermaid diagram source from traversed nodes.
   */
  generate(options: MermaidGenerationOptions): string {
    const { flowType, traversedNodes, turns, finalStatus } = options;

    log.info(`Generating Mermaid diagram for ${flowType}: ${traversedNodes.length} nodes, ${turns.length} turns`);

    // Build the diagram
    const nodes = new Set<string>();
    const edges: Array<{ from: string; to: string }> = [];

    // Add traversed nodes
    for (const node of traversedNodes) {
      nodes.add(this.formatNodeName(node));
    }

    // Add edges between consecutive traversed nodes
    for (let i = 0; i < traversedNodes.length - 1; i++) {
      edges.push({
        from: this.formatNodeName(traversedNodes[i]),
        to: this.formatNodeName(traversedNodes[i + 1]),
      });
    }

    // Generate flowchart
    let diagram = 'flowchart TD\n';

    // Add style definitions
    diagram += '    classDef visited fill:#2ecc71,stroke:#27ae60,color:#fff\n';
    diagram += '    classDef current fill:#3498db,stroke:#2980b9,color:#fff\n';
    diagram += '    classDef skipped fill:#95a5a6,stroke:#7f8c8d,color:#fff\n\n';

    // Add nodes with styles
    for (const node of nodes) {
      const isStart = node === 'start' || node === 'setup';
      const isEnd = node === 'finalize' || node === 'end';
      const isVisited = traversedNodes.includes(this.reverseFormat(node));

      let label = this.formatNodeLabel(node);
      if (node.includes('turn')) {
        // Add model info to turn nodes
        const turnNum = node.match(/turn(\d+)/)?.[1];
        if (turnNum && turns[parseInt(turnNum) - 1]) {
          const turn = turns[parseInt(turnNum) - 1];
          label += `<br/>${turn.modelUsed}`;
        }
      }

      diagram += `    ${node}["${label}"]\n`;
    }

    diagram += '\n';

    // Add edges
    for (const edge of edges) {
      diagram += `    ${edge.from} --> ${edge.to}\n`;
    }

    // Add final status
    if (finalStatus && finalStatus !== 'complete') {
      diagram += `\n    note right of ${traversedNodes[traversedNodes.length - 1] || 'end'}: Status: ${finalStatus}`;
    }

    return diagram;
  }

  /**
   * Generate a simple execution summary diagram.
   */
  generateSummary(state: GraphState): string {
    const options: MermaidGenerationOptions = {
      flowType: state.flowType,
      traversedNodes: state.traversedNodes,
      turns: state.turns,
      finalStatus: state.status,
    };

    return this.generate(options);
  }

  /**
   * Format a node name for Mermaid (alphanumeric + underscores).
   */
  private formatNodeName(node: string): string {
    return node.toLowerCase().replace(/[^a-z0-9]/g, '_');
  }

  /**
   * Reverse format a node name.
   */
  private reverseFormat(name: string): string {
    return name;
  }

  /**
   * Format a node name for display label.
   */
  private formatNodeLabel(node: string): string {
    const labels: Record<string, string> = {
      start: 'Start',
      setup: 'Setup',
      plan: 'Plan',
      execute_turn: 'Execute Turn',
      evaluate_turn: 'Evaluate',
      check_escalation: 'Check Escalation',
      checkpoint: 'Checkpoint',
      reflect: 'Reflexion',
      ask_clarification: 'Clarify',
      abort: 'Abort',
      finalize: 'Finalize',
      end: 'End',
      social: 'Social Response',
      proofread: 'Proofread',
      shell: 'Shell Command',
      simple: 'Simple Response',
    };

    // Handle turn nodes
    if (node.match(/^turn\d+$/)) {
      return `Turn ${node.match(/\d+/)?.[0] || ''}`;
    }

    return labels[node] || node.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  }

  /**
   * Generate a full execution diagram with turn details.
   */
  generateDetailedDiagram(state: GraphState): string {
    let diagram = 'flowchart TB\n';
    diagram += '    classDef visited fill:#2ecc71,stroke:#27ae60,color:#fff\n';
    diagram += '    classDef complete fill:#27ae60,stroke:#1e8449,color:#fff\n';
    diagram += '    classDef error fill:#e74c3c,stroke:#c0392b,color:#fff\n';
    diagram += '    classDef pending fill:#95a5a6,stroke:#7f8c8d,color:#fff\n\n';

    // Setup node
    const startNode = 'setup';
    diagram += `    ${startNode}["Setup Session<br/>Load Tools"]:::visited\n`;

    // Plan node
    const planNode = 'plan';
    diagram += `    ${planNode}["Plan - Opus"]:::visited\n`;
    diagram += `    ${startNode} --> ${planNode}\n`;

    // Turn nodes
    for (let i = 0; i < state.turns.length; i++) {
      const turn = state.turns[i];
      const turnNode = `turn${i + 1}`;
      const evalNode = `eval${i + 1}`;

      const statusClass = turn.status === 'complete' ? 'complete' : 'visited';
      diagram += `    ${turnNode}["Turn ${i + 1}<br/>${turn.modelUsed}"]:::${statusClass}\n`;
      diagram += `    ${planNode} --> ${turnNode}\n`;

      // Evaluation node
      const evalStatus = turn.status === 'complete' ? 'complete' : 'visited';
      const confidence = Math.round(turn.confidence);
      diagram += `    ${evalNode}["Evaluate<br/>Confidence: ${confidence}%"]:::${evalStatus}\n`;
      diagram += `    ${turnNode} --> ${evalNode}\n`;
    }

    // Checkpoint nodes
    if (state.turns.length > 0) {
      diagram += `    eval${state.turns.length} -.-> checkpoint[Checkpoint]:::pending\n`;
    }

    // Final nodes
    if (state.status === 'complete') {
      diagram += '    reflect["Reflexion<br/>Trajectory Evaluation"]:::complete\n';
      diagram += `    eval${state.turns.length} --> reflect\n`;
      diagram += '    reflect --> finalize["Finalize<br/>Write Logs, Upload S3"]:::complete\n';
    } else if (state.status === 'aborted') {
      diagram += '    abort["Abort<br/>User Stopped"]:::error\n';
      diagram += `    eval${state.turns.length} --> abort\n`;
      diagram += '    abort --> finalize["Finalize"]:::error\n';
    } else if (state.status === 'needs_clarification') {
      diagram += '    clarify["Ask Clarification"]:::pending\n';
      diagram += `    eval${state.turns.length} --> clarify\n`;
      diagram += '    clarify --> finalize["Finalize"]:::pending\n';
    }

    // Escalation indicators
    if (state.escalations.length > 0) {
      diagram += '\n    %% Escalation markers\n';
      for (const esc of state.escalations) {
        diagram += `    note right of turn${esc.turnNumber}: Escalated: ${esc.fromModel} → ${esc.toModel}\n`;
      }
    }

    return diagram;
  }
}

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

let generator: MermaidGenerator | null = null;

export function getMermaidGenerator(): MermaidGenerator {
  if (!generator) {
    generator = new MermaidGenerator();
  }
  return generator;
}
