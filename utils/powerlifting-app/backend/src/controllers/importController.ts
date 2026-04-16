import { Request, Response } from 'express'
import { importService } from '../services/importService'
import { templateService } from '../services/templateService'
import { invokeToolDirect } from '../utils/agent'
import { AppError } from '../middleware/errorHandler'
import type { ImportType } from '@powerlifting/types'

/**
 * Upload a file for parsing and staging
 */
export async function uploadImport(req: Request, res: Response) {
  if (!req.file) {
    throw new AppError('No file uploaded', 400)
  }

  const { buffer, originalname } = req.file
  let type = req.body.type as ImportType
  if ((type as any) === 'program_template') type = 'template'
  if (!type) type = 'template'

  try {
    const importPending = await importService.stageImport({
      buffer,
      filename: originalname,
      type,
    })

    res.status(201).json(importPending)
  } catch (err: any) {
    console.error('[ImportController] upload failed:', err)
    throw new AppError(`Import failed: ${err.message}`, 502)
  }
}

/**
 * List pending imports
 */
export async function listPendingImports(req: Request, res: Response) {
  const type = req.query.type as ImportType | undefined
  const pending = await importService.listPending()
  res.json(pending)
}

/**
 * Get a specific pending import
 */
export async function getPendingImport(req: Request, res: Response) {
  const { importId } = req.params
  const pending = await importService.get(importId)
  if (!pending) {
    throw new AppError('Import not found', 404)
  }
  res.json(pending)
}

/**
 * Apply a staged import
 */
export async function applyImport(req: Request, res: Response) {
  const { importId } = req.params
  const { merge_strategy, conflict_resolutions, start_date } = req.body

  try {
    const result = await importService.apply(
      importId,
      merge_strategy,
      conflict_resolutions,
      start_date
    )

    res.json(result)
  } catch (err: any) {
    throw new AppError(`Apply failed: ${err.message}`, 502)
  }
}

/**
 * Reject a staged import
 */
export async function rejectImport(req: Request, res: Response) {
  const { importId } = req.params
  const { reason } = req.body

  await importService.reject(importId, reason)
  res.json({ status: 'rejected', importId })
}
