import { Router } from 'express'
import crypto from 'crypto'
import * as sessionController from '../controllers/sessionController'
import type { Session, Exercise, SessionStatus, SessionWellness } from '@powerlifting/types'

export const sessionsRouter = Router({ mergeParams: true })

// GET /api/sessions/:version/:date/:index - Get a specific session
sessionsRouter.get('/:version/:date/:index', async (req, res, next) => {
  try {
    const index = parseInt(req.params.index, 10)
    const session = await sessionController.getSession(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index
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
      id: session.id || crypto.randomUUID(),
      date: session.date,
      day: session.day || 'Monday',
      week: session.week || 'W1',
      week_number: 1,
      phase: session.phase || { name: 'Unknown', intent: '', start_week: 1, end_week: 1 },
      status: session.status || 'planned',
      completed: false,
      planned_exercises: session.planned_exercises || [],
      exercises: session.exercises || [],
      session_notes: session.session_notes || '',
      session_rpe: session.session_rpe || null,
      body_weight_kg: session.body_weight_kg || null,
      wellness: session.wellness ?? undefined,
    }

    await sessionController.createSession(req.effectivePk!, req.params.version, newSession)
    res.json({ data: { success: true, session: newSession }, error: null })
  } catch (err) {
    next(err)
  }
})

// DELETE /api/sessions/:version/:date/:index - Delete a session
sessionsRouter.delete('/:version/:date/:index', async (req, res, next) => {
  try {
    const index = parseInt(req.params.index, 10)
    await sessionController.deleteSession(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PUT /api/sessions/:version/:date/:index - Replace entire session
sessionsRouter.put('/:version/:date/:index', async (req, res, next) => {
  try {
    const session = req.body as Session
    const index = parseInt(req.params.index, 10)

    if (!session || !session.date) {
      return res.status(400).json({
        data: null,
        error: 'Invalid session data',
      })
    }

    await sessionController.updateSession(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      session
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/:index/reschedule - Move session to new date
sessionsRouter.patch('/:version/:date/:index/reschedule', async (req, res, next) => {
  try {
    const { newDate, newDay } = req.body
    const index = parseInt(req.params.index, 10)

    if (!newDate) {
      return res.status(400).json({
        data: null,
        error: 'Missing newDate in request body',
      })
    }

    await sessionController.rescheduleSession(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      newDate,
      newDay || 'Monday'
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/:index/status - Update session status
sessionsRouter.patch('/:version/:date/:index/status', async (req, res, next) => {
  try {
    const { status } = req.body as { status: SessionStatus }
    const index = parseInt(req.params.index, 10)

    const validStatuses: SessionStatus[] = ['planned', 'logged', 'completed', 'skipped']
    if (!status || !validStatuses.includes(status)) {
      return res.status(400).json({
        data: null,
        error: `Invalid status. Must be one of: ${validStatuses.join(', ')}`,
      })
    }

    await sessionController.updateSessionStatus(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      status
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/:index/complete - Mark session complete
sessionsRouter.patch('/:version/:date/:index/complete', async (req, res, next) => {
  try {
    const { rpe, bodyWeightKg, notes, wellness } = req.body as {
      rpe?: number
      bodyWeightKg?: number
      notes?: string
      wellness?: SessionWellness | null
    }
    const index = parseInt(req.params.index, 10)

    await sessionController.completeSession(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      { rpe, bodyWeightKg, notes, wellness: wellness ?? undefined }
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// POST /api/sessions/:version/:date/:index/exercise - Add exercise to session
sessionsRouter.post('/:version/:date/:index/exercise', async (req, res, next) => {
  try {
    const exercise = req.body as Exercise
    const index = parseInt(req.params.index, 10)

    if (!exercise || !exercise.name) {
      return res.status(400).json({
        data: null,
        error: 'Invalid exercise data',
      })
    }

    const newExercise: Exercise = {
      ...exercise,
      failed: exercise.failed ?? false,
    }

    await sessionController.addExercise(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      newExercise
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// PATCH /api/sessions/:version/:date/:index/exercise/:exerciseIndex - Update exercise field
sessionsRouter.patch('/:version/:date/:index/exercise/:exerciseIndex', async (req, res, next) => {
  try {
    const { field, value } = req.body
    const index = parseInt(req.params.index, 10)
    const exerciseIndex = parseInt(req.params.exerciseIndex, 10)

    if (!field || value === undefined) {
      return res.status(400).json({
        data: null,
        error: 'Missing field or value in request body',
      })
    }

    await sessionController.updateExerciseField(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      exerciseIndex,
      field as keyof Exercise,
      value
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})

// DELETE /api/sessions/:version/:date/:index/exercise/:exerciseIndex - Remove exercise
sessionsRouter.delete('/:version/:date/:index/exercise/:exerciseIndex', async (req, res, next) => {
  try {
    const index = parseInt(req.params.index, 10)
    const exerciseIndex = parseInt(req.params.exerciseIndex, 10)

    await sessionController.removeExercise(
      req.effectivePk!,
      req.params.version,
      req.params.date,
      index,
      exerciseIndex
    )
    res.json({ data: { success: true }, error: null })
  } catch (err) {
    next(err)
  }
})
