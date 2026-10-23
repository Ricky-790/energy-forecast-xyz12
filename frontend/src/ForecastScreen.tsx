import { useEffect, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getForecasts } from "./api";
import type { ForecastResponse } from "./types";
import {
  DataSourceNote,
  EnergyBlock,
  ErrorBox,
  Field,
  LEAD_TIMES,
  Loading,
  StatRow,
  chartColors,
  clampPercent,
  energyStats,
  formatAxisTime,
  formatDateTime,
  formatLead,
  formatMw,
  formatNumber,
  toUtcIso,
  useChartZoom,
  type Theme,
} from "./ui";

interface ForecastScreenProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  theme: Theme;
}

interface ChartPoint {
  time: string;
  forecast: number | null;
  lower: number | null;
  span: number | null;
  upper: number | null;
}

function ForecastTooltip({ active, payload }: any) {
  if (!active || !payload?.length) {
    return null;
  }
  const point = payload[0].payload as ChartPoint;
  return (
    <div className="tooltip">
      <strong>{formatDateTime(point.time)} UTC</strong>
      {point.forecast === null ? (
        <span>No eligible forecast</span>
      ) : (
        <>
          <span>Forecast: {formatMw(point.forecast)}</span>
          <span>Lower bound: {formatMw(point.lower)}</span>
          <span>Upper bound: {formatMw(point.upper)}</span>
        </>
      )}
    </div>
  );
}

