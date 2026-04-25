import { Router } from 'express'
import { invokeToolDirect } from '../utils/agent'

export const analyticsRouter = Router()

// GET /api/analytics/analysis/weekly?weeks=N&block=X
analyticsRouter.get('/analysis/weekly', async (req, res) => {
  try {
    const weeks = parseInt(req.query.weeks as string) || 1
    const block = (req.query.block as string) || 'current'
    const today = new Date().toISOString().slice(0, 10)
    try {
      await invokeToolDirect('health_snapshot_competition_projection', {
        date: today,
        version: 'current',
        allow_retrospective: false,
        pk: req.effectivePk,
      })
    } catch (snapshotErr) {
      console.warn('Failed to snapshot competition projections before weekly analysis:', snapshotErr)
    }
    const data = await invokeToolDirect('weekly_analysis', { weeks, block, refresh_program: true, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// GET /api/analytics/correlation?weeks=N&block=X&refresh=bool
analyticsRouter.get('/correlation', async (req, res) => {
  try {
    const weeks = parseInt(req.query.weeks as string) || 4
    const block = (req.query.block as string) || 'current'
    const refresh = req.query.refresh === 'true'
    const data = await invokeToolDirect('correlation_analysis', { weeks, block, refresh, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/fatigue-profile/estimate
analyticsRouter.post('/fatigue-profile/estimate', async (req, res) => {
  try {
    const exercise = req.body?.exercise ?? req.body
    const data = await invokeToolDirect('fatigue_profile_estimate', { exercise, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/muscle-groups/estimate
analyticsRouter.post('/muscle-groups/estimate', async (req, res) => {
  try {
    const body = req.body ?? {}
    const exercise = body.exercise ?? body
    const lift_profiles = Array.isArray(body.lift_profiles) ? body.lift_profiles : undefined
    const data = await invokeToolDirect('muscle_group_estimate', {
      exercise,
      ...(lift_profiles ? { lift_profiles } : {}),
      pk: req.effectivePk,
    })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/lift-profile/review
analyticsRouter.post('/lift-profile/review', async (req, res) => {
  try {
    const profile = req.body?.profile ?? req.body
    const data = await invokeToolDirect('lift_profile_review', { profile, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/lift-profile/rewrite
analyticsRouter.post('/lift-profile/rewrite', async (req, res) => {
  try {
    const profile = req.body?.profile ?? req.body
    const data = await invokeToolDirect('lift_profile_rewrite', { profile, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/lift-profile/estimate-stimulus
analyticsRouter.post('/lift-profile/estimate-stimulus', async (req, res) => {
  try {
    const profile = req.body?.profile ?? req.body
    const data = await invokeToolDirect('lift_profile_estimate_stimulus', { profile, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/lift-profile/rewrite-and-estimate
analyticsRouter.post('/lift-profile/rewrite-and-estimate', async (req, res) => {
  try {
    const profile = req.body?.profile ?? req.body
    const data = await invokeToolDirect('lift_profile_rewrite_and_estimate', { profile, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// GET /api/analytics/program-evaluation?refresh=bool
analyticsRouter.get('/program-evaluation', async (req, res) => {
  try {
    const refresh = req.query.refresh === 'true'
    const data = await invokeToolDirect('program_evaluation', { refresh, pk: req.effectivePk })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})
