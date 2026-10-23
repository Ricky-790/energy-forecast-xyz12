export type ToleranceMetric = "mae" | "p90";
export type ForecastStatus = "ok" | "missing";
export type AccuracyStatus =
  | "ok"
  | "missing_forecast"
  | "missing_actual"
  | "missing_both";

export interface ResponseMeta {
  fetched_from_elexon: boolean;
  fetched_forecast_rows: number;
  fetched_actual_rows: number;
  generated_at: string;
  forecast_interval_minutes: number;
  actual_interval_minutes: number;
  matching: string;
}

export interface ToleranceResponse {
  timezone: string;
  metric: ToleranceMetric;
  start: string;
  end: string;
  lead_time_hours: number;
  value_percent: number | null;
  metric_mw: number | null;
  mean_forecast_mw: number | null;
  sample_count: number;
  available: boolean;
  note: string | null;
}

export interface ForecastInterval {
  start_time: string;
  publish_time: string | null;
  forecast_lead_hours: number | null;
  forecast_mw: number | null;
  status: ForecastStatus;
}

export interface ForecastSummary {
  interval_count: number;
  selected_count: number;
  missing_count: number;
}

export interface ForecastResponse {
  timezone: string;
  lead_time_hours: number;
  start: string;
  end: string;
  intervals: ForecastInterval[];
  summary: ForecastSummary;
  meta: ResponseMeta;
}

export interface AccuracyInterval {
  start_time: string;
  publish_time: string | null;
  forecast_lead_hours: number | null;
  forecast_mw: number | null;
  actual_mw: number | null;
  actual_publish_time: string | null;
  settlement_periods: number[];
  error_mw: number | null;
  absolute_error_mw: number | null;
  status: AccuracyStatus;
}

export interface AccuracyMetrics {
  peak_error_mw: number | null;
  mean_error_mw: number | null;
  total_energy_error_mwh: number | null;
  mean_percentage_error: number | null;
  interval_count: number;
  matched_count: number;
  missing_forecast_count: number;
  missing_actual_count: number;
  missing_both_count: number;
  excluded_count: number;
}

export interface AccuracyResponse {
  timezone: string;
  lead_time_hours: number;
  start: string;
  end: string;
  metrics: AccuracyMetrics;
  intervals: AccuracyInterval[];
  meta: ResponseMeta;
}

export interface SyncWindow {
  dataset: string;
  range_start: string;
  range_end: string;
  rows: number;
}

export interface SyncResponse {
  start: string;
  end: string;
  force: boolean;
  fetched_from_elexon: boolean;
  forecast_rows: number;
  actual_rows: number;
  windows: SyncWindow[];
  duration_ms: number;
}

export interface HealthResponse {
  status: string;
  database: string;
  forecasts_rows: number;
  actuals_rows: number;
}
