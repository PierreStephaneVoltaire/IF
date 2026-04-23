import { Request, Response, NextFunction } from 'express'
import jwt from 'jsonwebtoken'
import { getSettings, getOrCreateSettings } from '../services/userSettings'

declare global {
  namespace Express {
    interface Request {
      user?: { discord_id: string; username: string; avatar: string | null } | null
      effectivePk?: string
    }
  }
}

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-me'
const JWT_EXPIRY = '7d'

export interface AuthToken {
  discord_id: string
  username: string
  avatar: string | null
}

export function signToken(payload: AuthToken): string {
  return jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRY })
}

export function verifyToken(token: string): AuthToken | null {
  try {
    return jwt.verify(token, JWT_SECRET) as AuthToken
  } catch {
    return null
  }
}

export function signState(): string {
  return jwt.sign({ t: Date.now() }, JWT_SECRET, { expiresIn: '10m' })
}

export function verifyState(state: string): boolean {
  try {
    jwt.verify(state, JWT_SECRET)
    return true
  } catch {
    return false
  }
}

export async function requireUserOptional(req: Request, _res: Response, next: NextFunction): Promise<void> {
  const token = req.cookies?.pl_auth
  if (!token) {
    req.user = null
    return next()
  }

  const payload = verifyToken(token)
  if (!payload) {
    req.user = null
    return next()
  }

  req.user = { discord_id: payload.discord_id, username: payload.username, avatar: payload.avatar }
  next()
}

export async function resolvePk(req: Request, _res: Response, next: NextFunction): Promise<void> {
  if (!req.user) {
    req.effectivePk = 'operator'
    return next()
  }

  try {
    const settings = await getOrCreateSettings(
      req.user.discord_id,
      req.user.username,
      req.user.avatar,
    )
    req.effectivePk = settings.nickname
  } catch (err) {
    console.error('Failed to resolve PK for user', req.user.discord_id, err)
    req.effectivePk = 'operator'
  }

  next()
}
