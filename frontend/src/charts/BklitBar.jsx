import React, { useMemo } from "react";
import { BarChart } from "../components/charts/bar-chart.tsx";
import { Bar } from "../components/charts/bar.tsx";
import { BarYAxis } from "../components/charts/bar-y-axis.tsx";
import { Grid } from "../components/charts/grid.tsx";
import { ChartTooltip } from "../components/charts/tooltip/chart-tooltip.tsx";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
const MAX_LABELS = 18;

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function toRows(figure) {
  const traces = asArray(figure?.data).filter((trace) => trace?.type === "bar");
  if (!traces.length) return null;

  const horizontal = traces.some((trace) => trace.orientation === "h");
  const valuesByTrace = traces.map((trace, index) => {
    const categories = asArray(horizontal ? trace.y : trace.x);
    const values = asArray(horizontal ? trace.x : trace.y);
    if (!categories.length || categories.length !== values.length) return null;
    return {
      key: `series_${index}`,
      label: String(trace.name || `Series ${index + 1}`),
      color: COLORS[index % COLORS.length],
      values: new Map(categories.map((category, i) => [String(category), Number(values[i])])),
    };
  }).filter(Boolean);
  if (!valuesByTrace.length) return null;

  const totals = new Map();
  for (const series of valuesByTrace) {
    for (const [category, value] of series.values) {
      if (Number.isFinite(value)) totals.set(category, (totals.get(category) || 0) + Math.abs(value));
    }
  }
  const categories = [...totals.keys()];
  if (categories.length > MAX_LABELS) {
    categories.sort((a, b) => totals.get(b) - totals.get(a));
  }
  const shown = categories.slice(0, MAX_LABELS);
  const rows = shown.map((category) => {
    const row = { category };
    for (const series of valuesByTrace) {
      const value = series.values.get(category);
      row[series.key] = Number.isFinite(value) ? value : 0;
    }
    return row;
  });
  return {
    rows,
    series: valuesByTrace.map(({ key, label, color }) => ({ key, label, color })),
    truncated: categories.length > shown.length,
    stacked: figure?.layout?.barmode === "stack" || figure?.layout?.barmode === "relative",
  };
}

export default function BklitBar({ chart }) {
  const model = useMemo(() => toRows(chart?.figure), [chart]);
  if (!model) return null;

  const heightRatio = Math.max(2, Math.min(4, model.rows.length / 7));
  return (
    <div className="bklit-chart-frame" aria-label={`${chart.title}, interactive horizontal bar chart`}>
      <BarChart
        data={model.rows}
        xDataKey="category"
        orientation="horizontal"
        stacked={model.stacked}
        aspectRatio={`3.15 / ${heightRatio}`}
        margin={{ top: 8, right: 20, bottom: 12, left: 112 }}
        barGap={0.24}
        animationDuration={360}
      >
        <Grid horizontal vertical={false} stroke="var(--chart-grid)" strokeDasharray="0" strokeOpacity={0.82} />
        {model.series.map((series) => (
          <Bar
            key={series.key}
            dataKey={series.key}
            fill={series.color}
            stroke={series.color}
            lineCap={4}
            showValue={model.series.length === 1}
            valueLabelOrientation="auto"
            valueLabelPosition="top"
            animate
            fadedOpacity={0.22}
          />
        ))}
        <BarYAxis showAllLabels={false} maxLabels={MAX_LABELS} />
        <ChartTooltip showCrosshair={false} showDatePill={false} />
      </BarChart>
      <span className="sr-only">
        {model.rows.map((row) => `${row.category}: ${model.series.map((series) => `${series.label} ${row[series.key]}`).join(", ")}`).join("; ")}
      </span>
      {model.truncated && <p className="chart-note">Showing the highest-value {MAX_LABELS} categories.</p>}
    </div>
  );
}

export { toRows };
