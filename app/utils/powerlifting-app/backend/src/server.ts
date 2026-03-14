import express from 'express'
import cors from 'cors'
import { programsRouter } from './routes/programs'
import { sessionsRouter } from './routes/sessions'
import { exercisesRouter } from './routes/exercises'
import { maxesRouter } from './routes/maxes'
import { weightRouter } from './routes/weight'
import { errorHandler } from './middleware/errorHandler'

const app = express()

// Middleware
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:5173',
}))
app.use(express.json())

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() })
})

// API routes
app.use('/api/programs', programsRouter)
app.use('/api/sessions', sessionsRouter)
app.use('/api/exercises', exercisesRouter)
app.use('/api/maxes', maxesRouter)
app.use('/api/weight', weightRouter)

// Error handler
app.use(errorHandler)

// 404 handler
app.use((_req, res) => {
  res.status(404).json({
    data: null,
    error: 'Not found',
  })
})

const PORT = process.env.PORT || 3001

app.listen(PORT, () => {
  console.log(`Powerlifting API running on port ${PORT}`)
  console.log(`Health check: http://localhost:${PORT}/health`)
})
