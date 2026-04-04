import { Router } from 'express';
import {
  getCashflow,
  putCashflow,
  patchIncome,
  patchFixedExpenses,
  patchDebtPayments,
  patchSavingsInvestments,
  patchVariableBudget,
} from '../controllers/cashflowController.js';

const router = Router();

/**
 * GET /api/cashflow
 * Get current cashflow data
 */
router.get('/', getCashflow);

/**
 * PUT /api/cashflow
 * Replace full cashflow object, recalculates totals
 */
router.put('/', putCashflow);

/**
 * PATCH /api/cashflow/income
 * Update net monthly income
 */
router.patch('/income', patchIncome);

/**
 * PATCH /api/cashflow/fixed-expenses
 * Update fixed expenses array
 */
router.patch('/fixed-expenses', patchFixedExpenses);

/**
 * PATCH /api/cashflow/debt-payments
 * Update debt payments array
 */
router.patch('/debt-payments', patchDebtPayments);

/**
 * PATCH /api/cashflow/savings-investments
 * Update savings and investments array
 */
router.patch('/savings-investments', patchSavingsInvestments);

/**
 * PATCH /api/cashflow/variable-budget
 * Update variable expense budget array
 */
router.patch('/variable-budget', patchVariableBudget);

export default router;
