const IF_API_URL = process.env.IF_API_URL || 'http://if-agent-api.if-portals.svc.cluster.local:8000'
const AGENT_MODEL = process.env.AGENT_MODEL || 'if-prototype'

function extractJson(text: string): any {
  const match = text.match(/\{[\s\S]*\}|\[[\s\S]*\]/)
  if (!match) throw new Error(`No JSON in tool response: ${text.slice(0, 200)}`)
  return JSON.parse(match[0])
}

/**
 * Invoke a Python tool directly via the Agent API.
 */
export async function invokeToolDirect(
  toolName: string,
  args: Record<string, unknown>,
): Promise<any> {
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
  const body: any = await response.json()
  const rawContent: string = body?.choices?.[0]?.message?.content ?? ''
  return extractJson(rawContent)
}
