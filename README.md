# Wind Forecast Dashboard

A dashboard for UK wind generation. It shows the latest Elexon wind forecast
available before a chosen lead-time cutoff, and compares it with actual
generation. The target period is January 2026. Timestamps are UTC and generation
is in MW.

**Live app:** https://energy-forecast-xyz12.vercel.app/

## Backend

Python, FastAPI, SQLAlchemy, and SQLite. Data comes from the Elexon `WINDFOR`
and `FUELHH` datasets and is cached in SQLite on demand.

| File / directory | Purpose |
| --- | --- |
| `main.py` | FastAPI app setup, CORS, and all API endpoints |
| `src/backend/config.py` | Loads environment variables and supplies default values |
| `src/backend/database.py` | SQLite engine, sessions, and table creation |
| `src/backend/db_schemas.py` | Forecast and actual table definitions |
| `src/backend/db_service.py` | All reads and writes for the two tables |
| `src/backend/elexon.py` | Fetches Elexon data and fills the cache on demand |
| `src/backend/analysis.py` | Forecast selection, actual matching, and error metrics |
| `src/backend/schemas.py` | Pydantic request and response models |
| `src/backend/utils.py` | Validation, time helpers, and request data sync |
| `data/` | Local SQLite cache, created at runtime |

Start the backend:

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn main:app --reload
```

API docs: http://localhost:8000/docs

## Frontend

React, TypeScript, Vite, and Recharts.

| File / directory | Purpose |
| --- | --- |
| `src/App.tsx` | App shell, tabs, collapsible sidebar, and theme switching |
| `src/ForecastScreen.tsx` | Forecast screen with chart, tolerance band, and table |
| `src/AccuracyScreen.tsx` | Review screen with forecast vs actual and error stats |
| `src/api.ts` | Backend API client |
| `src/types.ts` | TypeScript types for the API responses |
| `src/ui.tsx` | Shared components, formatters, and chart zoom |
| `src/styles.css` | Light and dark theme styling |
| `.env` | Backend base URL (`VITE_API_BASE_URL`) |

Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

## Deployment

The frontend and backend are deployed as two Vercel projects. Set
`VITE_API_BASE_URL` in the frontend to the backend URL, and `CORS_ORIGINS` in the
backend to the frontend origin. On Vercel the backend caches to `/tmp/wind.db`,
so its SQLite cache is ephemeral and refills on demand.

To run both locally with Docker, use `docker compose up --build`
(app on http://localhost:3000).

## AI usage

- AI wrote the db operations and schemas, the frontend: React screens, charts, tables, theme, and styling.
- All features were run against live January 2026 Elexon data before acceptance.
