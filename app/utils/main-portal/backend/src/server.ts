import 'dotenv/config'
import express from 'express'
import cors from 'cors'
import { hubRouter } from './routes/hub'
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
app.use('/api/hub', hubRouter)

// Error handler
app.use(errorHandler)

// 404 handler
app.use((_req, res) => {
  res.status(404).json({
    data: null,
    error: 'Not found',
  })
})

const PORT = process.env.PORT || 3000

app.listen(PORT, () => {
  console.log(`Main Portal Hub running on port ${PORT}`)
  console.log(`Health check: http://localhost:${PORT}/health`)
  console.log(`Hub status: http://localhost:${PORT}/api/hub/status`)
})
