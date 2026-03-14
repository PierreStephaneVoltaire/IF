import { Request, Response, NextFunction } from 'express';
import {
  getProposalsByStatus,
  getProposal,
  createProposal,
  updateProposalStatus,
  deleteProposal,
  OPERATOR_PK,
} from '../db/dynamodb';
import { generateImplementationPlan } from '../services/planGenerator';
import { getDirectives } from '../db/dynamodb';
import { createError } from '../middleware/errorHandler';
import { WebSocket } from 'ws';

// Store connected WebSocket clients
export const wsClients = new Set<WebSocket>();

export async function listProposals(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { status, type, author, q } = req.query;

    let proposals = await getProposalsByStatus(OPERATOR_PK);

    // Apply filters
    if (status) {
      proposals = proposals.filter((p) => p.status === status);
    }
    if (type) {
      proposals = proposals.filter((p) => p.type === type);
    }
    if (author) {
      proposals = proposals.filter((p) => p.author === author);
    }
    if (q) {
      const searchLower = (q as string).toLowerCase();
      proposals = proposals.filter(
        (p) =>
          p.title.toLowerCase().includes(searchLower) ||
          p.rationale.toLowerCase().includes(searchLower)
      );
    }

    // Sort by created_at descending
    proposals.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );

    res.json({
      proposals,
      total: proposals.length,
    });
  } catch (error) {
    next(error);
  }
}

export async function getProposalById(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const proposal = await getProposal(OPERATOR_PK, decodeURIComponent(sk));

    if (!proposal) {
      throw createError('Proposal not found', 404);
    }

    res.json({ proposal });
  } catch (error) {
    next(error);
  }
}

export async function createNewProposal(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { type, title, rationale, content, target_id } = req.body;

    if (!title || !rationale) {
      throw createError('Title and rationale are required');
    }

    const now = new Date().toISOString();
    const sk = `proposal#${now}`;

    const proposal = {
      pk: OPERATOR_PK,
      sk,
      type: type || 'system_observation',
      status: 'pending',
      author: 'user',
      title,
      rationale,
      content: content || '',
      target_id: target_id || null,
      implementation_plan: null,
      created_at: now,
      resolved_at: null,
      resolved_by: null,
      rejection_reason: null,
    };

    await createProposal(proposal);

    res.status(201).json({ proposal });
  } catch (error) {
    next(error);
  }
}

export async function approveProposal(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const now = new Date().toISOString();

    const proposal = await updateProposalStatus(OPERATOR_PK, decodeURIComponent(sk), {
      status: 'approved',
      resolved_at: now,
      resolved_by: 'user',
    });

    if (!proposal) {
      throw createError('Proposal not found', 404);
    }

    // Trigger plan generation asynchronously
    generatePlanAsync(proposal);

    res.json({ proposal });
  } catch (error) {
    next(error);
  }
}

export async function rejectProposal(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const { reason } = req.body;
    const now = new Date().toISOString();

    const proposal = await updateProposalStatus(OPERATOR_PK, decodeURIComponent(sk), {
      status: 'rejected',
      resolved_at: now,
      resolved_by: 'user',
      rejection_reason: reason || null,
    });

    if (!proposal) {
      throw createError('Proposal not found', 404);
    }

    res.json({ proposal });
  } catch (error) {
    next(error);
  }
}

export async function deleteProposalById(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const deleted = await deleteProposal(OPERATOR_PK, decodeURIComponent(sk));

    if (!deleted) {
      throw createError(
        'Proposal not found or cannot be deleted (only pending proposals can be deleted)',
        400
      );
    }

    res.status(204).send();
  } catch (error) {
    next(error);
  }
}

export async function generatePlan(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const proposal = await getProposal(OPERATOR_PK, decodeURIComponent(sk));

    if (!proposal) {
      throw createError('Proposal not found', 404);
    }

    if (proposal.status !== 'approved') {
      throw createError('Can only generate plans for approved proposals', 400);
    }

    // Generate plan asynchronously
    generatePlanAsync(proposal);

    res.json({ success: true, message: 'Plan generation started' });
  } catch (error) {
    next(error);
  }
}

export async function getPlan(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const proposal = await getProposal(OPERATOR_PK, decodeURIComponent(sk));

    if (!proposal) {
      throw createError('Proposal not found', 404);
    }

    res.json({ plan: proposal.implementation_plan });
  } catch (error) {
    next(error);
  }
}

// Helper function to generate plan asynchronously and notify WebSocket clients
async function generatePlanAsync(proposal: any): Promise<void> {
  const sk = proposal.sk;

  // Notify clients that plan is generating
  broadcast({ type: 'plan_generating', sk });

  try {
    const directives = await getDirectives(OPERATOR_PK);
    const plan = await generateImplementationPlan(proposal, directives);

    // Update proposal with plan
    await updateProposalStatus(OPERATOR_PK, sk, { implementation_plan: plan });

    // Notify clients that plan is ready
    broadcast({ type: 'plan_ready', sk, plan });
  } catch (error: any) {
    console.error('Plan generation failed:', error);

    // Notify clients of failure
    broadcast({ type: 'plan_failed', sk, error: error.message });
  }
}

// Broadcast to all connected WebSocket clients
function broadcast(message: any): void {
  const data = JSON.stringify(message);
  wsClients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(data);
    }
  });
}
