import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { errorHandler } from './middleware/errorHandler';
import { wsClients } from './controllers/proposalsController';
import proposalsRouter from './routes/proposals';
import directivesRouter from './routes/directives';

const app = express();
const PORT = process.env.PORT || 3004;

// Middleware
app.use(cors());
app.use(express.json());

// Request logging
app.use((req, _res, next) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  next();
});

// Routes
app.get('/health', (_req, res) => {
  res.json({
    status: 'healthy',
    service: 'proposals-portal-backend',
    timestamp: new Date().toISOString(),
  });
});

app.use('/api/proposals', proposalsRouter);
app.use('/api/directives', directivesRouter);

// 404 handler
app.use((_req, res) => {
  res.status(404).json({
    status: 'error',
    message: 'Not found',
  });
});

// Error handler
app.use(errorHandler);

// Create HTTP server
const server = createServer(app);

// WebSocket server
const wss = new WebSocketServer({ server, path: '/ws' });

wss.on('connection', (ws: WebSocket) => {
  console.log('WebSocket client connected');
  wsClients.add(ws);

  ws.on('close', () => {
    console.log('WebSocket client disconnected');
    wsClients.delete(ws);
  });

  ws.on('error', (error) => {
    console.error('WebSocket error:', error);
    wsClients.delete(ws);
  });

  // Send connection confirmation
  ws.send(JSON.stringify({ type: 'connected', message: 'WebSocket connected' }));
});

// Start server
server.listen(PORT, () => {
  console.log(`Proposals Portal Backend running on port ${PORT}`);
  console.log(`WebSocket available at ws://localhost:${PORT}/ws`);
});

export { app, server, wss };
