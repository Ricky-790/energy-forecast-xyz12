from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db_service import actuals_service, forecasts_service
from .utils import from_db, hourly_intervals, nearest_rank, require_utc


class SelectedForecast(BaseModel):
    start_time: datetime
    publish_time: datetime | None
    forecast_mw: float | None
    status: Literal["ok", "missing"]


class ActualPoint(BaseModel):
    start_time: datetime
    publish_time: datetime
    generation_mw: float
    settlement_periods: list[int]


class ToleranceResult(BaseModel):
    metric_mw: float | None
    mean_forecast_mw: float | None
    sample_count: int

    @property
    def available(self) -> bool:
        return (
            self.sample_count > 0
            and self.metric_mw is not None
            and self.mean_forecast_mw is not None
            and self.mean_forecast_mw != 0
        )

    def value_percent(self) -> float | None:
        if not self.available or self.mean_forecast_mw is None:
            return None
        percent = self.metric_mw / abs(self.mean_forecast_mw) * 100
        return max(1.0, min(100.0, percent))


def select_forecasts(
    session: Session, start: datetime, end: datetime, lead_time_hours: int
) -> list[SelectedForecast]:
    start = require_utc(start)
    end = require_utc(end)
    rows = forecasts_service.select_selections(
        session, start, end, lead_time_hours
    )
    by_start: dict[datetime, tuple[datetime | None, float | None, str]] = {}
    for start_time, publish_time, generation_mw, status in rows:
        key = from_db(start_time)
        if key is not None:
            by_start[key] = (publish_time, generation_mw, status)

    selected: list[SelectedForecast] = []
    for interval_start in hourly_intervals(start, end):
        row = by_start.get(interval_start)
        if row is None:
            selected.append(
                SelectedForecast(
                    start_time=interval_start,
                    publish_time=None,
                    forecast_mw=None,
                    status="missing",
                )
            )
            continue

        publish_time, generation_mw, status = row
        publish_time = from_db(publish_time)
        if status != "ok" or publish_time is None or generation_mw is None:
            selected.append(
                SelectedForecast(
                    start_time=interval_start,
                    publish_time=None,
                    forecast_mw=None,
                    status="missing",
                )
            )
            continue

        selected.append(
            SelectedForecast(
                start_time=interval_start,
                publish_time=publish_time,
                forecast_mw=generation_mw,
                status="ok",
            )
        )

    return selected


def load_actuals(
    session: Session, start: datetime, end: datetime
) -> dict[datetime, ActualPoint]:
    """Load actuals per hour, averaging the two half-hourly settlement periods."""
    rows = actuals_service.select_range(session, start, end)

    latest: dict[datetime, tuple[datetime, float, int]] = {}
    for start_time, publish_time, generation_mw, settlement_period in rows:
        key = from_db(start_time)
        if key is None or publish_time is None:
            continue
        published = from_db(publish_time)
        existing = latest.get(key)
        if existing is None or published >= existing[0]:
            latest[key] = (published, generation_mw, settlement_period)

    grouped: dict[datetime, list[tuple[datetime, float, int]]] = {}
    for key, point in latest.items():
        hour = key.replace(minute=0, second=0, microsecond=0)
        grouped.setdefault(hour, []).append(point)

    return {
        hour: ActualPoint(
            start_time=hour,
            publish_time=max(point[0] for point in points),
            generation_mw=sum(point[1] for point in points) / len(points),
            settlement_periods=sorted(point[2] for point in points),
        )
        for hour, points in grouped.items()
    }


def compute_tolerance(
    session: Session,
    start: datetime,
    end: datetime,
    lead_time_hours: int,
    metric: Literal["mae", "p90"],
) -> ToleranceResult:
    start = require_utc(start)
    end = require_utc(end)
    forecasts = select_forecasts(session, start, end, lead_time_hours)
    actuals = load_actuals(session, start, end)

    errors: list[float] = []
    forecasts_used: list[float] = []
    for item in forecasts:
        if item.status != "ok" or item.forecast_mw is None:
            continue
        actual = actuals.get(item.start_time)
        if actual is None:
            continue
        errors.append(abs(item.forecast_mw - actual.generation_mw))
        forecasts_used.append(abs(item.forecast_mw))

    sample_count = len(errors)
    if sample_count == 0:
        return ToleranceResult(
            metric_mw=None,
            mean_forecast_mw=None,
            sample_count=0,
        )

    metric_mw = (
        sum(errors) / sample_count
        if metric == "mae"
        else nearest_rank(errors, 0.9)
    )
    return ToleranceResult(
        metric_mw=metric_mw,
        mean_forecast_mw=sum(forecasts_used) / sample_count,
        sample_count=sample_count,
    )


def build_accuracy(
    session: Session, start: datetime, end: datetime, lead_time_hours: int
) -> tuple[list[dict], dict]:
    start = require_utc(start)
    end = require_utc(end)
    forecasts = select_forecasts(session, start, end, lead_time_hours)
    actuals = load_actuals(session, start, end)

    intervals: list[dict] = []
    matched_forecast: list[float] = []
    matched_actual: list[float] = []
    percentage_errors: list[float] = []
    missing_forecast = 0
    missing_actual = 0
    missing_both = 0

    for forecast in forecasts:
        actual = actuals.get(forecast.start_time)
        if forecast.status == "missing" and actual is None:
            status = "missing_both"
            missing_both += 1
        elif forecast.status == "missing":
            status = "missing_forecast"
            missing_forecast += 1
        elif actual is None:
            status = "missing_actual"
            missing_actual += 1
        else:
            status = "ok"

        error = None
        absolute_error = None
        if status == "ok" and forecast.forecast_mw is not None and actual is not None:
            error = forecast.forecast_mw - actual.generation_mw
            absolute_error = abs(error)
            matched_forecast.append(forecast.forecast_mw)
            matched_actual.append(actual.generation_mw)
            if actual.generation_mw != 0:
                percentage_errors.append(error / actual.generation_mw * 100)

        lead_hours = None
        if forecast.publish_time is not None:
            lead_hours = (
                forecast.start_time - forecast.publish_time
            ).total_seconds() / 3600

        intervals.append(
            {
                "start_time": forecast.start_time,
                "publish_time": forecast.publish_time,
                "forecast_lead_hours": lead_hours,
                "forecast_mw": forecast.forecast_mw,
                "actual_mw": actual.generation_mw if actual is not None else None,
                "actual_publish_time": actual.publish_time if actual is not None else None,
                "settlement_periods": (
                    actual.settlement_periods if actual is not None else []
                ),
                "error_mw": error,
                "absolute_error_mw": absolute_error,
                "status": status,
            }
        )

    sample_count = len(matched_forecast)
    forecast_total = sum(matched_forecast)
    actual_total = sum(matched_actual)
    metrics = {
        "peak_error_mw": max(matched_forecast) - max(matched_actual)
        if sample_count
        else None,
        "mean_error_mw": (forecast_total - actual_total) / sample_count
        if sample_count
        else None,
        "total_energy_error_mwh": forecast_total - actual_total
        if sample_count
        else None,
        "mean_percentage_error": sum(percentage_errors) / len(percentage_errors)
        if percentage_errors
        else None,
        "interval_count": len(intervals),
        "matched_count": sample_count,
        "missing_forecast_count": missing_forecast + missing_both,
        "missing_actual_count": missing_actual + missing_both,
        "missing_both_count": missing_both,
        "excluded_count": len(intervals) - sample_count,
    }
    return intervals, metrics
