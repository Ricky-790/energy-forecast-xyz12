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

import { getAccuracy, getTolerance } from "./api";
import type { AccuracyResponse, ToleranceMetric } from "./types";
import {
  ACCURACY_LEAD_TIMES,
  DataSourceNote,
  EnergyBlock,
  ErrorBox,
  Field,
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
  formatSettlementPeriods,
  formatSignedMwh,
  formatSignedMw,
  formatSignedPercent,
  toUtcIso,
  useChartZoom,
  type Theme,
} from "./ui";

interface AccuracyScreenProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  theme: Theme;
}

interface AccuracyChartPoint {
  time: string;
  forecast: number | null;
  actual: number | null;
  error: number | null;
  lower: number | null;
  span: number | null;
  upper: number | null;
}

function AccuracyTooltip({ active, payload }: any) {
  if (!active || !payload?.length) {
    return null;
  }
  const point = payload[0].payload as AccuracyChartPoint;
  return (
    <div className="tooltip">
      <strong>{formatDateTime(point.time)} UTC</strong>
      <span>Forecast: {formatMw(point.forecast)}</span>
      <span>Actual: {formatMw(point.actual)}</span>
      <span>Error: {formatSignedMw(point.error)}</span>
    </div>
  );
}

type Filter = "all" | "matched" | "missing";

