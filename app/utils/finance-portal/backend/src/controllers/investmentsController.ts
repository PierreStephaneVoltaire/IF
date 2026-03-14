import { Request, Response, NextFunction } from 'express';
import {
  resolvePointer,
  patchVersionedItem,
} from '../db/dynamodb.js';
import {
  PatchHoldingRequest,
  PutWatchlistRequest,
  PatchTargetAllocationRequest,
  InvestmentAccount,
  Holding,
} from '@finance-portal/types';
import { createError } from '../middleware/errorHandler.js';

const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator';

/**
 * PATCH /api/investments/:accountId/holdings/:ticker
 * Update a specific holding within an investment account
 */
export async function patchHolding(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { accountId, ticker } = req.params;
    const updates = req.body as PatchHoldingRequest;

    if (!accountId || !ticker) {
      throw createError('Account ID and ticker are required', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    // Find the investment account
    const accountIndex = resolved.item.investment_accounts.findIndex(
      (a) => a.id === accountId
    );
    if (accountIndex === -1) {
      throw createError('Investment account not found', 404, 'NOT_FOUND');
    }

    // Find the holding
    const account = resolved.item.investment_accounts[accountIndex];
    const holdingIndex = account.holdings.findIndex((h) => h.ticker === ticker);
    if (holdingIndex === -1) {
      throw createError('Holding not found', 404, 'NOT_FOUND');
    }

    // Apply updates
    const existingHolding = account.holdings[holdingIndex];
    const updatedHolding: Holding = {
      ...existingHolding,
      ...updates,
      last_price_update: updates.current_price !== undefined
        ? new Date().toISOString()
        : existingHolding.last_price_update,
    };

    // Update the holding in the array
    const path = `investment_accounts[${accountIndex}].holdings[${holdingIndex}]`;
    await patchVersionedItem(pk, path, updatedHolding);

    res.json({ success: true, holding: updatedHolding });
  } catch (error) {
    next(error);
  }
}

/**
 * PUT /api/investments/:accountId/watchlist
 * Replace the watchlist for an investment account
 */
export async function putWatchlist(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { accountId } = req.params;
    const { watchlist } = req.body as PutWatchlistRequest;

    if (!accountId) {
      throw createError('Account ID is required', 400, 'VALIDATION_ERROR');
    }

    if (!Array.isArray(watchlist)) {
      throw createError('Watchlist must be an array', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    // Find the investment account
    const accountIndex = resolved.item.investment_accounts.findIndex(
      (a) => a.id === accountId
    );
    if (accountIndex === -1) {
      throw createError('Investment account not found', 404, 'NOT_FOUND');
    }

    // Update the watchlist
    const path = `investment_accounts[${accountIndex}].watchlist`;
    await patchVersionedItem(pk, path, watchlist);

    res.json({ success: true, watchlist });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/investments/:accountId/target-allocation
 * Update target allocation for an investment account
 */
export async function patchTargetAllocation(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { accountId } = req.params;
    const { allocation } = req.body as PatchTargetAllocationRequest;

    if (!accountId) {
      throw createError('Account ID is required', 400, 'VALIDATION_ERROR');
    }

    if (!Array.isArray(allocation)) {
      throw createError('Allocation must be an array', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    // Find the investment account
    const accountIndex = resolved.item.investment_accounts.findIndex(
      (a) => a.id === accountId
    );
    if (accountIndex === -1) {
      throw createError('Investment account not found', 404, 'NOT_FOUND');
    }

    // Update the target allocation
    const path = `investment_accounts[${accountIndex}].target_allocation`;
    await patchVersionedItem(pk, path, allocation);

    res.json({ success: true, allocation });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/investments/:accountId
 * Update investment account properties (cash balance, notes, etc.)
 */
export async function patchInvestmentAccount(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { accountId } = req.params;
    const updates = req.body;

    if (!accountId) {
      throw createError('Account ID is required', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    // Find the investment account
    const accountIndex = resolved.item.investment_accounts.findIndex(
      (a) => a.id === accountId
    );
    if (accountIndex === -1) {
      throw createError('Investment account not found', 404, 'NOT_FOUND');
    }

    // Apply updates (excluding holdings and allocation which have their own endpoints)
    const existingAccount = resolved.item.investment_accounts[accountIndex];
    const updatedAccount: InvestmentAccount = {
      ...existingAccount,
      ...updates,
      // Preserve arrays that should be updated via dedicated endpoints
      holdings: updates.holdings || existingAccount.holdings,
      target_allocation: updates.target_allocation || existingAccount.target_allocation,
    };

    const path = `investment_accounts[${accountIndex}]`;
    await patchVersionedItem(pk, path, updatedAccount);

    res.json({ success: true, account: updatedAccount });
  } catch (error) {
    next(error);
  }
}

/**
 * PUT /api/watchlist
 * Update global watchlist
 */
export async function putGlobalWatchlist(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { watchlist } = req.body;

    if (!Array.isArray(watchlist)) {
      throw createError('Watchlist must be an array', 400, 'VALIDATION_ERROR');
    }

    await patchVersionedItem(pk, 'watchlist', watchlist);

    res.json({ success: true, watchlist });
  } catch (error) {
    next(error);
  }
}
