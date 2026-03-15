import { Router } from 'express'
import { getLatestSignal, getSignalHistory, getEntryCount } from '../controllers/signalsController'

export const signalsRouter = Router()

/**
 * GET /api/signals/latest - Get current signal
 * Returns the latest mental health snapshot
 */
signalsRouter.get('/latest', async (_req, res, next) => {
  try {
    const signal = await getLatestSignal()

    res.json({
      data: signal,
      error: null,
    })
  } catch (err) {
    next(err)
  }
})

/**
 * GET /api/signals - Get signal history for charting
 * Query params:
 *   - days: number (default: 90, max: 365)
 * Returns signals sorted by computed_at ascending
 */
signalsRouter.get('/', async (req, res, next) => {
  try {
    const daysParam = req.query.days
    let days = 90

    if (daysParam) {
      const parsed = parseInt(daysParam as string, 10)
      if (!isNaN(parsed) && parsed > 0 && parsed <= 365) {
        days = parsed
      }
    }

    const signals = await getSignalHistory(days)

    res.json({
      data: signals,
      error: null,
    })
  } catch (err) {
    next(err)
  }
})

/**
 * GET /api/signals/entry-count - Get count of active entries
 * Returns how many non-expired entries the agent has to work with
 * No content is ever returned - just the count
 */
signalsRouter.get('/entry-count', async (_req, res, next) => {
  try {
    const count = await getEntryCount()

    res.json({
      data: { count },
      error: null,
    })
  } catch (err) {
    next(err)
  }
})
