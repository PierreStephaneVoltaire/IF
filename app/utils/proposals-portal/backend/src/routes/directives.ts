import { Router } from 'express';
import { listDirectives, getDirectiveById } from '../controllers/directivesController';

const router = Router();

router.get('/', listDirectives);
router.get('/:sk', getDirectiveById);

export default router;
