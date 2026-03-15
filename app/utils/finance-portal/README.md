# Finance Portal

Full-stack web application for managing and visualizing personal financial state.
Serves as the editable UI layer over `if-finance` DynamoDB table.
Agent reads this data before every finance-related response.

## Tech Stack

- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS
- **Backend**: Node.js 20 + Express 5 + TypeScript
- **Database**: DynamoDB (table: `if-finance`)
- **State Management**: Zustand

## Quick Start

### Prerequisites

- Node.js 20+
- npm or yarn
- AWS account with DynamoDB access

### Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   ```bash
   # Backend
   cp backend/.env.example backend/.env
   # AWS credentials are automatically picked up from the instance IAM role

   # Frontend
   cp frontend/.env.example frontend/.env
   ```

3. **Create DynamoDB table:**
   Run the table creation script from the main project:
   ```bash
   cd ../../../scripts
   ./create_dynamo_tables.sh
   ```

4. **Seed initial data (optional):**
   ```bash
   ./seed_finance.sh
   ```

### Development

Run both frontend and backend:
```bash
npm run dev
```

Or run separately:
```bash
# Backend only (port 3002)
npm run dev:backend

# Frontend only (port 5173)
npm run dev:frontend
```

### Build

```bash
npm run build
```

## Project Structure

```
finance-portal/
├── packages/types/          # Shared TypeScript types
│   └── src/index.ts         # FinanceSnapshot, CreditCard, etc.
├── backend/                 # Express API server
│   ├── src/
│   │   ├── server.ts        # Main server entry
│   │   ├── routes/          # API route definitions
│   │   ├── controllers/     # Request handlers
│   │   ├── db/dynamodb.ts   # DynamoDB operations
│   │   └── middleware/      # Error handling
│   └── .env.example
├── frontend/                # React application
│   ├── src/
│   │   ├── store/           # Zustand state management
│   │   ├── api/             # API client
│   │   ├── pages/           # Page components
│   │   ├── components/      # Reusable components
│   │   └── utils/           # Formatters, helpers
│   └── .env.example
└── package.json             # Workspace root
```

## Features

- 📊 **Dashboard** — Net worth, monthly surplus, utilization at a glance
- 💳 **Accounts** — Credit cards, LOCs, loans: balances, limits, APR, payment targets
- 📈 **Investments** — Holdings per account, allocation vs target, watchlist
- 💸 **Cashflow** — Fixed expenses, debt payments, savings, variable budget, surplus
- 🎯 **Goals** — Short/medium/long-term with progress bars and deadlines
- 🧾 **Tax & Insurance** — RRSP/TFSA room, insurance gaps, tax notes
- 🕓 **Version History** — View and restore previous snapshots

## API Endpoints

### Snapshot (versioned)
- `GET  /api/finance/current`         — Resolves pointer → returns latest version
- `PUT  /api/finance`                 — Saves full snapshot (increments version)
- `GET  /api/finance/versions`        — Lists all versions
- `GET  /api/finance/versions/:sk`    — Returns specific version

### Accounts (surgical updates)
- `PATCH /api/accounts/credit-cards/:id`
- `PATCH /api/accounts/loc/:id`
- `PATCH /api/accounts/loans/:id`

### Investments
- `PATCH /api/investments/:accountId/holdings/:ticker`
- `PUT   /api/investments/:accountId/watchlist`
- `PATCH /api/investments/:accountId/target-allocation`

### Cashflow
- `PUT  /api/cashflow`               — Replace full cashflow, recalculates totals

## Key Design Principles

1. **Versioning on every full save** — PATCH endpoints update directly without creating new versions. PUT /api/finance always creates a new version.

2. **Totals computed server-side** — `total_fixed`, `total_debt_payments`, `total_outflow`, `monthly_surplus` are recalculated on every PUT/PATCH.

3. **Utilization computed server-side** — `utilization_pct` on credit cards is derived from `balance_owing / credit_limit`.

4. **No ticker price fetching** — Portal does not call Yahoo Finance. User manually updates `current_price`. The agent has MCP tools for live prices.

5. **EditableField pattern** — Every number is click-to-edit inline. Click value → input → save/cancel.

## Environment Variables

### Backend (.env)
```bash
# AWS credentials are picked up from the instance IAM role
AWS_REGION=ca-central-1
IF_FINANCE_TABLE_NAME=if-finance
IF_OPERATOR_PK=operator
PORT=3002
```

### Frontend (.env)
```bash
VITE_API_URL=http://localhost:3002
```

Note: Port 3002 to avoid collision with health portal (3001).
