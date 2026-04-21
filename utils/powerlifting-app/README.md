# Powerlifting App

Training tracking and analytics portal. Data is managed by the `powerlifting_coach` specialist (reads) and the `health_write` specialist (writes). Stores to DynamoDB `if-health`.

## Tech stack

- **Frontend** — React 19, Vite, TypeScript, Mantine, Zustand, Recharts, react-router-dom, dnd-kit
- **Backend** — Node.js, Express 5, TypeScript, AWS SDK v3 (DynamoDB, S3)
- **Storage** — DynamoDB single-table (`if-health`), S3 (video — not yet wired)
- **Shared types** — `packages/types/` (TypeScript workspace package)

## Ports

| Service | Port |
|---------|------|
| Frontend (Vite dev) | 5173 |
| Backend (Express) | 3001 |

In production served on port 3005 via Kubernetes.

## Directory layout

```
powerlifting-app/
├── backend/src/
│   ├── server.ts          # Express entry point
│   ├── routes/            # Route handlers
│   ├── controllers/       # Business logic
│   ├── db/                # DynamoDB operations
│   ├── services/          # Shared services
│   ├── ai/                # AI reasoning tools (fatigue, correlation, evaluation)
│   └── utils/
├── frontend/src/
│   ├── main.tsx           # Vite entry
│   ├── App.tsx
│   ├── pages/             # Route-level components
│   ├── components/        # Shared components
│   ├── store/             # Zustand state
│   ├── constants/         # Formula descriptions and thresholds
│   └── utils/
└── packages/types/        # Shared TypeScript types
```

## Running locally

```bash
# From powerlifting-app/
npm install

npm run dev:backend    # Express on :3001
npm run dev:frontend   # Vite on :5173 (proxies /api/* to :3001)

npm run build          # Build all workspaces
npm run typecheck      # Type-check all workspaces
```

## Key features

- Session logging (sets, reps, kg, RPE, failed-set flags, bodyweight)
- Competition management (attempts, results, weight class)
- Program phases + planned vs logged session compliance
- Analytics: DOTS, e1RM (RPE table or Epley), Theil-Sen progression slope, ACWR, INOL, fatigue index, readiness score
- AI reasoning layer: fatigue profile estimation, accessory correlation analysis, full-block program evaluation
- Formula definitions and thresholds: `frontend/src/constants/formulaDescriptions.ts`
