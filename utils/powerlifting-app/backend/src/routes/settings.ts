import { Router } from 'express'
import { getSettingsHandler, updateNicknameHandler } from '../controllers/settingsController'

export const settingsRouter = Router()

settingsRouter.get('/', getSettingsHandler)
settingsRouter.put('/nickname', updateNicknameHandler)
