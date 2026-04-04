# Main Portal (Hub)

Lightweight hub portal that links to all domain portals and surfaces a unified at-a-glance view of system state.

## Tech Stack

- **Frontend**: React 18 + Vite + TypeScript + Tailwind CSS
- **Backend**: Node.js 20 + Express 5 + TypeScript
- **State Management**: Zustand

## Quick Start

### Backend

```bash
cd backend
cp .env.example .env
npm install
npm run dev
```

Server runs on port 3000.

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend runs on port 5173 with API proxy to backend.

## API Endpoints

### `GET /api/hub/status`

Aggregates status from all portal backends in parallel:

- `health-portal:3001/api/programs/current`
- `finance-portal:3002/api/finance/current`
- `diary-portal:3003/api/signals/latest`
- `proposals-portal:3004/api/proposals?status=pending`

Returns unified status with graceful degradation for unreachable portals.

## Environment Variables

### Backend

```bash
FINANCE_PORTAL_URL=http://localhost:3002
HEALTH_PORTAL_URL=http://localhost:3001
DIARY_PORTAL_URL=http://localhost:3003
PROPOSALS_PORTAL_URL=http://localhost:3004
PORT=3000
FRONTEND_URL=http://localhost:5173
```

### Frontend

```bash
VITE_API_URL=http://localhost:3000
```

## Port Map

| Port | Portal |
|------|--------|
| 3000 | main-portal (hub) |
| 3001 | health-portal |
| 3002 | finance-portal |
| 3003 | diary-portal |
| 3004 | proposals-portal |

## Key Design Principles

1. **Hub is thin** — Aggregates, never stores. No database access.
2. **Graceful degradation** — Unreachable portals show grey dot and "unavailable"
3. **Single page** — No navigation. The hub IS the navigation.
4. **Alerts are advisory** — Computed fresh on every request, not stored.
