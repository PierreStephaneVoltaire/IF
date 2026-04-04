import { Router } from 'express';
import {
  listProposals,
  getProposalById,
  createNewProposal,
  approveProposal,
  rejectProposal,
  deleteProposalById,
  generatePlan,
  getPlan,
} from '../controllers/proposalsController';

const router = Router();

// Proposals CRUD
router.get('/', listProposals);
router.get('/:sk', getProposalById);
router.post('/', createNewProposal);
router.patch('/:sk/approve', approveProposal);
router.patch('/:sk/reject', rejectProposal);
router.delete('/:sk', deleteProposalById);

// Implementation Plan
router.post('/:sk/generate-plan', generatePlan);
router.get('/:sk/plan', getPlan);

export default router;
