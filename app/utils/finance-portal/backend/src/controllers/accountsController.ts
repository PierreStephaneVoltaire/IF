import { Request, Response, NextFunction } from 'express';
import {
  resolvePointer,
  patchVersionedItem,
  calculateUtilization,
} from '../db/dynamodb.js';
import {
  PatchCreditCardRequest,
  PatchLOCRequest,
  PatchLoanRequest,
  CreditCard,
  LineOfCredit,
  Loan,
} from '@finance-portal/types';
import { createError } from '../middleware/errorHandler.js';

const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator';

/**
 * PATCH /api/accounts/credit-cards/:id
 * Update a credit card (surgical update, no new version)
 */
export async function patchCreditCard(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { id } = req.params;
    const updates = req.body as PatchCreditCardRequest;

    if (!id) {
      throw createError('Credit card ID is required', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot to find the card
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const cardIndex = resolved.item.accounts.credit_cards.findIndex((c) => c.id === id);
    if (cardIndex === -1) {
      throw createError('Credit card not found', 404, 'NOT_FOUND');
    }

    // Get the existing card
    const existingCard = resolved.item.accounts.credit_cards[cardIndex];

    // Apply updates
    const updatedCard: CreditCard = {
      ...existingCard,
      ...updates,
    };

    // Recalculate utilization if balance or limit changed
    if (updates.balance_owing !== undefined || updates.credit_limit !== undefined) {
      updatedCard.utilization_pct = calculateUtilization(updatedCard);
    }

    // Update the card in the array
    const path = `accounts.credit_cards[${cardIndex}]`;
    await patchVersionedItem(pk, path, updatedCard);

    res.json({ success: true, card: updatedCard });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/accounts/loc/:id
 * Update a line of credit (surgical update, no new version)
 */
export async function patchLineOfCredit(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { id } = req.params;
    const updates = req.body as PatchLOCRequest;

    if (!id) {
      throw createError('LOC ID is required', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot to find the LOC
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const locIndex = resolved.item.accounts.lines_of_credit.findIndex((loc) => loc.id === id);
    if (locIndex === -1) {
      throw createError('Line of credit not found', 404, 'NOT_FOUND');
    }

    // Get the existing LOC
    const existingLOC = resolved.item.accounts.lines_of_credit[locIndex];

    // Apply updates
    const updatedLOC: LineOfCredit = {
      ...existingLOC,
      ...updates,
    };

    // Update the LOC in the array
    const path = `accounts.lines_of_credit[${locIndex}]`;
    await patchVersionedItem(pk, path, updatedLOC);

    res.json({ success: true, loc: updatedLOC });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/accounts/loans/:id
 * Update a loan (surgical update, no new version)
 */
export async function patchLoan(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { id } = req.params;
    const updates = req.body as PatchLoanRequest;

    if (!id) {
      throw createError('Loan ID is required', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot to find the loan
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const loanIndex = resolved.item.accounts.loans.findIndex((l) => l.id === id);
    if (loanIndex === -1) {
      throw createError('Loan not found', 404, 'NOT_FOUND');
    }

    // Get the existing loan
    const existingLoan = resolved.item.accounts.loans[loanIndex];

    // Apply updates
    const updatedLoan: Loan = {
      ...existingLoan,
      ...updates,
    };

    // Update the loan in the array
    const path = `accounts.loans[${loanIndex}]`;
    await patchVersionedItem(pk, path, updatedLoan);

    res.json({ success: true, loan: updatedLoan });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/accounts/chequing/:id
 * Update a chequing account
 */
export async function patchChequing(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { id } = req.params;
    const updates = req.body;

    if (!id) {
      throw createError('Account ID is required', 400, 'VALIDATION_ERROR');
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const accountIndex = resolved.item.accounts.chequing.findIndex((a) => a.id === id);
    if (accountIndex === -1) {
      throw createError('Account not found', 404, 'NOT_FOUND');
    }

    const existingAccount = resolved.item.accounts.chequing[accountIndex];
    const updatedAccount = { ...existingAccount, ...updates };

    const path = `accounts.chequing[${accountIndex}]`;
    await patchVersionedItem(pk, path, updatedAccount);

    res.json({ success: true, account: updatedAccount });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/accounts/savings/:id
 * Update a savings account
 */
export async function patchSavings(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { id } = req.params;
    const updates = req.body;

    if (!id) {
      throw createError('Account ID is required', 400, 'VALIDATION_ERROR');
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const accountIndex = resolved.item.accounts.savings.findIndex((a) => a.id === id);
    if (accountIndex === -1) {
      throw createError('Account not found', 404, 'NOT_FOUND');
    }

    const existingAccount = resolved.item.accounts.savings[accountIndex];
    const updatedAccount = { ...existingAccount, ...updates };

    const path = `accounts.savings[${accountIndex}]`;
    await patchVersionedItem(pk, path, updatedAccount);

    res.json({ success: true, account: updatedAccount });
  } catch (error) {
    next(error);
  }
}
