import { Request, Response } from 'express'
import { templateService } from '../services/templateService'
import { invokeToolDirect } from '../utils/agent'
import { AppError } from '../middleware/errorHandler'

/**
 * List all templates
 */
export async function listTemplates(req: Request, res: Response) {
  const includeArchived = req.query.includeArchived === 'true'
  const templates = await templateService.listTemplates(includeArchived)
  res.json(templates)
}

/**
 * Get full template detail
 */
export async function getTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const template = await templateService.getTemplate(sk)
  if (!template) {
    throw new AppError('Template not found', 404)
  }
  res.json(template)
}

/**
 * Create a template from a block
 */
export async function createTemplateFromBlock(req: Request, res: Response) {
  const { name, program_sk } = req.body
  
  try {
    const result = await invokeToolDirect('template_create_from_block', {
      name,
      program_sk,
    })
    res.status(201).json(result)
  } catch (err: any) {
    throw new AppError(`Template creation failed: ${err.message}`, 502)
  }
}

/**
 * Copy a template
 */
export async function copyTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const { new_name } = req.body
  
  const newSk = await templateService.copyTemplate(sk, new_name)
  res.status(201).json({ status: 'copied', new_sk: newSk })
}

/**
 * Archive a template
 */
export async function archiveTemplate(req: Request, res: Response) {
  const { sk } = req.params
  await templateService.setArchiveStatus(sk, true)
  res.json({ status: 'archived', sk })
}

/**
 * Unarchive a template
 */
export async function unarchiveTemplate(req: Request, res: Response) {
  const { sk } = req.params
  await templateService.setArchiveStatus(sk, false)
  res.json({ status: 'unarchived', sk })
}

/**
 * Run template evaluation
 */
export async function evaluateTemplate(req: Request, res: Response) {
  const { sk } = req.params
  
  try {
    const result = await templateService.evaluate(sk)
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Evaluation failed: ${err.message}`, 502)
  }
}

/**
 * Apply template to block (preview/gate check)
 */
export async function applyTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const { target, start_date, week_start_day } = req.body
  
  try {
    const result = await templateService.applyPreview(
      sk,
      target,
      start_date,
      week_start_day
    )
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Apply preview failed: ${err.message}`, 502)
  }
}

/**
 * Confirm template application
 */
export async function confirmApplyTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const { backfilled_maxes, start_date, week_start_day } = req.body
  
  try {
    // For now, delegate backfill to Python or implement here
    // Python tool: template_apply_confirm
    const result = await invokeToolDirect('template_apply_confirm', {
      sk,
      backfilled_maxes,
      start_date,
      week_start_day,
    })
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Confirm apply failed: ${err.message}`, 502)
  }
}
