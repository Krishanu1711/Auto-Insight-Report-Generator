import React from "react";
import { createRoot } from "react-dom/client";

const roots = new Map();
const plotlyCharts = new Set();
let plotlyPromise;
let bklitPromise;
let bklitLinePromise;

function loadPlotly() {
  if (!plotlyPromise) plotlyPromise = import("plotly.js-dist-min").then((module) => module.default);
  return plotlyPromise;
}

function loadBklitBar() {
  if (!bklitPromise) bklitPromise = import("./BklitBar.jsx").then((module) => module.default);
  return bklitPromise;
}

function loadBklitLine() {
  if (!bklitLinePromise) bklitLinePromise = import("./BklitLine.jsx");
  return bklitLinePromise;
}

function supportsBklitBar(chart) {
  return chart?.kind === "bar" && Array.isArray(chart?.figure?.data)
    && chart.figure.data.some((trace) => trace?.type === "bar" && Array.isArray(trace.x) && Array.isArray(trace.y));
}

const PALETTE_TOKENS = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5"];
const FALLBACK_PALETTE = ["#a9c8d1", "#a4bda8", "#d7b67a", "#c7988c", "#aebacf"];
const FONT_STACK = '"IBM Plex Sans", "Segoe UI", sans-serif';

function chartTheme(host) {
  const styles = getComputedStyle(host);
  const read = (name, fallback) => styles.getPropertyValue(name).trim() || fallback;
  return {
    palette: PALETTE_TOKENS.map((name, index) => read(name, FALLBACK_PALETTE[index])),
    ink: read("--chart-foreground", "#ecebe7"),
    muted: read("--chart-label", "#a4adaf"),
    grid: read("--chart-grid", "#384247"),
    tooltip: read("--chart-tooltip-background", "#252d30"),
  };
}

