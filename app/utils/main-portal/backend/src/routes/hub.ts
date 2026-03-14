import { Router } from 'express'
import { getHubStatus } from '../controllers/hubController.js'

export const hubRouter = Router()

/**
 * GET /api/hub/status
 *
 * Aggregates status from all portal backends in parallel.
 * Returns unified view with graceful degradation for unreachable portals.
 */
hubRouter.get('/status', async (_req, res, next) => {
  try {
    const status = await getHubStatus()
    res.json({
      data: status,
      error: null,
    })
  } catch (error) {
    next(error)
  }
})
