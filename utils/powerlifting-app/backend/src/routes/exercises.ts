import { Router } from 'express'
import * as exerciseController from '../controllers/exerciseController'
import type { GlossaryExercise } from '@powerlifting/types'

export const exercisesRouter = Router()

// GET /api/exercises - Get full glossary
exercisesRouter.get('/', async (req, res, next) => {
  try {
    const glossary = await exerciseController.getGlossary()
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

    const exercises = await exerciseController.searchExercises(query)
    res.json({ data: exercises, error: null })
  } catch (err) {
    next(err)
  }
})

// GET /api/exercises/:id - Get exercise by ID
exercisesRouter.get('/:id', async (req, res, next) => {
  try {
    const exercise = await exerciseController.getExerciseById(req.params.id)

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

    await exerciseController.upsertExercise(exercise)
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

    await exerciseController.upsertExercise(exercise)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// DELETE /api/exercises/:id - Remove exercise
exercisesRouter.delete('/:id', async (req, res, next) => {
  try {
    await exerciseController.removeExercise(req.params.id)
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})
