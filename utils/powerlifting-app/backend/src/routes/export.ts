import { Router } from 'express'

export const exportRouter = Router()

const IF_API_URL = process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'
// Stable chat_id → predictable sandbox directory for the exported file
const EXPORT_CHAT_ID = process.env.EXPORT_CHAT_ID || 'pl-export'

exportRouter.get('/xlsx', async (_req, res) => {
  try {
    // Step 1: invoke the export tool via X-Direct-Tool-Invoke
    const invokeRes = await fetch(`${IF_API_URL}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Direct-Tool-Invoke': 'true',
      },
      body: JSON.stringify({
        model: 'if-prototype-a1',  // must match API_MODEL_NAME in config
        chat_id: EXPORT_CHAT_ID,
        messages: [{ role: 'user', content: '/export_program_history {}' }],
      }),
    })

    if (!invokeRes.ok) {
      return res.status(invokeRes.status).json({ data: null, error: 'Tool invocation failed' })
    }

    const invokeJson = await invokeRes.json()
    // The tool response is a JSON payload on the first line
    const content: string = invokeJson?.choices?.[0]?.message?.content ?? ''
    let filename = 'program_history.xlsx'
    try {
      const parsed = JSON.parse(content.split('\n')[0])
      if (parsed.filename) filename = parsed.filename
    } catch { /* use default filename */ }

    // Step 2: fetch the binary from the sandbox
    // Note: the files endpoint has NO /v1/ prefix
    const fileRes = await fetch(
      `${IF_API_URL}/files/sandbox/${EXPORT_CHAT_ID}/${filename}`
    )

    if (!fileRes.ok) {
      return res.status(fileRes.status).json({ data: null, error: 'File not found in sandbox' })
    }

    const contentType =
      fileRes.headers.get('content-type') ||
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    res.setHeader('Content-Type', contentType)
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`)

    const arrayBuffer = await fileRes.arrayBuffer()
    res.end(Buffer.from(arrayBuffer))
  } catch (err) {
    res.status(502).json({ data: null, error: `Proxy error: ${err}` })
  }
})