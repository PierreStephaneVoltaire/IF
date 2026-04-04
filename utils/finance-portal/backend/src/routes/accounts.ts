import { Router } from 'express';
import {
  patchCreditCard,
  patchLineOfCredit,
  patchLoan,
  patchChequing,
  patchSavings,
} from '../controllers/accountsController.js';

const router = Router();

/**
 * PATCH /api/accounts/credit-cards/:id
 * Update credit card (balance, limit, target payment)
 */
router.patch('/credit-cards/:id', patchCreditCard);

/**
 * PATCH /api/accounts/loc/:id
 * Update line of credit (balance, target payment)
 */
router.patch('/loc/:id', patchLineOfCredit);

/**
 * PATCH /api/accounts/loans/:id
 * Update loan (current balance)
 */
router.patch('/loans/:id', patchLoan);

/**
 * PATCH /api/accounts/chequing/:id
 * Update chequing account
 */
router.patch('/chequing/:id', patchChequing);

/**
 * PATCH /api/accounts/savings/:id
 * Update savings account
 */
router.patch('/savings/:id', patchSavings);

export default router;
