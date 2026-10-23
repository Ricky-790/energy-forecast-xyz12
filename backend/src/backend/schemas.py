from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer, field_validator, model_validator

ToleranceMetric = Literal["mae", "p90"]
ForecastStatus = Literal["ok", "missing"]
AccuracyStatus = Literal["ok", "missing_forecast", "missing_actual", "missing_both"]


def _serialize_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str)]


class SyncRequest(BaseModel):
    start: datetime
    end: datetime
    force: bool = False

    @field_validator("start", "end")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timezone offset required")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_range(self) -> "SyncRequest":
        if self.start >= self.end:
            raise ValueError("end must be after start")
        return self


class ResponseMeta(BaseModel):
    fetched_from_elexon: bool
    fetched_forecast_rows: int
    fetched_actual_rows: int
    generated_at: UtcDateTime
    forecast_interval_minutes: int = 60
    actual_interval_minutes: int = 30
    matching: str = "hourly forecast vs mean of both settlement periods"


class ToleranceResponse(BaseModel):
    timezone: str = "UTC"
    metric: ToleranceMetric
    start: UtcDateTime
    end: UtcDateTime
    lead_time_hours: int
    value_percent: float | None
    metric_mw: float | None
    mean_forecast_mw: float | None
    sample_count: int
    available: bool
    note: str | None = None


class ForecastInterval(BaseModel):
    start_time: UtcDateTime
    publish_time: UtcDateTime | None
    forecast_lead_hours: float | None
    forecast_mw: float | None
    status: ForecastStatus


class ForecastSummary(BaseModel):
    interval_count: int
    selected_count: int
    missing_count: int


class ForecastResponse(BaseModel):
    timezone: str = "UTC"
    lead_time_hours: int
    start: UtcDateTime
    end: UtcDateTime
    intervals: list[ForecastInterval]
    summary: ForecastSummary
    meta: ResponseMeta


class AccuracyInterval(BaseModel):
    start_time: UtcDateTime
    publish_time: UtcDateTime | None
    forecast_lead_hours: float | None
    forecast_mw: float | None
    actual_mw: float | None
    actual_publish_time: UtcDateTime | None
    settlement_periods: list[int]
    error_mw: float | None
    absolute_error_mw: float | None
    status: AccuracyStatus


class AccuracyMetrics(BaseModel):
    peak_error_mw: float | None
    mean_error_mw: float | None
    total_energy_error_mwh: float | None
    mean_percentage_error: float | None
    interval_count: int
    matched_count: int
    missing_forecast_count: int
    missing_actual_count: int
    missing_both_count: int
    excluded_count: int


class AccuracyResponse(BaseModel):
    timezone: str = "UTC"
    lead_time_hours: int
    start: UtcDateTime
    end: UtcDateTime
    metrics: AccuracyMetrics
    intervals: list[AccuracyInterval]
    meta: ResponseMeta


class SyncWindow(BaseModel):
    dataset: str
    range_start: UtcDateTime
    range_end: UtcDateTime
    rows: int


class SyncResponse(BaseModel):
    start: UtcDateTime
    end: UtcDateTime
    force: bool
    fetched_from_elexon: bool
    forecast_rows: int
    actual_rows: int
    windows: list[SyncWindow]
    duration_ms: int


class HealthResponse(BaseModel):
    status: str
    database: str
    forecasts_rows: int
    actuals_rows: int


class DataCounts(BaseModel):
    forecasts: int
    actuals: int


class DataStatusResponse(BaseModel):
    database: str
    counts: DataCounts
    forecast_start: UtcDateTime | None
    forecast_end: UtcDateTime | None
    actual_start: UtcDateTime | None
    actual_end: UtcDateTime | None
