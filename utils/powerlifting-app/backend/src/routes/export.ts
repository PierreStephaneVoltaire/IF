import { Router } from 'express'

export const exportRouter = Router()

const IF_API_URL = process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'

// GET /api/export/xlsx — stream the Excel file from Python backend
exportRouter.get('/xlsx', async (_req, res) => {
  try {
    const upstream = await fetch(`${IF_API_URL}/v1/health/export/xlsx`)

    if (!upstream.ok) {
      return res.status(upstream.status).json({ data: null, error: 'Export failed' })
    }

    const contentType = upstream.headers.get('content-type') ||
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    res.setHeader('Content-Type', contentType)
    res.setHeader('Content-Disposition', 'attachment; filename="program_history.xlsx"')

    const arrayBuffer = await upstream.arrayBuffer()
    res.end(Buffer.from(arrayBuffer))
  } catch (err) {
    res.status(502).json({ data: null, error: `Proxy error: ${err}` })
  }
})
