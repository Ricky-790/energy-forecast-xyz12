import type {
  AccuracyResponse,
  ForecastResponse,
  HealthResponse,
  SyncResponse,
  ToleranceMetric,
  ToleranceResponse,
} from "./types";

const API_BASE = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    signal,
    headers: {
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item: { msg?: string }) => item.msg ?? JSON.stringify(item))
          .join("; ");
      }
    } catch {
      message = `${response.status} ${response.statusText}`;
    }
    throw new ApiError(message, response.status);  }

  return (await response.json()) as T;
}

export function getForecasts(
  params: {
    start: string;
    end: string;
    lead: number;
  },
  signal?: AbortSignal,
): Promise<ForecastResponse> {
  const query = new URLSearchParams({
    start: params.start,
    end: params.end,
    lead_time_hours: String(params.lead),
  });
  return request<ForecastResponse>(`/api/forecasts?${query}`, {}, signal);
}

export function getAccuracy(
  params: {
    start: string;
    end: string;
    lead: number;
  },
  signal?: AbortSignal,
): Promise<AccuracyResponse> {
  const query = new URLSearchParams({
    start: params.start,
    end: params.end,
    lead_time_hours: String(params.lead),
  });
  return request<AccuracyResponse>(`/api/accuracy?${query}`, {}, signal);
}

export function getTolerance(
  params: {
    start: string;
    end: string;
    lead: number;
    metric: ToleranceMetric;
  },
  signal?: AbortSignal,
): Promise<ToleranceResponse> {
  const query = new URLSearchParams({
    start: params.start,
    end: params.end,
    lead_time_hours: String(params.lead),
    metric: params.metric,
  });
  return request<ToleranceResponse>(`/api/tolerance?${query}`, {}, signal);
}

export function syncData(body: {
  start: string;
  end: string;
  force: boolean;
}): Promise<SyncResponse> {
  return request<SyncResponse>("/api/data/sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health", {}, signal);
}
