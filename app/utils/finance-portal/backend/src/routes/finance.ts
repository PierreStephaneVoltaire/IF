import { Router } from 'express';
import {
  getCurrentSnapshot,
  saveSnapshot,
  listAllVersions,
  getSpecificVersion,
} from '../controllers/financeController.js';

const router = Router();

/**
 * GET /api/finance/current
 * Get current finance snapshot (resolves pointer)
 */
router.get('/current', getCurrentSnapshot);

/**
 * PUT /api/finance
 * Save full snapshot (creates new version)
 */
router.put('/', saveSnapshot);

/**
 * GET /api/finance/versions
 * List all versions
 */
router.get('/versions', listAllVersions);

/**
 * GET /api/finance/versions/:sk
 * Get specific version by sk
 */
router.get('/versions/:sk', getSpecificVersion);

export default router;
