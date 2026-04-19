import { Router } from 'express'
import * as templateController from '../controllers/templateController'

export const templateRouter = Router()

// GET /api/templates
templateRouter.get('/', templateController.listTemplates)

// GET /api/templates/:sk
templateRouter.get('/:sk', templateController.getTemplate)

// POST /api/templates
templateRouter.post('/', templateController.createTemplateFromBlock)

// POST /api/templates/:sk/copy
templateRouter.post('/:sk/copy', templateController.copyTemplate)

// PATCH /api/templates/:sk/archive
templateRouter.patch('/:sk/archive', templateController.archiveTemplate)

// PATCH /api/templates/:sk/unarchive
templateRouter.patch('/:sk/unarchive', templateController.unarchiveTemplate)

// POST /api/templates/:sk/evaluate
templateRouter.post('/:sk/evaluate', templateController.evaluateTemplate)

// POST /api/templates/:sk/apply
templateRouter.post('/:sk/apply', templateController.applyTemplate)

// POST /api/templates/:sk/apply/confirm
templateRouter.post('/:sk/apply/confirm', templateController.confirmApplyTemplate)

// POST /api/templates/blank
templateRouter.post('/blank', templateController.createBlankTemplate)

// PUT /api/templates/:sk
templateRouter.put('/:sk', templateController.updateTemplate)
