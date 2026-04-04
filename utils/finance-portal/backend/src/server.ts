import express from 'express';
import cors from 'cors';
import { errorHandler, notFoundHandler } from './middleware/errorHandler.js';
import financeRoutes from './routes/finance.js';
import accountsRoutes from './routes/accounts.js';
import investmentsRoutes from './routes/investments.js';
import versionsRoutes from './routes/versions.js';
import cashflowRoutes from './routes/cashflow.js';

const app = express();
const PORT = process.env.PORT || 3002;

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// Request logging
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  next();
});

// Health check
app.get('/health', (_req, res) => {
  res.json({
    status: 'healthy',
    service: 'finance-portal-backend',
    timestamp: new Date().toISOString(),
  });
});

// API Routes
app.use('/api/finance', financeRoutes);
app.use('/api/accounts', accountsRoutes);
app.use('/api/investments', investmentsRoutes);
app.use('/api/versions', versionsRoutes);
app.use('/api/cashflow', cashflowRoutes);

// Error handling
app.use(notFoundHandler);
app.use(errorHandler);

// Start server
app.listen(PORT, () => {
  console.log(`Finance Portal Backend running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`API Base: http://localhost:${PORT}/api`);
});

export default app;
