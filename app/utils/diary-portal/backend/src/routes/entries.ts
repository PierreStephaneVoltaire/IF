import { Router } from 'express'
import {
  writeEntry,
  getActiveEntries,
  getEntry,
  updateEntry,
  deleteEntry,
  countActiveEntries,
} from '../controllers/entriesController'

export const entriesRouter = Router()

/**
 * GET /api/entries - Get all active diary entries
 */
entriesRouter.get('/', async (req, res, next) => {
  try {
    const limit = req.query.limit ? parseInt(req.query.limit as string) : 50
    const entries = await getActiveEntries(limit)

    res.json({
      data: entries,
      error: null,
    })
  } catch (err) {
    next(err)
  }
})

/**
 * GET /api/entries/:sk - Get a single entry
 */
entriesRouter.get('/:sk', async (req, res, next) => {
  try {
    const { sk } = req.params
    const entry = await getEntry(sk)

    if (!entry) {
      return res.status(404).json({
        data: null,
        error: 'Entry not found',
      })
    }

    res.json({
      data: entry,
      error: null,
    })
  } catch (err) {
    next(err)
  }
})

/**
 * POST /api/entries - Write a new diary entry
 */
entriesRouter.post('/', async (req, res, next) => {
  try {
    const { content } = req.body

    if (!content || typeof content !== 'string') {
      return res.status(400).json({
        data: null,
        error: 'Missing or invalid content field',
      })
    }

    if (content.length > 10000) {
      return res.status(400).json({
        data: null,
        error: 'Content exceeds 10,000 character limit',
      })
    }

    await writeEntry(content)

    // Get updated count after write
    const entryCount = await countActiveEntries()

    res.json({
      data: {
        ok: true,
        entry_count: entryCount,
      },
      error: null,
    })
  } catch (err) {
    next(err)
  }
})

/**
 * PATCH /api/entries/:sk - Update an entry
 */
entriesRouter.patch('/:sk', async (req, res, next) => {
  try {
    const { sk } = req.params
    const { content } = req.body

    if (!content || typeof content !== 'string') {
      return res.status(400).json({
        data: null,
        error: 'Missing or invalid content field',
      })
    }

    if (content.length > 10000) {
      return res.status(400).json({
        data: null,
        error: 'Content exceeds 10,000 character limit',
      })
    }

    await updateEntry(sk, content)

    // Return updated entry
    const entry = await getEntry(sk)

    res.json({
      data: entry,
      error: null,
    })
  } catch (err) {
    next(err)
  }
})

/**
 * DELETE /api/entries/:sk - Delete an entry
 */
entriesRouter.delete('/:sk', async (req, res, next) => {
  try {
    const { sk } = req.params
    await deleteEntry(sk)

    res.json({
      data: { ok: true },
      error: null,
    })
  } catch (err) {
    next(err)
  }
})