export default function AccuracyScreen({
  sidebarOpen,
  onToggleSidebar,
  theme,
}: AccuracyScreenProps) {
  const colors = chartColors(theme);
  const [start, setStart] = useState("2026-01-15T00:00");
  const [end, setEnd] = useState("2026-01-30T00:00");
  const [lead, setLead] = useState(24);
  const [metric, setMetric] = useState<ToleranceMetric>("mae");
  const [tolerancePercent, setTolerancePercent] = useState(5);
  const [data, setData] = useState<AccuracyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [filter, setFilter] = useState<Filter>("all");
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcNote, setCalcNote] = useState<string | null>(null);
  const [calcError, setCalcError] = useState<string | null>(null);

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
    getAccuracy(
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
  const chartData: AccuracyChartPoint[] =
    data?.intervals.map((interval) => {
      const forecast = interval.forecast_mw;
      const lower = forecast === null ? null : forecast * (1 - band);
      const upper = forecast === null ? null : forecast * (1 + band);
      return {
        time: interval.start_time,
        forecast,
        actual: interval.actual_mw,
        error: interval.error_mw,
        lower,
        span: lower !== null && upper !== null ? upper - lower : null,
        upper,
      };
    }) ?? [];

  const { ref: chartRef, range } = useChartZoom(chartData.length);
  const visibleData = chartData.slice(range[0], range[1] + 1);
  const visibleDays = Math.max(0, (visibleData.length - 1) / 24);

  const calculateTolerance = () => {
    if (rangeError) {
      return;
    }
    setCalcLoading(true);
    setCalcError(null);
    getTolerance({ start: toUtcIso(start), end: toUtcIso(end), lead, metric })
      .then((response) => {
        setCalcNote(response.note ?? null);
        if (response.available && response.value_percent !== null) {
          setTolerancePercent(clampPercent(Math.round(response.value_percent)));
        }
      })
      .catch((requestError: Error) => {
        setCalcError(requestError.message);
      })
      .finally(() => {
        setCalcLoading(false);
      });
  };

  const filteredIntervals =
    data?.intervals.filter((interval) => {
      if (filter === "matched") {
        return interval.status === "ok";
      }
      if (filter === "missing") {
        return interval.status !== "ok";
      }
      return true;
    }) ?? [];

  const forecastEnergy = energyStats(
    data?.intervals.map((interval) => interval.forecast_mw) ?? [],
  );
  const actualEnergy = energyStats(
    data?.intervals.map((interval) => interval.actual_mw) ?? [],
  );

  return (
    <section className={`screen ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
      <aside className="sidebar">
        <div className="sidebar-head">
          <div>
            <p className="eyebrow">Controls</p>
            <h2>Accuracy setup</h2>
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
            <Field
              label="Forecast lead time"
              hint="Shorter leads are retrospective only."
            >
              <select
                value={lead}
                onChange={(event) => setLead(Number(event.target.value))}
              >
                {ACCURACY_LEAD_TIMES.map((hours) => (
                  <option key={hours} value={hours}>
                    {hours} hours
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="control-group">
            <h3>Tolerance band</h3>
            <Field label="Error type" hint="Used when calculating the band.">
              <select
                value={metric}
                onChange={(event) =>
                  setMetric(event.target.value as ToleranceMetric)
                }
              >
                <option value="mae">Typical error (MAE)</option>
                <option value="p90">Wider range (P90)</option>
              </select>
            </Field>
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
            <button
              type="button"
              className="button button-block"
              onClick={calculateTolerance}
              disabled={calcLoading || Boolean(rangeError)}
            >
              {calcLoading ? "Calculating…" : "Calculate tolerance"}
            </button>
            {calcError ? (
              <p className="field-hint">{calcError}</p>
            ) : calcNote ? (
              <p className="field-hint">{calcNote}</p>
            ) : null}
          </div>

          {rangeError ? <div className="warning">{rangeError}</div> : null}
        </div>
      </aside>

      <div className="workbench">
        <div className="panel chart-panel">
          <div className="panel-head">
            <div>
              <h2>Forecast against actual</h2>
              <p className="panel-sub">
                Hourly forecast against the mean of both half-hourly settlement
                periods. UTC and MW.
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
            <Loading label="Loading accuracy data. The first request for a range may take a few seconds while Elexon data is cached in SQLite." />
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
                    content={(props: any) => <AccuracyTooltip {...props} />}
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
                  <Line
                    dataKey="actual"
                    name="Actual"
                    stroke={colors.actual}
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
                <h3>Interval comparison</h3>
                <p className="panel-sub">
                  Errors in MW. Positive error means forecast above actual.
                </p>
              </div>
              <div className="segmented">
                {(["all", "matched", "missing"] as Filter[]).map((value) => (
                  <button
                    key={value}
                    className={filter === value ? "active" : ""}
                    onClick={() => setFilter(value)}
                  >
                    {value === "all"
                      ? "All"
                      : value === "matched"
                        ? "Matched"
                        : "Missing"}
                  </button>
                ))}
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Start time (UTC)</th>
                    <th className="num">SP</th>
                    <th>Forecast published (UTC)</th>
                    <th>Actual published (UTC)</th>
                    <th className="num">Lead</th>
                    <th className="num">Predicted</th>
                    <th className="num">Actual (MW)</th>
                    <th className="num">Error (MW)</th>
                    <th className="num">Abs error (MW)</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredIntervals.map((interval) => (
                    <tr key={interval.start_time}>
                      <td>{formatDateTime(interval.start_time)}</td>
                      <td className="num">
                        {formatSettlementPeriods(interval.settlement_periods)}
                      </td>
                      <td>{formatDateTime(interval.publish_time)}</td>
                      <td>{formatDateTime(interval.actual_publish_time)}</td>
                      <td className="num">
                        {formatLead(interval.forecast_lead_hours)}
                      </td>
                      <td className="num">{formatMw(interval.forecast_mw)}</td>
                      <td className="num">{formatMw(interval.actual_mw)}</td>
                      <td className="num">{formatSignedMw(interval.error_mw)}</td>
                      <td className="num">
                        {formatMw(interval.absolute_error_mw)}
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
              <h3>Energy & errors</h3>
            </div>
            <EnergyBlock label="Forecast" stats={forecastEnergy} />
            <EnergyBlock label="Actual" stats={actualEnergy} />
            <div className="stat-list">
              <StatRow
                label="Peak error"
                value={formatSignedMw(data?.metrics.peak_error_mw ?? null)}
              />
              <StatRow
                label="Mean error"
                value={formatSignedMw(data?.metrics.mean_error_mw ?? null)}
              />
              <StatRow
                label="Total energy error"
                value={formatSignedMwh(data?.metrics.total_energy_error_mwh ?? null)}
              />
              <StatRow
                label="Mean percentage error"
                value={formatSignedPercent(
                  data?.metrics.mean_percentage_error ?? null,
                )}
              />
            </div>
            <p className="data-note">
              Matched hours only, error = forecast − actual. Total energy error
              is the difference in MWh over the span.
            </p>
            {data ? <DataSourceNote meta={data.meta} /> : null}
          </aside>
        </div>
      </div>
    </section>
  );
}
