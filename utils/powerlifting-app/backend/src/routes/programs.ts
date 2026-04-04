import { Router } from 'express'
import * as programController from '../controllers/programController'

export const programsRouter = Router()

// GET /api/programs - List all program versions
programsRouter.get('/', async (req, res, next) => {
  try {
    const programs = await programController.listPrograms()
    res.json({ data: programs, error: null })
  } catch (err) {
    next(err)
  }
})

// GET /api/programs/:version - Get a specific program
programsRouter.get('/:version', async (req, res, next) => {
  try {
    const program = await programController.getProgram(req.params.version)
    res.json({ data: program, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/programs/:version/meta - Update a meta field
programsRouter.put('/:version/meta', async (req, res, next) => {
  try {
    const { field, value } = req.body

    if (!field || value === undefined) {
      return res.status(400).json({
        data: null,
        error: 'Missing field or value in request body',
      })
    }

    await programController.updateMetaField(req.params.version, field, value)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/programs/:version/fork - Fork to a new version
programsRouter.post('/:version/fork', async (req, res, next) => {
  try {
    const { label } = req.body
    const newVersion = await programController.forkProgram(req.params.version, label)
    res.json({ data: { version: newVersion }, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/programs/:version/body-weight - Update body weight
programsRouter.put('/:version/body-weight', async (req, res, next) => {
  try {
    const { weightKg } = req.body

    if (typeof weightKg !== 'number') {
      return res.status(400).json({
        data: null,
        error: 'weightKg must be a number',
      })
    }

    await programController.updateMetaField(req.params.version, 'current_body_weight_kg', weightKg)
    await programController.updateMetaField(req.params.version, 'current_body_weight_lb', weightKg * 2.20462)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/programs/:version/phases - Update phases
programsRouter.put('/:version/phases', async (req, res, next) => {
  try {
    const { phases } = req.body

    if (!Array.isArray(phases)) {
      return res.status(400).json({
        data: null,
        error: 'phases must be an array',
      })
    }

    await programController.updatePhases(req.params.version, phases)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})