export default function ForecastScreen({
  sidebarOpen,
  onToggleSidebar,
  theme,
}: ForecastScreenProps) {
  const colors = chartColors(theme);
  const [start, setStart] = useState("2026-01-15T00:00");
  const [end, setEnd] = useState("2026-01-16T00:00");
  const [lead, setLead] = useState(24);
  const [tolerancePercent, setTolerancePercent] = useState(5);
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  const rangeDays = Math.max(
    0,
    (Date.parse(toUtcIso(end)) - Date.parse(toUtcIso(start))) / 86_400_000,
  );
  const rangeError = !start || !end
    ? "Start and end are required."
    : toUtcIso(end) <= toUtcIso(start)
      ? "End must be after start."
      : rangeDays > 31
        ? "Range must be 31 days or less."
        : null;

  useEffect(() => {
    if (rangeError) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    getForecasts(
      {
        start: toUtcIso(start),
        end: toUtcIso(end),
        lead,
      },
      controller.signal,
    )
      .then((response) => {
        if (active) {
          setData(response);
        }
      })
      .catch((requestError: Error) => {
        if (active && requestError.name !== "AbortError") {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [start, end, lead, reload, rangeError]);

  const band = tolerancePercent / 100;
  const chartData: ChartPoint[] =
    data?.intervals.map((interval) => {
      const forecast = interval.forecast_mw;
      const lower = forecast === null ? null : forecast * (1 - band);
      const upper = forecast === null ? null : forecast * (1 + band);
      return {
        time: interval.start_time,
        forecast,
        lower,
        span: lower !== null && upper !== null ? upper - lower : null,
        upper,
      };
    }) ?? [];

  const forecastEnergy = energyStats(
    data?.intervals.map((interval) => interval.forecast_mw) ?? [],
  );

  const { ref: chartRef, range } = useChartZoom(chartData.length);
  const visibleData = chartData.slice(range[0], range[1] + 1);
  const visibleDays = Math.max(0, (visibleData.length - 1) / 24);

  return (
    <section className={`screen ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
          <div>
            <p className="eyebrow">Controls</p>
            <h2>Forecast setup</h2>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onToggleSidebar}
            aria-label="Collapse controls"
          >
            ⟨
          </button>
        </div>
        <div className="sidebar-scroll">
          <div className="control-group">
            <h3>Date &amp; time span</h3>
            <Field label="Delivery start (UTC)">
              <input
                type="datetime-local"
                step={3600}
                min="2026-01-01T00:00"
                max="2026-01-30T23:00"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </Field>
            <Field label="Delivery end (UTC)" hint="End is exclusive.">
              <input
                type="datetime-local"
                step={3600}
                min="2026-01-01T00:00"
                max="2026-01-30T23:00"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </Field>
          </div>

          <div className="control-group">
            <h3>Lead time</h3>
            <Field label="Forecast lead time" hint="Cutoff = start - lead time.">
              <select
                value={lead}
                onChange={(event) => setLead(Number(event.target.value))}
              >
                {LEAD_TIMES.map((hours) => (
                  <option key={hours} value={hours}>
                    {hours} hours
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="control-group">
            <h3>Tolerance band</h3>
            <Field
              label="Band width (% of forecast)"
              hint="Draws a band at ± this share of the forecast."
            >
              <input
                type="number"
                min={1}
                max={100}
                step={1}
                value={tolerancePercent}
                onChange={(event) =>
                  setTolerancePercent(clampPercent(Number(event.target.value)))
                }
              />
            </Field>
          </div>

          {rangeError ? <div className="warning">{rangeError}</div> : null}
        </div>
      </aside>

      <div className="workbench">
        <div className="panel chart-panel">
          <div className="panel-head">
            <div>
              <h2>Day-ahead forecast</h2>
              <p className="panel-sub">
                Latest publication at or before each interval cutoff. UTC and MW.
                Scroll over the chart to zoom.
              </p>
            </div>
            {loading ? <span className="panel-status">Refreshing…</span> : null}
          </div>

          {error ? (
            <ErrorBox
              message={error}
              onRetry={() => setReload((value) => value + 1)}
            />
          ) : null}

          {loading && !data ? (
            <Loading label="Loading forecast data. The first request for a range may take a few seconds while Elexon data is cached in SQLite." />
          ) : null}

          {data ? (
            <div className="chart-box" ref={chartRef}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={visibleData}
                  margin={{ top: 44, right: 20, bottom: 4, left: 0 }}
                >
                  <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tickFormatter={(value) =>
                      formatAxisTime(String(value), visibleDays)
                    }
                    minTickGap={36}
                    tick={{ fill: colors.axis, fontSize: 11 }}
                  />
                  <YAxis
                    tickFormatter={(value) => formatNumber(Number(value))}
                    width={58}
                    tick={{ fill: colors.axis, fontSize: 11 }}
                    label={{
                      value: "MW",
                      angle: -90,
                      position: "insideLeft",
                      fill: colors.axis,
                      fontSize: 11,
                    }}
                  />
                  <Tooltip
                    content={(props: any) => <ForecastTooltip {...props} />}
                  />
                  <Legend
                    layout="vertical"
                    align="right"
                    verticalAlign="top"
                    iconType="plainline"
                    iconSize={12}
                    wrapperStyle={{
                      fontSize: 11,
                      color: colors.axis,
                      lineHeight: "18px",
                    }}
                  />
                  <Area
                    dataKey="lower"
                    stackId="band"
                    stroke="none"
                    fill="transparent"
                    isAnimationActive={false}
                    legendType="none"
                    name="Band base"
                  />
                  <Area
                    dataKey="span"
                    stackId="band"
                    stroke="none"
                    fill={colors.band}
                    fillOpacity={0.18}
                    isAnimationActive={false}
                    name="Tolerance band"
                  />
                  <Line
                    dataKey="forecast"
                    name="Forecast"
                    stroke={colors.forecast}
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          ) : null}

        </div>

        <div className="bottom-row">
          <div className="panel table-panel">
            <div className="panel-head">
              <div>
                <h3>Delivery intervals</h3>
                <p className="panel-sub">
                  Publication and generation values in UTC and MW.
                </p>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Start time (UTC)</th>
                    <th>Publication time (UTC)</th>
                    <th className="num">Actual lead</th>
                    <th className="num">Forecast (MW)</th>
                    <th className="num">Band (± %)</th>
                    <th className="num">Lower (MW)</th>
                    <th className="num">Upper (MW)</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.intervals.map((interval) => (
                    <tr key={interval.start_time}>
                      <td>{formatDateTime(interval.start_time)}</td>
                      <td>{formatDateTime(interval.publish_time)}</td>
                      <td className="num">
                        {formatLead(interval.forecast_lead_hours)}
                      </td>
                      <td className="num">{formatMw(interval.forecast_mw)}</td>
                      <td className="num">{`${formatNumber(tolerancePercent)}%`}</td>
                      <td className="num">
                        {formatMw(
                          interval.forecast_mw === null
                            ? null
                            : interval.forecast_mw * (1 - band),
                        )}
                      </td>
                      <td className="num">
                        {formatMw(
                          interval.forecast_mw === null
                            ? null
                            : interval.forecast_mw * (1 + band),
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="panel stats-panel">
            <div>
              <p className="eyebrow">Selected span</p>
              <h3>Energy</h3>
            </div>
            <EnergyBlock label="Forecast" stats={forecastEnergy} />
            <div className="stat-list">
              <StatRow
                label="Intervals"
                value={formatNumber(data?.summary.interval_count ?? null)}
              />
              <StatRow
                label="With forecast"
                value={formatNumber(data?.summary.selected_count ?? null)}
              />
              <StatRow
                label="Missing"
                value={formatNumber(data?.summary.missing_count ?? null)}
              />
              <StatRow
                label="Band width"
                value={`${formatNumber(tolerancePercent)}%`}
              />
              <StatRow
                label="Lead time"
                value={data ? `${data.lead_time_hours} h` : "—"}
              />
            </div>
            {data ? <DataSourceNote meta={data.meta} /> : null}
          </aside>
        </div>
      </div>
    </section>
  );
}
