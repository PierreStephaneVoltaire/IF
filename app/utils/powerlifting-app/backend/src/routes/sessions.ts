import { Router } from 'express'
import * as sessionController from '../controllers/sessionController'
import type { Session, Exercise } from '@powerlifting/types'

export const sessionsRouter = Router({ mergeParams: true })

// GET /api/sessions/:version/:date - Get a specific session
sessionsRouter.get('/:version/:date', async (req, res, next) => {
  try {
    const session = await sessionController.getSession(
      req.params.version,
      req.params.date
    )
    res.json({ data: session, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/sessions/:version - Create a new session
sessionsRouter.post('/:version', async (req, res, next) => {
  try {
    const session = req.body as Partial<Session>

    if (!session.date) {
      return res.status(400).json({
        data: null,
        error: 'Session date is required',
      })
    }

    // Create a complete session with defaults
    const newSession: Session = {
      date: session.date,
      day: session.day || 'Monday',
      week: session.week || 'W1',
      week_number: 1,
      phase: session.phase || { name: 'Unknown', intent: '', start_week: 1, end_week: 1 },
      completed: false,
      exercises: session.exercises || [],
      session_notes: session.session_notes || '',
      session_rpe: session.session_rpe || null,
      body_weight_kg: session.body_weight_kg || null,
    }

    await sessionController.createSession(req.params.version, newSession)
    res.json({ data: { success: true, session: newSession }, error: null })
  } catch (err) {
    next(err)
  }
})

// DELETE /api/sessions/:version/:date - Delete a session
sessionsRouter.delete('/:version/:date', async (req, res, next) => {
  try {
    await sessionController.deleteSession(
      req.params.version,
      req.params.date
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/sessions/:version/:date - Replace entire session
sessionsRouter.put('/:version/:date', async (req, res, next) => {
  try {
    const session = req.body as Session

    if (!session || !session.date) {
      return res.status(400).json({
        data: null,
        error: 'Invalid session data',
      })
    }

    await sessionController.updateSession(
      req.params.version,
      req.params.date,
      session
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/reschedule - Move session to new date
sessionsRouter.patch('/:version/:date/reschedule', async (req, res, next) => {
  try {
    const { newDate, newDay } = req.body

    if (!newDate) {
      return res.status(400).json({
        data: null,
        error: 'Missing newDate in request body',
      })
    }

    await sessionController.rescheduleSession(
      req.params.version,
      req.params.date,
      newDate,
      newDay || 'Monday'
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/complete - Mark session complete
sessionsRouter.patch('/:version/:date/complete', async (req, res, next) => {
  try {
    const { rpe, bodyWeightKg, notes } = req.body

    await sessionController.completeSession(
      req.params.version,
      req.params.date,
      { rpe, bodyWeightKg, notes }
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/sessions/:version/:date/exercise - Add exercise to session
sessionsRouter.post('/:version/:date/exercise', async (req, res, next) => {
  try {
    const exercise = req.body as Exercise

    if (!exercise || !exercise.name) {
      return res.status(400).json({
        data: null,
        error: 'Invalid exercise data',
      })
    }

    await sessionController.addExercise(
      req.params.version,
      req.params.date,
      exercise
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/exercise/:index - Update exercise field
sessionsRouter.patch('/:version/:date/exercise/:index', async (req, res, next) => {
  try {
    const { field, value } = req.body
    const index = parseInt(req.params.index, 10)

    if (!field || value === undefined) {
      return res.status(400).json({
        data: null,
        error: 'Missing field or value in request body',
      })
    }

    await sessionController.updateExerciseField(
      req.params.version,
      req.params.date,
      index,
      field as keyof Exercise,
      value
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// DELETE /api/sessions/:version/:date/exercise/:index - Remove exercise
sessionsRouter.delete('/:version/:date/exercise/:index', async (req, res, next) => {
  try {
    const index = parseInt(req.params.index, 10)

    await sessionController.removeExercise(
      req.params.version,
      req.params.date,
      index
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})
