import { Router } from 'express'

export const analyticsRouter = Router()

const IF_API_URL = process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'

// GET /api/analytics/analysis/weekly?weeks=N
analyticsRouter.get('/analysis/weekly', async (req, res) => {
  try {
    const weeks = req.query.weeks || '1'
    const upstream = await fetch(`${IF_API_URL}/v1/health/analysis/weekly?weeks=${weeks}`)

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
