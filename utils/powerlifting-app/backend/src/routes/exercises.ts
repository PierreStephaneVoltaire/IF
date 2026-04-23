import { Router } from 'express'
import * as exerciseController from '../controllers/exerciseController'
import type { GlossaryExercise } from '@powerlifting/types'

export const exercisesRouter = Router()

// GET /api/exercises - Get full glossary
exercisesRouter.get('/', async (req, res, next) => {
  try {
    const glossary = await exerciseController.getGlossary(req.effectivePk!)
    res.json({ data: glossary.exercises, error: null })
  } catch (err) {
    next(err)
  }
})

// GET /api/exercises/search - Search exercises
exercisesRouter.get('/search', async (req, res, next) => {
  try {
    const query = req.query.q as string

    if (!query) {
      return res.status(400).json({
        data: null,
        error: 'Missing search query (q parameter)',
      })
    }

    const exercises = await exerciseController.searchExercises(req.effectivePk!, query)
    res.json({ data: exercises, error: null })
  } catch (err) {
    next(err)
  }
})

// GET /api/exercises/:id - Get exercise by ID
exercisesRouter.get('/:id', async (req, res, next) => {
  try {
    const exercise = await exerciseController.getExerciseById(req.effectivePk!, req.params.id)

    if (!exercise) {
      return res.status(404).json({
        data: null,
        error: `Exercise ${req.params.id} not found`,
      })
    }

    res.json({ data: exercise, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/exercises - Add exercise
exercisesRouter.post('/', async (req, res, next) => {
  try {
    const exercise = req.body as GlossaryExercise

    if (!exercise.name) {
      return res.status(400).json({
        data: null,
        error: 'Missing exercise name',
      })
    }

    await exerciseController.upsertExercise(req.effectivePk!, exercise)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/exercises/:id - Update exercise
exercisesRouter.put('/:id', async (req, res, next) => {
  try {
    const exercise = req.body as GlossaryExercise
    exercise.id = req.params.id

    await exerciseController.upsertExercise(req.effectivePk!, exercise)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// DELETE /api/exercises/:id - Remove exercise
exercisesRouter.delete('/:id', async (req, res, next) => {
  try {
    await exerciseController.removeExercise(req.effectivePk!, req.params.id)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/exercises/:id/archive - Archive an exercise
exercisesRouter.patch('/:id/archive', async (req, res, next) => {
  try {
    await exerciseController.archiveExercise(req.effectivePk!, req.params.id)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/exercises/:id/unarchive - Unarchive an exercise
exercisesRouter.patch('/:id/unarchive', async (req, res, next) => {
  try {
    await exerciseController.unarchiveExercise(req.effectivePk!, req.params.id)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/exercises/:id/e1rm - Set e1RM estimate
exercisesRouter.post('/:id/e1rm', async (req, res, next) => {
  try {
    const { value_kg, method } = req.body
    if (typeof value_kg !== 'number') {
      return res.status(400).json({ data: null, error: 'value_kg must be a number' })
    }
    await exerciseController.setE1rmEstimate(req.effectivePk!, req.params.id, value_kg, method)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/exercises/:id/estimate-e1rm - AI estimate e1RM
exercisesRouter.post('/:id/estimate-e1rm', async (req, res, next) => {
  try {
    const result = await exerciseController.estimateExerciseE1rm(req.params.id)
    res.json({ data: result, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/exercises/:id/estimate-fatigue - AI estimate fatigue profile
exercisesRouter.post('/:id/estimate-fatigue', async (req, res, next) => {
  try {
    const result = await exerciseController.estimateExerciseFatigue(req.params.id)
    res.json({ data: result, error: null })
  } catch (err) {
    next(err)
  }
})
