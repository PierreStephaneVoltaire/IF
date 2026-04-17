import { Request, Response } from 'express'
import { invokeToolDirect } from '../utils/agent'
import { AppError } from '../middleware/errorHandler'

export async function listTemplates(req: Request, res: Response) {
  const include_archived = req.query.includeArchived === 'true'
  try {
    const data = await invokeToolDirect('template_list', { include_archived })
    res.json(data)
  } catch (err: any) {
    throw new AppError(`List failed: ${err.message}`, 502)
  }
}

export async function getTemplate(req: Request, res: Response) {
  const { sk } = req.params
  try {
    const data = await invokeToolDirect('template_get', { sk })
    res.json(data)
  } catch (err: any) {
    if (err.message?.includes('not found')) throw new AppError('Template not found', 404)
    throw new AppError(`Get failed: ${err.message}`, 502)
  }
}

export async function createTemplateFromBlock(req: Request, res: Response) {
  const { name, program_sk } = req.body
  try {
    const result = await invokeToolDirect('template_create_from_block', { name, program_sk })
    res.status(201).json(result)
  } catch (err: any) {
    throw new AppError(`Template creation failed: ${err.message}`, 502)
  }
}

export async function copyTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const { new_name } = req.body
  try {
    const result = await invokeToolDirect('template_copy', { sk, new_name })
    res.status(201).json(result)
  } catch (err: any) {
    throw new AppError(`Copy failed: ${err.message}`, 502)
  }
}

export async function archiveTemplate(req: Request, res: Response) {
  const { sk } = req.params
  try {
    const result = await invokeToolDirect('template_archive', { sk })
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Archive failed: ${err.message}`, 502)
  }
}

export async function unarchiveTemplate(req: Request, res: Response) {
  const { sk } = req.params
  try {
    const result = await invokeToolDirect('template_unarchive', { sk })
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Unarchive failed: ${err.message}`, 502)
  }
}

export async function evaluateTemplate(req: Request, res: Response) {
  const { sk } = req.params
  try {
    const result = await invokeToolDirect('template_evaluate', { sk })
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Evaluation failed: ${err.message}`, 502)
  }
}

export async function applyTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const { target, start_date, week_start_day } = req.body
  try {
    const result = await invokeToolDirect('template_apply', { sk, target, start_date, week_start_day })
    res.json(result)
  } catch (err: any) {
    throw new AppError(`Apply preview failed: ${err.message}`, 502)
  }
}

export async function confirmApplyTemplate(req: Request, res: Response) {
  const { sk } = req.params
  const { backfilled_maxes, start_date, week_start_day } = req.body
  try {
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
