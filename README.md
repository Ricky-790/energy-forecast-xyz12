# Wind Forecast Decision Support

A small web app for a UK energy trading team. It shows the latest Elexon
national wind forecast available before a chosen day-ahead lead-time cutoff, and
compares those selected forecasts with actual wind generation.

The target delivery period is January 2026. The app can fetch other periods if
Elexon has data for them.

## What it does

Screen A, day-ahead forecast:

- Choose a delivery start, delivery end, lead time, and a tolerance band width.
- For every hourly delivery interval, the backend computes
  `cutoff = start_time - lead_time`.
- It selects the latest forecast with `publishTime <= cutoff`.
- If no forecast is eligible, the interval is marked missing. A later forecast
  is never substituted.
- The chart shows the selected forecast and a shaded band drawn at
  `forecast ± (width% of forecast)`. The table shows the selected publication
  time, actual publication lead, generation, and bounds.

Screen B, forecast accuracy:

- Uses the same forecast selection rule.
- Averages the two half-hourly settlement periods of each hour into one hourly
  actual.
- Shows forecast versus actual, signed error, absolute error, peak error, mean
  error, total energy error, mean percentage error, and missing intervals.
- A **Calculate tolerance** button asks the backend for the MAE or P90 of the
  errors in the visible range and writes the result into the band width box.

## Stack

- Backend: Python, FastAPI, SQLAlchemy, SQLite.
- Frontend: React, TypeScript, Vite, Recharts.
- Data: Elexon `WINDFOR` and `FUELHH` stream endpoints.

## Data and caching

SQLite starts empty. Tables are created on backend startup.

When a request arrives, the backend:

1. Works out the target delivery hours and the required lead time.
2. Checks the selected-forecast cache for those target and lead-time rows.
3. Fetches publication windows from Elexon only for target blocks with no
   cached selection row.
4. Selects the latest eligible publication for every supported lead, writes one
   row per target and lead, and stores an explicit `missing` row when no
   publication is early enough.
5. Checks actual settlement dates and fetches only dates with no cached actuals.
6. Builds the response from SQLite.

A repeated request for the same lead and covered target range does not call
Elexon again, including when the correct result is a missing forecast. A request
for another lead fetches only target blocks that do not already have a selection
for that lead. `POST /api/data/sync` with `force: true` refetches a range and
updates corrected records.

Forecast selections deduplicate on
`(dataset, start_time, lead_time_hours)`. Each row stores `publish_time`,
`generation_mw`, and `status` (`ok` or `missing`). Actuals deduplicate on
`(dataset, start_time, fuel_type)` and keep the latest publication. A settlement
date with any cached actual rows is treated as fetched.

The first request for a new range can take several seconds. Later requests are
served from SQLite. If the cache predates this selected-forecast schema, delete
`backend/data/wind.db` or run `docker compose down -v` before starting.

## Forecast selection

For each target interval:

```text
cutoff = start_time - lead_time_hours
eligible = forecasts where publish_time <= cutoff
selected = eligible with the latest publish_time
```

The cutoff is applied per interval, not once for the whole range. The selected
publication may be earlier than the cutoff because Elexon publishes every few
hours. The UI shows the actual publication lead.

## Granularity and matching

Elexon `WINDFOR` forecasts are hourly. `FUELHH` actuals are half-hourly.

Actuals are stored as published and aggregated at read time. The two settlement
periods that cover an hour are averaged into one hourly actual, which is then
joined to the forecast for that same hour. A forecast at 10:00 is compared with
the mean of the actuals at 10:00 and 10:30. Forecast values are not copied or
interpolated, and the interval table shows both settlement periods for each
hour.

## Tolerance band

The band is a percentage of the forecast:
`lower = forecast × (1 - width/100)`, `upper = forecast × (1 + width/100)`.
The width is entered by hand (1 to 100) and is drawn as a shaded envelope around
the forecast line on both screens.

`GET /api/tolerance` computes a suggested width from the errors in the requested
range and lead time:

- Typical error: MAE of the matched absolute errors.
- Wider range: P90 of the matched absolute errors, nearest-rank percentile.
- Width: `metric_mw / mean(|forecast_mw|) × 100`, clamped to 1–100.
- Samples: only hours with both a selected forecast and an hourly actual count.

The value is computed from the same range the user is viewing, so it moves when
the range or lead time changes. It is a historical error range, not a promise
about future generation.

## Metrics

```text
actual_mw = mean(actuals at :00 and :30 for the hour)
error_mw = forecast_mw - actual_mw
absolute_error_mw = abs(error_mw)
peak_error_mw = max(forecast_mw) - max(actual_mw)
mean_error_mw = mean(forecast_mw) - mean(actual_mw)
total_energy_error_mwh = sum(forecast_mw) - sum(actual_mw)
mean_percentage_error = mean(error_mw / actual_mw × 100)
```

Each hourly value is one hour, so summing MW gives MWh. Positive errors mean
overforecasting, negative errors mean underforecasting. The error statistics use
only matched hours, and missing values are excluded rather than treated as zero.

## Run locally

Backend:

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn main:app --reload
```

API docs: http://localhost:8000/docs

Frontend:

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

The API base URL comes from `frontend/.env` (`VITE_API_BASE_URL`). When the
variable is missing, the app falls back to `http://localhost:8000`.