function withAlpha(color, alpha) {
  const match = color.match(/^#([\da-f]{3}|[\da-f]{6})$/i);
  if (!match) return color;
  const hex = match[1].length === 3 ? [...match[1]].map((part) => part + part).join("") : match[1];
  const [r, g, b] = [0, 2, 4].map((offset) => parseInt(hex.slice(offset, offset + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function themeTrace(trace, index, theme) {
  const color = theme.palette[index % theme.palette.length];
  if (["heatmap", "histogram2d", "contour"].includes(trace.type)) {
    return {
      ...trace,
      colorscale: [[0, "#303a3e"], [0.5, "#252d30"], [1, theme.palette[0]]],
      colorbar: {
        ...trace.colorbar,
        outlinecolor: theme.grid,
        tickfont: { ...trace.colorbar?.tickfont, color: theme.muted, family: FONT_STACK },
      },
      textfont: { ...trace.textfont, color: theme.ink, family: FONT_STACK },
    };
  }

  if (["pie", "donut", "sunburst"].includes(trace.type)) {
    const count = trace.labels?.length || trace.values?.length || theme.palette.length;
    return {
      ...trace,
      marker: {
        ...trace.marker,
        color: Array.from({ length: count }, (_, point) => theme.palette[point % theme.palette.length]),
        line: { ...trace.marker?.line, color: "#1d2326", width: 1 },
      },
      textfont: { ...trace.textfont, color: theme.ink, family: FONT_STACK },
    };
  }

  const marker = trace.marker ? { ...trace.marker } : null;
  if (marker) {
    const numericScale = Array.isArray(marker.color) && marker.color.some((value) => typeof value === "number");
    marker.color = numericScale ? marker.color : color;
    if (numericScale) marker.colorscale = [[0, theme.palette[0]], [0.5, theme.palette[1]], [1, theme.palette[2]]];
    if (marker.line) marker.line = { ...marker.line, color };
  }

  const themed = { ...trace };
  if (trace.line) themed.line = { ...trace.line, color };
  if (marker) themed.marker = marker;
  if (["bar", "histogram", "box", "violin", "waterfall"].includes(trace.type) && !marker) themed.marker = { color };
  if (trace.fill && trace.fill !== "none") themed.fillcolor = withAlpha(theme.palette[0], 0.16);
  else if (trace.fillcolor) themed.fillcolor = withAlpha(color, 0.18);
  return themed;
}

function themeLayout(source, theme, traces = []) {
  const categoryAxes = new Set();
  for (const trace of traces) {
    const values = Array.isArray(trace.x) ? trace.x.filter((value) => typeof value === "string") : [];
    const isDateAxis = values.length > 0 && values.every((value) => /^\d{4}-\d{2}-\d{2}/.test(value));
    if (values.length >= 5 && !isDateAxis) {
      const xAxis = trace.xaxis || "x";
      categoryAxes.add(xAxis === "x" ? "xaxis" : `xaxis${xAxis.slice(1)}`);
    }
  }

  const layout = {
    ...source,
    title: undefined,
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    colorway: theme.palette,
    font: { ...source.font, family: FONT_STACK, color: theme.ink, size: 11 },
    legend: {
      ...source.legend,
      bgcolor: "rgba(0,0,0,0)",
      bordercolor: "rgba(0,0,0,0)",
      font: { ...source.legend?.font, family: FONT_STACK, color: theme.muted, size: 10 },
    },
    hoverlabel: {
      ...source.hoverlabel,
      bgcolor: theme.tooltip,
      bordercolor: theme.grid,
      font: { ...source.hoverlabel?.font, family: FONT_STACK, color: theme.ink, size: 11 },
    },
    margin: {
      l: 54, r: 22, t: 20, b: 46, ...source.margin,
      ...(categoryAxes.size ? { b: Math.max(source.margin?.b || 0, 68) } : {}),
    },
  };

  for (const [key, axis] of Object.entries(source)) {
    if (/^[xy]axis\d*$/.test(key) && axis && typeof axis === "object") {
      layout[key] = {
        ...axis,
        gridcolor: theme.grid,
        zerolinecolor: theme.grid,
        linecolor: theme.grid,
        tickangle: categoryAxes.has(key) ? (axis.tickangle ?? -30) : axis.tickangle,
        automargin: true,
        tickfont: { ...axis.tickfont, family: FONT_STACK, color: theme.muted, size: categoryAxes.has(key) ? 9 : 10 },
        titlefont: { ...axis.titlefont, family: FONT_STACK, color: theme.muted, size: 11 },
      };
    } else if (key === "annotations" && Array.isArray(axis)) {
      layout[key] = axis.map((annotation) => ({
        ...annotation,
        font: { ...annotation.font, family: FONT_STACK, color: theme.muted },
      }));
    } else if (/^coloraxis\d*$/.test(key) && axis && typeof axis === "object") {
      layout[key] = {
        ...axis,
        colorbar: {
          ...axis.colorbar,
          outlinecolor: theme.grid,
          tickfont: { ...axis.colorbar?.tickfont, family: FONT_STACK, color: theme.muted },
        },
      };
    }
  }
  return layout;
}

export function clearCharts(container) {
  for (const [node, root] of roots) {
    if (container.contains(node)) {
      root.unmount();
      roots.delete(node);
    }
  }
  for (const node of [...plotlyCharts]) {
    if (container.contains(node)) {
      if (plotlyPromise) plotlyPromise.then((Plotly) => Plotly.purge(node));
      plotlyCharts.delete(node);
    }
  }
}

export async function renderCharts(container, charts = []) {
  const byId = new Map(charts.map((chart) => [chart.id, chart]));
  for (const host of container.querySelectorAll("[data-chart-id]")) {
    const chart = byId.get(host.dataset.chartId);
    if (!chart) {
      host.innerHTML = '<p class="empty-inline">Chart data is not available.</p>';
      continue;
    }
    try {
      if (supportsBklitBar(chart)) {
        const BklitBar = await loadBklitBar();
        if (!container.contains(host)) continue;
        const root = createRoot(host);
        roots.set(host, root);
        root.render(<BklitBar chart={chart} />);
        continue;
      }
      if (chart.kind === "line" && chart.group === "time_series") {
        const lineModule = await loadBklitLine();
        if (lineModule.toTimeSeries(chart.figure)) {
          if (!container.contains(host)) continue;
          const root = createRoot(host);
          roots.set(host, root);
          root.render(<lineModule.default chart={chart} />);
          continue;
        }
      }
      const Plotly = await loadPlotly();
      if (!container.contains(host)) continue;
      const figure = chart.figure || {};
      const theme = chartTheme(host);
      const traces = (figure.data || []).map((trace, index) => themeTrace(trace, index, theme));
      const layout = themeLayout(figure.layout || {}, theme, traces);
      await Plotly.newPlot(host, traces, layout, {
        responsive: true,
        displayModeBar: false,
        displaylogo: false,
        scrollZoom: false,
      });
      plotlyCharts.add(host);
    } catch (error) {
      console.error("Chart renderer failed", chart.id, error);
      host.innerHTML = '<p class="empty-inline">This chart could not be rendered. Its data may still be included in the report.</p>';
    }
  }
}
