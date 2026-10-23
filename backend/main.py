import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from backend.analysis import build_accuracy, compute_tolerance, select_forecasts
from backend.config import (
    CORS_ORIGINS,
    SUPPORTED_ACCURACY_LEAD_TIMES,
    SUPPORTED_LEAD_TIMES,
)
from backend.database import get_db
from backend.db_service import actuals_service, forecasts_service
from backend.schemas import (
    AccuracyInterval,
    AccuracyMetrics,
    AccuracyResponse,
    DataCounts,
    DataStatusResponse,
    ForecastInterval,
    ForecastResponse,
    ForecastSummary,
    HealthResponse,
    SyncRequest,
    SyncResponse,
    SyncWindow,
    ToleranceResponse,
)
from backend.utils import (
    build_response_meta,
    build_tolerance_response,
    ensure_request_data,
    from_db,
    lifespan,
    validate_lead,
    validate_range,
)

app = FastAPI(
    title="Wind Forecast",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health(session: Session = Depends(get_db)) -> HealthResponse:
    forecasts_rows = forecasts_service.count(session)
    actuals_rows = actuals_service.count(session)
    return HealthResponse(
        status="ok",
        database="sqlite",
        forecasts_rows=forecasts_rows,
        actuals_rows=actuals_rows,
    )


@app.get("/api/data/status", response_model=DataStatusResponse)
def data_status(session: Session = Depends(get_db)) -> DataStatusResponse:
    forecasts_rows = forecasts_service.count(session)
    actuals_rows = actuals_service.count(session)
    forecast_start, forecast_end = forecasts_service.time_bounds(session)
    actual_start, actual_end = actuals_service.time_bounds(session)

    return DataStatusResponse(
        database="sqlite",
        counts=DataCounts(forecasts=forecasts_rows, actuals=actuals_rows),
        forecast_start=from_db(forecast_start),
        forecast_end=from_db(forecast_end),
        actual_start=from_db(actual_start),
        actual_end=from_db(actual_end),
    )


@app.post("/api/data/sync", response_model=SyncResponse)
async def sync_data(
    request: SyncRequest, session: Session = Depends(get_db)
) -> SyncResponse:
    start, end = validate_range(request.start, request.end)
    started = time.perf_counter()
    stats = await ensure_request_data(session, start, end, force=request.force)
    duration_ms = int((time.perf_counter() - started) * 1000)

    return SyncResponse(
        start=start,
        end=end,
        force=request.force,
        fetched_from_elexon=stats.fetched_from_elexon,
        forecast_rows=stats.fetched_forecast_rows,
        actual_rows=stats.fetched_actual_rows,
        windows=[SyncWindow(**window) for window in stats.windows],
        duration_ms=duration_ms,
    )


@app.get("/api/forecasts", response_model=ForecastResponse)
async def forecasts(
    start: datetime,
    end: datetime,
    lead_time_hours: int = Query(24),
    session: Session = Depends(get_db),
) -> ForecastResponse:
    start, end = validate_range(start, end)
    validate_lead(lead_time_hours, SUPPORTED_LEAD_TIMES)
    stats = await ensure_request_data(
        session, start, end, lead_time_hours=lead_time_hours
    )

    selected = select_forecasts(session, start, end, lead_time_hours)

    intervals: list[ForecastInterval] = []
    missing_count = 0
    for item in selected:
        lead_hours = None
        if item.publish_time is not None:
            lead_hours = (item.start_time - item.publish_time).total_seconds() / 3600
        if item.status == "missing":
            missing_count += 1

        intervals.append(
            ForecastInterval(
                start_time=item.start_time,
                publish_time=item.publish_time,
                forecast_lead_hours=lead_hours,
                forecast_mw=item.forecast_mw,
                status=item.status,
            )
        )

    return ForecastResponse(
        lead_time_hours=lead_time_hours,
        start=start,
        end=end,
        intervals=intervals,
        summary=ForecastSummary(
            interval_count=len(intervals),
            selected_count=len(intervals) - missing_count,
            missing_count=missing_count,
        ),
        meta=build_response_meta(stats),
    )


@app.get("/api/accuracy", response_model=AccuracyResponse)
async def accuracy(
    start: datetime,
    end: datetime,
    lead_time_hours: int = Query(24),
    session: Session = Depends(get_db),
) -> AccuracyResponse:
    start, end = validate_range(start, end)
    validate_lead(lead_time_hours, SUPPORTED_ACCURACY_LEAD_TIMES)
    stats = await ensure_request_data(
        session, start, end, lead_time_hours=lead_time_hours
    )

    rows, metrics = build_accuracy(session, start, end, lead_time_hours)

    return AccuracyResponse(
        lead_time_hours=lead_time_hours,
        start=start,
        end=end,
        metrics=AccuracyMetrics(**metrics),
        intervals=[AccuracyInterval(**row) for row in rows],
        meta=build_response_meta(stats),
    )


@app.get("/api/tolerance", response_model=ToleranceResponse)
async def tolerance(
    start: datetime,
    end: datetime,
    lead_time_hours: int = Query(24),
    metric: Literal["mae", "p90"] = Query("mae"),
    session: Session = Depends(get_db),
) -> ToleranceResponse:
    start, end = validate_range(start, end)
    validate_lead(lead_time_hours, SUPPORTED_ACCURACY_LEAD_TIMES)
    await ensure_request_data(session, start, end, lead_time_hours=lead_time_hours)

    result = compute_tolerance(session, start, end, lead_time_hours, metric)
    return build_tolerance_response(result, metric, start, end, lead_time_hours)
