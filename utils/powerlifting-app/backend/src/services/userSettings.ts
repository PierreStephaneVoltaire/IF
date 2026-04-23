import { GetCommand, PutCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'

export interface UserSettings {
  discord_id: string
  discord_username: string
  avatar_url: string | null
  nickname: string
  created_at: string
  updated_at: string
}

const CACHE_TTL_MS = 60_000
const cache = new Map<string, { settings: UserSettings; expires: number }>()

function settingsPk(discordId: string): string {
  return `user#${discordId}`
}

const NICKNAME_RE = /^[a-z0-9_-]{2,32}$/

export function validateNickname(nickname: string): boolean {
  return NICKNAME_RE.test(nickname)
}

function sanitizeUsername(username: string): string {
  return username.toLowerCase().replace(/[^a-z0-9_-]/g, '_').slice(0, 32)
}

export async function getSettings(discordId: string): Promise<UserSettings | null> {
  const cached = cache.get(discordId)
  if (cached && cached.expires > Date.now()) return cached.settings

  const result = await docClient.send(new GetCommand({
    TableName: TABLE,
    Key: { pk: settingsPk(discordId), sk: 'settings' },
  }))

  if (!result.Item) return null

  const settings = result.Item as unknown as UserSettings
  cache.set(discordId, { settings, expires: Date.now() + CACHE_TTL_MS })
  return settings
}

export async function getOrCreateSettings(
  discordId: string,
  discordUsername: string,
  avatarUrl: string | null,
): Promise<UserSettings> {
  const existing = await getSettings(discordId)
  if (existing) return existing

  const now = new Date().toISOString()
  const settings: UserSettings = {
    discord_id: discordId,
    discord_username: discordUsername,
    avatar_url: avatarUrl,
    nickname: sanitizeUsername(discordUsername),
    created_at: now,
    updated_at: now,
  }

  await docClient.send(new PutCommand({
    TableName: TABLE,
    Item: { pk: settingsPk(discordId), sk: 'settings', ...settings },
    ConditionExpression: 'attribute_not_exists(pk)',
  })).catch(() => {
    // Race: another request created it first. Fetch instead.
  })

  cache.set(discordId, { settings, expires: Date.now() + CACHE_TTL_MS })
  return settings
}

export async function updateNickname(discordId: string, nickname: string): Promise<UserSettings> {
  if (!validateNickname(nickname)) {
    throw new Error('Invalid nickname: must be 2-32 chars, lowercase alphanumeric, hyphens, underscores only')
  }

  const now = new Date().toISOString()
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: settingsPk(discordId), sk: 'settings' },
    UpdateExpression: 'SET #nick = :nick, updated_at = :now',
    ConditionExpression: 'attribute_exists(pk)',
    ExpressionAttributeNames: { '#nick': 'nickname' },
    ExpressionAttributeValues: { ':nick': nickname, ':now': now },
  }))

  cache.delete(discordId)
  return getSettings(discordId) as Promise<UserSettings>
}

export function invalidateCache(discordId: string): void {
  cache.delete(discordId)
}
