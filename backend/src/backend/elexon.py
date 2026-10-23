import asyncio
from datetime import date, datetime, time, timedelta

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import (
    CACHED_LEAD_TIMES,
    ELEXON_API_BASE_URL,
    ELEXON_TIMEOUT_SECONDS,
    FORECAST_HORIZON_HOURS,
)
from .db_service import actuals_service, forecasts_service
from .utils import (
    UTC,
    chunk_dates,
    chunk_datetimes,
    from_db,
    hourly_intervals,
    iso_z,
    parse_iso,
    require_utc,
    settlement_date_for,
)


class ElexonError(RuntimeError):
    """Raised when an Elexon request cannot be completed."""


class SyncStats(BaseModel):
    """Counts and windows produced by a data sync."""

    fetched_from_elexon: bool = False
    fetched_forecast_rows: int = 0
    fetched_actual_rows: int = 0
    windows: list[dict] = Field(default_factory=list)

    def extend(self, other: "SyncStats") -> None:
        """Merge another sync result into this one."""
        self.fetched_from_elexon = self.fetched_from_elexon or other.fetched_from_elexon
        self.fetched_forecast_rows += other.fetched_forecast_rows
        self.fetched_actual_rows += other.fetched_actual_rows
        self.windows.extend(other.windows)


_sync_lock = asyncio.Lock()


