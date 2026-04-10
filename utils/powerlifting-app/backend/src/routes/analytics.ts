import { Router } from 'express'

export const analyticsRouter = Router()

const IF_API_URL = process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'

// GET /api/analytics/analysis/weekly?weeks=N&block=X
analyticsRouter.get('/analysis/weekly', async (req, res) => {
  try {
    const weeks = req.query.weeks || '1'
    const block = req.query.block || 'current'
    const upstream = await fetch(`${IF_API_URL}/v1/health/analysis/weekly?weeks=${weeks}&block=${encodeURIComponent(block as string)}`)

    if (!upstream.ok) {
      const text = await upstream.text()
      return res.status(upstream.status).json({ data: null, error: text })
    }

    const data = await upstream.json()
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Proxy error: ${err}` })
  }
})

// POST /api/analytics/fatigue-profile/estimate
analyticsRouter.post('/fatigue-profile/estimate', async (req, res) => {
  try {
    const upstream = await fetch(`${IF_API_URL}/v1/health/fatigue-profile/estimate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req.body),
    })

    if (!upstream.ok) {
      const text = await upstream.text()
      return res.status(upstream.status).json({ data: null, error: text })
    }

    const data = await upstream.json()
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Proxy error: ${err}` })
  }
})
