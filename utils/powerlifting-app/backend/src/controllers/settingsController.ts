import { Request, Response } from 'express'
import { getSettings, updateNickname, validateNickname, invalidateCache } from '../services/userSettings'
import { AppError } from '../middleware/errorHandler'

export async function getSettingsHandler(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    throw new AppError('Not authenticated', 401)
  }

  const settings = await getSettings(req.user.discord_id)
  if (!settings) {
    throw new AppError('Settings not found', 404)
  }

  res.json({ data: settings })
}

export async function updateNicknameHandler(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    throw new AppError('Not authenticated', 401)
  }

  const { nickname } = req.body
  if (typeof nickname !== 'string' || !validateNickname(nickname)) {
    throw new AppError('Invalid nickname: must be 2-32 chars, lowercase alphanumeric, hyphens, underscores only', 400)
  }

  const settings = await updateNickname(req.user.discord_id, nickname)
  invalidateCache(req.user.discord_id)
  res.json({ data: settings })
}