async def _request_json(
    client: httpx.AsyncClient, dataset: str, params: dict[str, str]
) -> list[dict]:
    """Fetch a dataset chunk with retries and return its JSON rows."""
    url = f"{ELEXON_API_BASE_URL}/{dataset}/stream"
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = await client.get(url, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                last_error = ElexonError(
                    f"{dataset} returned HTTP {response.status_code}"
                )
            elif response.status_code >= 400:
                raise ElexonError(
                    f"{dataset} returned HTTP {response.status_code}: "
                    f"{response.text[:200]}"
                )
            else:
                payload = response.json()
                if not isinstance(payload, list):
                    raise ElexonError(f"{dataset} returned an unexpected payload")
                return payload
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc

        if attempt < 2:
            await asyncio.sleep(1.5 * (attempt + 1))

    raise ElexonError(f"{dataset} request failed: {last_error}")


async def _fetch_forecasts(publish_from: datetime, publish_to: datetime) -> list[dict]:
    """Fetch and deduplicate WINDFOR rows for a publication window."""
    rows: dict[tuple[datetime, datetime], dict] = {}
    chunks = list(chunk_datetimes(publish_from, publish_to))

    async with httpx.AsyncClient(timeout=ELEXON_TIMEOUT_SECONDS) as client:
        payloads = await asyncio.gather(
            *[
                _request_json(
                    client,
                    "WINDFOR",
                    {
                        "publishDateTimeFrom": iso_z(chunk_start),
                        "publishDateTimeTo": iso_z(chunk_end),
                    },
                )
                for chunk_start, chunk_end in chunks
            ]
        )

    for payload in payloads:
        for item in payload:
            if item.get("dataset") != "WINDFOR":
                continue
            generation = item.get("generation")
            if not isinstance(generation, (int, float)):
                continue
            try:
                start_time = parse_iso(str(item["startTime"]))
                publish_time = parse_iso(str(item["publishTime"]))
            except (KeyError, TypeError, ValueError):
                continue
            rows[(start_time, publish_time)] = {
                "start_time": start_time,
                "publish_time": publish_time,
                "generation_mw": float(generation),
            }

    return list(rows.values())


async def _fetch_actuals(start_date: date, end_date: date) -> list[dict]:
    """Fetch and deduplicate national WIND actuals for a date range."""
    rows: dict[datetime, dict] = {}
    chunks = list(chunk_dates(start_date, end_date))

    async with httpx.AsyncClient(timeout=ELEXON_TIMEOUT_SECONDS) as client:
        payloads = await asyncio.gather(
            *[
                _request_json(
                    client,
                    "FUELHH",
                    {
                        "settlementDateFrom": chunk_start.isoformat(),
                        "settlementDateTo": chunk_end.isoformat(),
                        "fuelType": "WIND",
                    },
                )
                for chunk_start, chunk_end in chunks
            ]
        )

    for payload in payloads:
        for item in payload:
            if item.get("dataset") != "FUELHH":
                continue
            if str(item.get("fuelType", "")).upper() != "WIND":
                continue
            generation = item.get("generation")
            if not isinstance(generation, (int, float)):
                continue
            try:
                start_time = parse_iso(str(item["startTime"]))
                publish_time = parse_iso(str(item["publishTime"]))
                settlement_date = date.fromisoformat(str(item["settlementDate"]))
                settlement_period = int(item["settlementPeriod"])
            except (KeyError, TypeError, ValueError):
                continue

            existing = rows.get(start_time)
            if existing is not None and existing["publish_time"] >= publish_time:
                continue
            rows[start_time] = {
                "start_time": start_time,
                "publish_time": publish_time,
                "settlement_date": settlement_date,
                "settlement_period": settlement_period,
                "generation_mw": float(generation),
            }

    return list(rows.values())


def _forecast_targets_missing(
    session: Session, start: datetime, end: datetime, leads: list[int]
) -> list[datetime]:
    """Return targets without cached rows for every required lead."""
    rows = forecasts_service.coverage(session, start, end, leads)

    covered: dict[datetime, set[int]] = {}
    for start_time, lead_time_hours in rows:
        key = from_db(start_time)
        if key is not None:
            covered.setdefault(key, set()).add(lead_time_hours)

    required = set(leads)
    return [
        interval
        for interval in hourly_intervals(start, end)
        if not required.issubset(covered.get(interval, set()))
    ]


def _time_blocks(values: list[datetime]) -> list[tuple[datetime, datetime]]:
    """Group sorted hourly timestamps into half-open contiguous blocks."""
    if not values:
        return []

    blocks: list[tuple[datetime, datetime]] = []
    block_start = values[0]
    previous = values[0]

    for value in values[1:]:
        if value - previous > timedelta(hours=1):
            blocks.append((block_start, previous + timedelta(hours=1)))
            block_start = value
        previous = value

    blocks.append((block_start, previous + timedelta(hours=1)))
    return blocks


def _date_blocks(values: list[date]) -> list[tuple[date, date]]:
    """Group sorted dates into inclusive contiguous blocks."""
    if not values:
        return []

    blocks: list[tuple[date, date]] = []
    block_start = values[0]
    previous = values[0]

    for value in values[1:]:
        if value - previous > timedelta(days=1):
            blocks.append((block_start, previous))
            block_start = value
        previous = value

    blocks.append((block_start, previous))
    return blocks


def _build_forecast_selections(
    rows: list[dict], start: datetime, end: datetime
) -> list[dict]:
    """Build one selected forecast row per target and supported lead."""
    grouped: dict[datetime, list[tuple[datetime, float]]] = {}
    for row in rows:
        grouped.setdefault(row["start_time"], []).append(
            (row["publish_time"], row["generation_mw"])
        )

    selections: list[dict] = []
    for target in hourly_intervals(start, end):
        publications = grouped.get(target, [])
        for lead_time_hours in CACHED_LEAD_TIMES:
            cutoff = target - timedelta(hours=lead_time_hours)
            eligible = [
                (publish_time, generation_mw)
                for publish_time, generation_mw in publications
                if publish_time <= cutoff
            ]
            if eligible:
                publish_time, generation_mw = max(
                    eligible, key=lambda item: item[0]
                )
                selections.append(
                    {
                        "start_time": target,
                        "lead_time_hours": lead_time_hours,
                        "publish_time": publish_time,
                        "generation_mw": generation_mw,
                        "status": "ok",
                    }
                )
            else:
                selections.append(
                    {
                        "start_time": target,
                        "lead_time_hours": lead_time_hours,
                        "publish_time": None,
                        "generation_mw": None,
                        "status": "missing",
                    }
                )

    return selections


async def _sync_forecasts(
    session: Session,
    start: datetime,
    end: datetime,
    lead_time_hours: int | None,
    force: bool,
) -> SyncStats:
    """Fetch and cache forecast selections for missing target blocks."""
    start = require_utc(start)
    end = require_utc(end)
    leads = (
        [lead_time_hours]
        if lead_time_hours is not None
        else CACHED_LEAD_TIMES
    )
    stats = SyncStats()
    missing = (
        list(hourly_intervals(start, end))
        if force
        else _forecast_targets_missing(session, start, end, leads)
    )
    if not missing:
        return stats

    stats.fetched_from_elexon = True
    for block_start, block_end in _time_blocks(missing):
        publish_from = block_start - timedelta(hours=FORECAST_HORIZON_HOURS)
        publish_to = block_end
        rows = await _fetch_forecasts(publish_from, publish_to)
        selections = _build_forecast_selections(rows, block_start, block_end)
        forecasts_service.upsert_selections(session, selections)
        stats.fetched_forecast_rows += len(rows)
        stats.windows.append(
            {
                "dataset": "WINDFOR",
                "range_start": publish_from,
                "range_end": publish_to,
                "rows": len(rows),
            }
        )
    return stats


async def _sync_actuals(
    session: Session, start_date: date, end_date: date, force: bool
) -> SyncStats:
    """Fetch and cache actual generation for missing settlement dates."""
    stats = SyncStats()
    dates = [
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    ]
    if force:
        missing = dates
    else:
        cached = actuals_service.cached_settlement_dates(
            session, start_date, end_date
        )
        missing = [item for item in dates if item not in cached]
    if not missing:
        return stats

    stats.fetched_from_elexon = True
    for block_start, block_end in _date_blocks(missing):
        rows = await _fetch_actuals(block_start, block_end)
        actuals_service.upsert(session, rows)
        stats.fetched_actual_rows += len(rows)
        stats.windows.append(
            {
                "dataset": "FUELHH",
                "range_start": datetime.combine(
                    block_start, time.min, tzinfo=UTC
                ),
                "range_end": datetime.combine(
                    block_end + timedelta(days=1), time.min, tzinfo=UTC
                ),
                "rows": len(rows),
            }
        )
    return stats


async def ensure_data(
    session: Session,
    start: datetime,
    end: datetime,
    lead_time_hours: int | None = None,
    force: bool = False,
) -> SyncStats:
    """Ensure cached selections and actuals cover a request."""
    start = require_utc(start)
    end = require_utc(end)
    actual_start = settlement_date_for(start)
    actual_end = settlement_date_for(end - timedelta(seconds=1))

    async with _sync_lock:
        stats = await _sync_forecasts(
            session,
            start,
            end,
            lead_time_hours,
            force,
        )
        stats.extend(await _sync_actuals(session, actual_start, actual_end, force))
        return stats
