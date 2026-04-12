import { Router } from 'express'

export const analyticsRouter = Router()

const IF_API_URL =
  process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'
const AGENT_MODEL = process.env.AGENT_MODEL || 'if-prototype'

function extractJson(text: string): unknown {
  const match = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/)
  if (!match) throw new Error(`No JSON in tool response: ${text.slice(0, 200)}`)
  return JSON.parse(match[0])
}

async function invokeToolDirect(
  toolName: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  const content = `/${toolName} ${JSON.stringify(args)}`
  const response = await fetch(`${IF_API_URL}/v1/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Direct-Tool-Invoke': 'true',
    },
    body: JSON.stringify({
      model: AGENT_MODEL,
      messages: [{ role: 'user', content }],
    }),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Agent API error ${response.status}: ${text}`)
  }
  const body = await response.json()
  const rawContent: string = body?.choices?.[0]?.message?.content ?? ''
  return extractJson(rawContent)
}

// GET /api/analytics/analysis/weekly?weeks=N&block=X
analyticsRouter.get('/analysis/weekly', async (req, res) => {
  try {
    const weeks = parseInt(req.query.weeks as string) || 1
    const block = (req.query.block as string) || 'current'
    const data = await invokeToolDirect('weekly_analysis', { weeks, block })
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
    const data = await invokeToolDirect('correlation_analysis', { weeks, block, refresh })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})

// POST /api/analytics/fatigue-profile/estimate
analyticsRouter.post('/fatigue-profile/estimate', async (req, res) => {
  try {
    const data = await invokeToolDirect('fatigue_profile_estimate', { exercise: req.body })
    res.json({ data, error: null })
  } catch (err) {
    res.status(502).json({ data: null, error: `Tool invocation error: ${err}` })
  }
})
