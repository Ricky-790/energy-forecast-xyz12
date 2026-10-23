import { useEffect, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import type { ResponseMeta } from "./types";

export const LEAD_TIMES = Array.from({ length: 13 }, (_, index) => 24 + index * 2);
export const ACCURACY_LEAD_TIMES = Array.from(
  { length: 19 },
  (_, index) => 12 + index * 2,
);

export type Theme = "light" | "dark";

export interface ChartColors {
  grid: string;
  axis: string;
  forecast: string;
  actual: string;
  band: string;
}

export function chartColors(theme: Theme): ChartColors {
  if (theme === "dark") {
    return {
      grid: "#27272a",
      axis: "#a1a1aa",
      forecast: "#60a5fa",
      actual: "#f87171",
      band: "#4ade80",
    };
  }
  return {
    grid: "#e4e4e7",
    axis: "#71717a",
    forecast: "#2563eb",
    actual: "#dc2626",
    band: "#16a34a",
  };
}

export function toUtcIso(value: string): string {
  if (!value) {
    return value;
  }
  return value.length === 16 ? `${value}:00Z` : `${value}Z`;
}

export function formatDateTime(value: string | null, withDate = true): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  const datePart = date.toLocaleDateString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const timePart = date.toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return withDate ? `${datePart}, ${timePart}` : timePart;
}

export function formatAxisTime(value: string, rangeDays: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  if (rangeDays > 2) {
    return date.toLocaleDateString("en-GB", {
      timeZone: "UTC",
      day: "2-digit",
      month: "short",
    });
  }
  return date.toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function formatNumber(value: number | null, digits = 0): string {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-GB", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

export function formatMw(value: number | null, digits = 0): string {
  if (value === null) {
    return "—";
  }
  return `${formatNumber(value, digits)} MW`;
}

export function formatSignedMw(value: number | null, digits = 0): string {
  if (value === null) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, digits)} MW`;
}

export function formatSignedMwh(value: number | null, digits = 0): string {
  if (value === null) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, digits)} MWh`;
}

export function formatSignedPercent(value: number | null, digits = 1): string {
  if (value === null) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatNumber(value, digits)}%`;
}

export function formatSettlementPeriods(values: number[]): string {
  return values.length ? values.join("–") : "—";
}

export function formatLead(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)} h`;
}

export interface EnergyStats {
  peak: number | null;
  mean: number | null;
  total: number | null;
}

export function energyStats(values: (number | null)[]): EnergyStats {
  const numbers = values.filter(
    (value): value is number => value !== null && !Number.isNaN(value),
  );
  if (numbers.length === 0) {
    return { peak: null, mean: null, total: null };
  }
  const total = numbers.reduce((sum, value) => sum + value, 0);
  return {
    peak: Math.max(...numbers),
    mean: total / numbers.length,
    total,
  };
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function EnergyBlock({
  label,
  stats,
}: {
  label: string;
  stats: EnergyStats;
}) {
  return (
    <div className="energy-block">
      <span className="energy-label">{label}</span>
      <div className="energy-grid">
        <div className="energy-cell">
          <span className="energy-key">Peak MW</span>
          <span className="energy-value">{formatNumber(stats.peak)}</span>
        </div>
        <div className="energy-cell">
          <span className="energy-key">Mean MW</span>
          <span className="energy-value">{formatNumber(stats.mean)}</span>
        </div>
        <div className="energy-cell">
          <span className="energy-key">Total MWh</span>
          <span className="energy-value">{formatNumber(stats.total)}</span>
        </div>
      </div>
    </div>
  );
}

export function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-row">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}

export function DataSourceNote({ meta }: { meta: ResponseMeta }) {
  const source = meta.fetched_from_elexon
    ? `Fetched ${meta.fetched_forecast_rows.toLocaleString(
        "en-GB",
      )} forecast rows and ${meta.fetched_actual_rows.toLocaleString(
        "en-GB",
      )} actual rows from Elexon, then cached in SQLite.`
    : "";
  return (
    <p className="data-note">
      {source} Matching: {meta.matching}.
    </p>
  );
}

export function clampPercent(value: number): number {
  if (Number.isNaN(value)) {
    return 1;
  }
  return Math.max(1, Math.min(100, value));
}

export function useChartZoom(count: number): {
  ref: RefObject<HTMLDivElement | null>;
  range: [number, number];
} {
  const [range, setRange] = useState<[number, number]>([
    0,
    Math.max(0, count - 1),
  ]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRange([0, Math.max(0, count - 1)]);
  }, [count]);

  useEffect(() => {
    const node = ref.current;
    if (!node || count <= 2) {
      return;
    }
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = node.getBoundingClientRect();
      const ratio =
        rect.width > 0
          ? Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
          : 0.5;
      setRange(([start, end]) => {
        const size = end - start + 1;
        const zoomOut = event.deltaY > 0;
        const scaled = zoomOut ? Math.ceil(size * 1.3) : Math.floor(size / 1.3);
        const next = Math.max(2, Math.min(count, scaled));
        if (next === size) {
          return [start, end];
        }
        const anchor = start + ratio * (size - 1);
        const nextStart = Math.round(anchor - ratio * (next - 1));
        const clamped = Math.max(0, Math.min(count - next, nextStart));
        return [clamped, clamped + next - 1];
      });
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [count]);

  return { ref, range };
}

export function Loading({ label }: { label: string }) {
  return (
    <div className="loading">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="error-box">
      <div>
        <strong>Could not load data.</strong>
        <p>{message}</p>
      </div>
      <button className="button" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
