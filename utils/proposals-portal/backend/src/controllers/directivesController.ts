import { Request, Response, NextFunction } from 'express';
import { getDirectives, getDirective, OPERATOR_PK } from '../db/dynamodb';
import { createError } from '../middleware/errorHandler';

export async function listDirectives(
  _req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const directives = await getDirectives(OPERATOR_PK);

    // Filter to only active directives and sort by alpha, beta
    const activeDirectives = directives
      .filter((d) => d.active !== false)
      .sort((a, b) => {
        if (a.alpha !== b.alpha) return a.alpha - b.alpha;
        return a.beta - b.beta;
      });

    res.json({
      directives: activeDirectives,
      total: activeDirectives.length,
    });
  } catch (error) {
    next(error);
  }
}

export async function getDirectiveById(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const { sk } = req.params;
    const directive = await getDirective(OPERATOR_PK, decodeURIComponent(sk));

    if (!directive) {
      throw createError('Directive not found', 404);
    }

    res.json({ directive });
  } catch (error) {
    next(error);
  }
}
