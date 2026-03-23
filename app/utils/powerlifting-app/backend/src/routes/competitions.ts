import { Router } from 'express'
import * as competitionController from '../controllers/competitionController'
import type { Competition, LiftResults } from '@powerlifting/types'

export const competitionsRouter = Router({ mergeParams: true })

// GET /api/competitions/:version - Get competitions
competitionsRouter.get('/:version', async (req, res, next) => {
  try {
    const competitions = await competitionController.getCompetitions(req.params.version)
    res.json({ data: competitions, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/competitions/:version - Update all competitions
competitionsRouter.put('/:version', async (req, res, next) => {
  try {
    const { competitions } = req.body

    if (!Array.isArray(competitions)) {
      return res.status(400).json({
        data: null,
        error: 'competitions must be an array',
      })
    }

    await competitionController.updateCompetitions(
      req.params.version,
      competitions as Competition[]
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/competitions/:version/migrate - Migrate last_comp into competitions
competitionsRouter.post('/:version/migrate', async (req, res, next) => {
  try {
    const competitions = await competitionController.migrateLastComp(req.params.version)
    res.json({ data: competitions, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/competitions/:version/:date/complete - Mark competition as completed
competitionsRouter.patch('/:version/:date/complete', async (req, res, next) => {
  try {
    const { results, bodyWeightKg } = req.body

    if (!results || typeof bodyWeightKg !== 'number') {
      return res.status(400).json({
        data: null,
        error: 'Missing results or bodyWeightKg in request body',
      })
    }

    await competitionController.completeCompetition(
      req.params.version,
      req.params.date,
      results as LiftResults,
      bodyWeightKg
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})
