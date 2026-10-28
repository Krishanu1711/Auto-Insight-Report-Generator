import React, { useMemo } from "react";
import { LineChart } from "../components/charts/line-chart.tsx";
import { Line } from "../components/charts/line.tsx";
import { Grid } from "../components/charts/grid.tsx";
import { XAxis } from "../components/charts/x-axis.tsx";
import { ChartTooltip } from "../components/charts/tooltip/chart-tooltip.tsx";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

function dateValue(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function toTimeSeries(figure) {
  const traces = (Array.isArray(figure?.data) ? figure.data : []).filter((trace) =>
    trace?.type === "scatter" && typeof trace.mode === "string" && trace.mode.includes("lines"),
  );
  if (!traces.length || traces.length > COLORS.length) return null;

  const series = [];
  const rowsByDate = new Map();
  for (const [index, trace] of traces.entries()) {
    const x = Array.isArray(trace.x) ? trace.x : [];
    const y = Array.isArray(trace.y) ? trace.y : [];
    if (!x.length || x.length !== y.length) return null;
    const key = `series_${index}`;
    let validDates = 0;
    for (const [pointIndex, rawDate] of x.entries()) {
      const date = dateValue(rawDate);
      if (!date) continue;
      validDates += 1;
      const row = rowsByDate.get(date) || { date };
      const rawValue = y[pointIndex];
      const value = rawValue == null ? null : Number(rawValue);
      row[key] = Number.isFinite(value) ? value : null;
      rowsByDate.set(date, row);
    }
    if (validDates < Math.ceil(x.length * 0.8)) return null;
    series.push({
      key,
      label: String(trace.name || `Series ${index + 1}`),
      color: COLORS[index],
      markers: String(trace.mode).includes("markers"),
    });
  }
  const rows = [...rowsByDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  if (rows.length < 2) return null;
  return { rows, series };
}

export default function BklitLine({ chart }) {
  const model = useMemo(() => toTimeSeries(chart?.figure), [chart]);
  if (!model) return null;
  return (
    <div className="bklit-chart-frame" aria-label={`${chart.title}, interactive time-series line chart`}>
      <LineChart
        data={model.rows}
        xDataKey="date"
        aspectRatio="3.25 / 1"
        margin={{ top: 20, right: 20, bottom: 40, left: 48 }}
        animationDuration={360}
        yDomainTween={false}
      >
        <Grid horizontal vertical={false} stroke="var(--chart-grid)" strokeDasharray="0" strokeOpacity={0.82} />
        {model.series.map((series) => (
          <Line
            key={series.key}
            dataKey={series.key}
            stroke={series.color}
            strokeWidth={2.2}
            showMarkers={series.markers}
            showHighlight
            fadeEdges={false}
          />
        ))}
        <XAxis numTicks={6} />
        <ChartTooltip showCrosshair showDatePill={false} />
      </LineChart>
      <ul className="bklit-legend" aria-label="Chart series">
        {model.series.map((series) => <li key={series.key}><i style={{ background: series.color }} />{series.label}</li>)}
      </ul>
      <span className="sr-only">
        {model.rows.map((row) => `${row.date}: ${model.series.map((series) => `${series.label} ${row[series.key] ?? "no value"}`).join(", ")}`).join("; ")}
      </span>
    </div>
  );
}

export { toTimeSeries };
