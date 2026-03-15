import { Router } from 'express'
import { writeEntry, countActiveEntries } from '../controllers/entriesController'

export const entriesRouter = Router()

/**
 * POST /api/entries - Write a new diary entry
 *
 * This is the ONLY endpoint for entries.
 * There is no GET endpoint - entries are write-only from the portal.
 * The server sets the TTL (3 days), not the client.
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