## Run with Docker

```bash
docker compose up --build
```

App: http://localhost:3000

The backend also listens on http://localhost:8000. SQLite is stored in the
`wind-data` Docker volume. Remove it with:

```bash
docker compose down -v
```

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `ELEXON_API_BASE_URL` | `https://data.elexon.co.uk/bmrs/api/v1/datasets` | Elexon dataset base URL |
| `DATABASE_PATH` | `data/wind.db` | SQLite file path |
| `CORS_ORIGINS` | local dev origins | Comma-separated allowed origins |
| `ELEXON_TIMEOUT_SECONDS` | `60` | Upstream request timeout |

## API

### Health

```bash
curl http://localhost:8000/api/health
```

### Data status

```bash
curl http://localhost:8000/api/data/status
```

### Sync a range

```bash
curl -X POST http://localhost:8000/api/data/sync \
  -H 'Content-Type: application/json' \
  -d '{"start":"2026-01-01T00:00:00Z","end":"2026-02-01T00:00:00Z","force":false}'
```

### Forecasts

```bash
curl 'http://localhost:8000/api/forecasts?start=2026-01-15T00:00:00Z&end=2026-01-16T00:00:00Z&lead_time_hours=24'
```

### Accuracy

```bash
curl 'http://localhost:8000/api/accuracy?start=2026-01-15T00:00:00Z&end=2026-01-30T00:00:00Z&lead_time_hours=24'
```

### Tolerance

```bash
curl 'http://localhost:8000/api/tolerance?start=2026-01-15T00:00:00Z&end=2026-01-30T00:00:00Z&lead_time_hours=24&metric=p90'
```

Supported lead times are 24 to 48 hours in 2-hour steps on Screen A, and 12 to
48 hours in 2-hour steps on Screen B. Timestamps must include a UTC offset. The
date pickers are limited to 1–30 January 2026. Ranges are limited to 31 days.

## Tests and checks

Backend syntax and import check:

```bash
cd backend
.venv/bin/python -m compileall main.py src
.venv/bin/python -c "import main"
```

Frontend typecheck and production build:

```bash
cd frontend
npm run build
```

Manual acceptance checks used against January 2026 data:

- Every selected forecast publication is at or before its interval cutoff.
- 24h lead selects 744 of 744 January hourly intervals.
- 48h lead selects 589 of 744, with 155 missing early-January intervals.
- Full January 24h accuracy: 744 matched intervals, peak error about 3,370 MW,
  mean error about 1,855 MW, total energy error about 1,379,821 MWh, mean
  percentage error about 18.5%.
- Each hourly actual is the mean of its two half-hourly settlement periods, and
  the interval table shows both settlement periods.
- Repeated syncs leave row counts unchanged and create no duplicate rows.

## Assumptions and limitations

- National `WIND` actuals only. Other fuel types are filtered out.
- January 2026 is the target period. Other ranges work only if Elexon returns
  data.
- All timestamps are stored and displayed in UTC. January 2026 is GMT in
  London, so local London time matches UTC for this dataset.
- Forecasts are hourly and actuals are half-hourly. Each hourly actual is the
  mean of the two settlement periods.
- SQLite is a single-instance cache. A multi-instance deployment would need a
  shared database or a single writer.
- No authentication is included. This is a first-version internal tool.
- The tolerance band is retrospective. It is not a forecast guarantee.

## Deployment notes

The repository includes Dockerfiles and Docker Compose.

For Heroku, Render, Fly.io, or another container host, attach a persistent disk
and point `DATABASE_PATH` at it. SQLite needs durable storage to keep the cache
across restarts.

If the frontend is served from a separate origin, set `VITE_API_BASE_URL` (in
`frontend/.env` or the deployment environment) to the backend URL before
building. Without it the app calls `http://localhost:8000`.

### Vercel

Deploy the backend as its own project with **Root Directory** set to `backend`.
The FastAPI entrypoint is `main.py`, and dependencies come from
`pyproject.toml`/`uv.lock`.

- `src/backend` is declared as the package in `pyproject.toml`
  (`module-root = "src"`, `module-name = "backend"`). `main.py` also adds that
  `src` directory to `sys.path`, because Vercel only puts the project root and
  its vendor directory on the import path, not a `src` layout.
- On Vercel the default `DATABASE_PATH` is `/tmp/wind.db`, because the
  deployment filesystem is read-only. `VERCEL=1` is set by the platform, so no
  configuration is required. The cache is ephemeral and per instance, so a cold
  start fetches the range again.
- Set `CORS_ORIGINS` to the frontend origin, for example
  `https://your-frontend.vercel.app`. The defaults only cover localhost.
- Set `VITE_API_BASE_URL` in the frontend project to the backend URL (for
  example `https://your-backend.vercel.app`) and redeploy the frontend after
  changing it.
- The first request for a month-long range calls Elexon many times. If the
  platform times out, use a smaller range or raise the function duration in the
  Vercel project settings.


## AI tools

AI tools were used to help design and implement this application. The code,
data model, selection logic, and UI were reviewed and verified against live
January 2026 Elexon data.
