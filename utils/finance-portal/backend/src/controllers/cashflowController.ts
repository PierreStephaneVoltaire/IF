import { Request, Response, NextFunction } from 'express';
import {
  resolvePointer,
  patchVersionedItem,
  calculateCashflowTotals,
} from '../db/dynamodb.js';
import { MonthlyCashflow, PutCashflowRequest } from '@finance-portal/types';
import { createError } from '../middleware/errorHandler.js';

const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator';

/**
 * PUT /api/cashflow
 * Replace full cashflow object, recalculates totals server-side
 */
export async function putCashflow(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { cashflow } = req.body as PutCashflowRequest;

    if (!cashflow) {
      throw createError('Cashflow data is required', 400, 'VALIDATION_ERROR');
    }

    // Get current snapshot
    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    // Calculate totals server-side (never trust client)
    const totals = calculateCashflowTotals(cashflow);

    // Build complete cashflow with computed totals
    const completeCashflow: MonthlyCashflow = {
      ...cashflow,
      as_of: new Date().toISOString(),
      ...totals,
    };

    // Update the cashflow
    await patchVersionedItem(pk, 'monthly_cashflow', completeCashflow);

    res.json({ success: true, cashflow: completeCashflow });
  } catch (error) {
    next(error);
  }
}

/**
 * GET /api/cashflow
 * Get current cashflow data
 */
export async function getCashflow(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    res.json({ cashflow: resolved.item.monthly_cashflow });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/cashflow/income
 * Update net monthly income
 */
export async function patchIncome(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { net_monthly_income } = req.body;

    if (typeof net_monthly_income !== 'number' || isNaN(net_monthly_income)) {
      throw createError('net_monthly_income must be a valid number', 400, 'VALIDATION_ERROR');
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const updatedCashflow: MonthlyCashflow = {
      ...resolved.item.monthly_cashflow,
      net_monthly_income,
    };

    // Recalculate totals
    const totals = calculateCashflowTotals(updatedCashflow);
    Object.assign(updatedCashflow, totals);

    await patchVersionedItem(pk, 'monthly_cashflow', updatedCashflow);

    res.json({ success: true, cashflow: updatedCashflow });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/cashflow/fixed-expenses
 * Update fixed expenses array
 */
export async function patchFixedExpenses(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { fixed_expenses } = req.body;

    if (!Array.isArray(fixed_expenses)) {
      throw createError('fixed_expenses must be an array', 400, 'VALIDATION_ERROR');
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const updatedCashflow: MonthlyCashflow = {
      ...resolved.item.monthly_cashflow,
      fixed_expenses,
    };

    // Recalculate totals
    const totals = calculateCashflowTotals(updatedCashflow);
    Object.assign(updatedCashflow, totals);

    await patchVersionedItem(pk, 'monthly_cashflow', updatedCashflow);

    res.json({ success: true, cashflow: updatedCashflow });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/cashflow/debt-payments
 * Update debt payments array
 */
export async function patchDebtPayments(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { debt_payments } = req.body;

    if (!Array.isArray(debt_payments)) {
      throw createError('debt_payments must be an array', 400, 'VALIDATION_ERROR');
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const updatedCashflow: MonthlyCashflow = {
      ...resolved.item.monthly_cashflow,
      debt_payments,
    };

    // Recalculate totals
    const totals = calculateCashflowTotals(updatedCashflow);
    Object.assign(updatedCashflow, totals);

    await patchVersionedItem(pk, 'monthly_cashflow', updatedCashflow);

    res.json({ success: true, cashflow: updatedCashflow });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/cashflow/savings-investments
 * Update savings and investments array
 */
export async function patchSavingsInvestments(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { savings_and_investments } = req.body;

    if (!Array.isArray(savings_and_investments)) {
      throw createError('savings_and_investments must be an array', 400, 'VALIDATION_ERROR');
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const updatedCashflow: MonthlyCashflow = {
      ...resolved.item.monthly_cashflow,
      savings_and_investments,
    };

    // Recalculate totals
    const totals = calculateCashflowTotals(updatedCashflow);
    Object.assign(updatedCashflow, totals);

    await patchVersionedItem(pk, 'monthly_cashflow', updatedCashflow);

    res.json({ success: true, cashflow: updatedCashflow });
  } catch (error) {
    next(error);
  }
}

/**
 * PATCH /api/cashflow/variable-budget
 * Update variable expense budget array
 */
export async function patchVariableBudget(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  try {
    const pk = (req.query.pk as string) || OPERATOR_PK;
    const { variable_expense_budget } = req.body;

    if (!Array.isArray(variable_expense_budget)) {
      throw createError('variable_expense_budget must be an array', 400, 'VALIDATION_ERROR');
    }

    // Validate that all budget_amount values are valid numbers
    for (const item of variable_expense_budget) {
      if (typeof item.budget_amount === 'number' && isNaN(item.budget_amount)) {
        throw createError('budget_amount values must be valid numbers', 400, 'VALIDATION_ERROR');
      }
    }

    const resolved = await resolvePointer(pk);
    if (!resolved) {
      throw createError('No finance snapshot found', 404, 'NOT_FOUND');
    }

    const updatedCashflow: MonthlyCashflow = {
      ...resolved.item.monthly_cashflow,
      variable_expense_budget,
    };

    // Recalculate totals
    const totals = calculateCashflowTotals(updatedCashflow);
    Object.assign(updatedCashflow, totals);

    await patchVersionedItem(pk, 'monthly_cashflow', updatedCashflow);

    res.json({ success: true, cashflow: updatedCashflow });
  } catch (error) {
    next(error);
  }
}
