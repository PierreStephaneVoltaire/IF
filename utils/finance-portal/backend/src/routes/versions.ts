import { Router } from 'express';
import {
  listAllVersions,
  getSpecificVersion,
} from '../controllers/financeController.js';

const router = Router();

/**
 * GET /api/versions
 * List all versions (alias for /api/finance/versions)
 */
router.get('/', listAllVersions);

/**
 * GET /api/versions/:sk
 * Get specific version (alias for /api/finance/versions/:sk)
 */
router.get('/:sk', getSpecificVersion);

export default router;
