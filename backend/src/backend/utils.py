from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from .config import MAX_RANGE_DAYS
from .schemas import ResponseMeta, ToleranceResponse

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.orm import Session

    from .analysis import ToleranceResult
    from .elexon import SyncStats

UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")


def require_utc(value: datetime) -> datetime:
    """Return an aware datetime normalized to UTC, rejecting naive input."""
    if value.tzinfo is None:
        raise ValueError("timezone offset required")
    return value.astimezone(UTC)


def to_db(value: datetime) -> datetime:
    """Convert an aware datetime to naive UTC for SQLite storage."""
    return require_utc(value).replace(tzinfo=None)


def from_db(value: datetime | None) -> datetime | None:
    """Convert a SQLite datetime back to aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_z(value: datetime) -> str:
    """Format an aware datetime as an ISO-8601 UTC string ending in Z."""
    return require_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def hourly_intervals(start: datetime, end: datetime) -> Iterator[datetime]:
    """Yield whole-hour UTC timestamps in the half-open [start, end) range."""
    cursor = require_utc(start).replace(minute=0, second=0, microsecond=0)
    if cursor < start:
        cursor += timedelta(hours=1)
    while cursor < end:
        yield cursor
        cursor += timedelta(hours=1)


def settlement_date_for(value: datetime) -> date:
    """Return the Europe/London settlement date for a UTC timestamp."""
    return require_utc(value).astimezone(LONDON).date()


def nearest_rank(values: list[float], percentile: float) -> float | None:
    """Return the nearest-rank percentile, or None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def chunk_datetimes(
    start: datetime, end: datetime, days: int = 7
) -> Iterator[tuple[datetime, datetime]]:
    """Yield half-open datetime windows of at most the given number of days."""
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + timedelta(days=days), end)
        yield cursor, chunk_end
        cursor = chunk_end


def chunk_dates(start: date, end: date, days: int = 7) -> Iterator[tuple[date, date]]:
    """Yield inclusive date windows of at most the given number of days."""
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def validate_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """Validate and normalize a request range, raises HTTP 422 on failure."""
    try:
        start = require_utc(start)
        end = require_utc(end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if start >= end:
        raise HTTPException(status_code=422, detail="end must be after start")
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise HTTPException(
            status_code=422,
            detail=f"range must be {MAX_RANGE_DAYS} days or less",
        )
    return start, end


def validate_lead(lead_time_hours: int, allowed: list[int]) -> None:
    """Validate a lead time against the allowed values, raising HTTP 422."""
    if lead_time_hours not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"lead_time_hours must be one of {allowed}",
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database tables at application startup."""
    from .database import init_db

    init_db()
    yield


async def ensure_request_data(
    session: Session,
    start: datetime,
    end: datetime,
    lead_time_hours: int | None = None,
    force: bool = False,
) -> SyncStats:
    """Ensure cached request data."""
    from .elexon import ElexonError, ensure_data

    try:
        return await ensure_data(
            session,
            start,
            end,
            lead_time_hours=lead_time_hours,
            force=force,
        )
    except ElexonError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def build_response_meta(stats: SyncStats) -> ResponseMeta:
    """Build API response metadata from sync statistics."""
    return ResponseMeta(
        fetched_from_elexon=stats.fetched_from_elexon,
        fetched_forecast_rows=stats.fetched_forecast_rows,
        fetched_actual_rows=stats.fetched_actual_rows,
        generated_at=datetime.now(UTC),
    )


def build_tolerance_response(
    tolerance: ToleranceResult,
    metric: Literal["mae", "p90"],
    start: datetime,
    end: datetime,
    lead_time_hours: int,
) -> ToleranceResponse:
    """Build the tolerance response model and explanatory note."""
    if not tolerance.available:
        note = (
            "No matched forecast and actual intervals in the visible range for "
            "this lead time."
        )
    else:
        note = (
            f"Based on {tolerance.sample_count} matched intervals in the "
            "visible range."
        )

    return ToleranceResponse(
        metric=metric,
        start=start,
        end=end,
        lead_time_hours=lead_time_hours,
        value_percent=tolerance.value_percent(),
        metric_mw=tolerance.metric_mw,
        mean_forecast_mw=tolerance.mean_forecast_mw,
        sample_count=tolerance.sample_count,
        available=tolerance.available,
        note=note,
    )
