import { Router } from 'express';
import {
  patchHolding,
  putWatchlist,
  patchTargetAllocation,
  patchInvestmentAccount,
  putGlobalWatchlist,
} from '../controllers/investmentsController.js';

const router = Router();

/**
 * PATCH /api/investments/:accountId
 * Update investment account properties
 */
router.patch('/:accountId', patchInvestmentAccount);

/**
 * PATCH /api/investments/:accountId/holdings/:ticker
 * Update holding (shares, avg cost, current price)
 */
router.patch('/:accountId/holdings/:ticker', patchHolding);

/**
 * PUT /api/investments/:accountId/watchlist
 * Replace watchlist array for account
 */
router.put('/:accountId/watchlist', putWatchlist);

/**
 * PATCH /api/investments/:accountId/target-allocation
 * Update target allocation
 */
router.patch('/:accountId/target-allocation', patchTargetAllocation);

/**
 * PUT /api/investments/watchlist
 * Update global watchlist
 */
router.put('/watchlist', putGlobalWatchlist);

export default router;
