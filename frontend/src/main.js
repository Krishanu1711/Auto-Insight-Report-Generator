import "./styles.css";
import { api } from "./api.js";
import { renderCharts, clearCharts } from "./charts/renderer.jsx";
import { DEMO_BUNDLE } from "./demo/demo-data.js";

const NAV = [
  ["upload", "Upload"],
  ["profile", "Profile & cleaning"],
  ["explore", "Explore charts"],
  ["forecast", "Forecast"],
  ["insights", "Insights"],
  ["reports", "Reports & export"],
  ["saved", "Saved datasets"],
];

const PAGE_INFO = {
  upload: ["Workspace", "Start with a dataset", "Upload a supported file or connect a public JSON endpoint. Analysis runs in the Python backend after it is integrated."],
  profile: ["Inspect", "Data profile", "Review the actual shape, quality, transformations, and descriptive results for the active dataset."],
  explore: ["Visualize", "Explore charts", "Compare generated charts by purpose. Each visualization is driven by the returned chart specification."],
  forecast: ["Project", "Time-series forecast", "Choose supported date and target fields, then inspect the model output, uncertainty, and evaluation metrics."],
  insights: ["Interpret", "Insights", "Browse deterministic observations and data-quality warnings returned with the analysis."],
  reports: ["Deliver", "Reports & export", "Download the existing self-contained HTML report, export data, or save the cleaned dataset."],
  saved: ["Library", "Saved datasets", "Review saved results from the project's SQLite persistence layer."],
};

const GROUP_LABELS = {
  distribution: "Distributions",
  category: "Categories",
  relationship: "Relationships",
  text: "Text analysis",
  time_series: "Time series",
};

const state = {
  page: routeFromHash(),
  mode: "offline",
  bundle: null,
  selectedFile: null,
  selectedGroup: "distribution",
  selectedTransform: "scaled_minmax",
  insightFilter: "all",
  uploadTab: "file",
  savedDatasets: null,
  savedPreview: null,
  running: false,
  apiUrl: "",
};

function routeFromHash() {
  const key = window.location.hash.replace(/^#\/?/, "").split("/")[0];
  return PAGE_INFO[key] ? key : "upload";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function display(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "—";
  if (Array.isArray(value)) return value.map(display).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatPercent(value, fraction = true) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${(fraction ? number * 100 : number).toFixed(1)}%`;
}

function titleCase(value) {
  return String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function pageHeader(page) {
  const [eyebrow, title, description] = PAGE_INFO[page];
  return `<header class="page-head"><p class="page-eyebrow">${escapeHtml(eyebrow)}</p><h1 class="page-title">${escapeHtml(title)}</h1><p class="page-description">${escapeHtml(description)}</p></header>`;
}

function demoBanner() {
  if (state.mode === "demo") {
    return `<aside class="demo-banner" role="note"><div><strong>Demo data · synthetic sample</strong><p>This is an illustrative showcase only—not your upload, not a backend result, and not a real forecast.</p></div><button class="button" data-action="exit-demo">Exit demo</button></aside>`;
  }
  return "";
}

function connectionLabel() {
  return state.mode === "connected" ? ["Connected", "connected"] : state.mode === "demo" ? ["Demo only", "demo"] : ["Backend not connected", "offline"];
}

function renderShell() {
  const app = document.querySelector("#app");
  clearCharts(app);
  const [connection, modifier] = connectionLabel();
  const currentInfo = PAGE_INFO[state.page] || PAGE_INFO.upload;
  const datasetName = state.bundle?.source?.filename || "No active dataset";
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar" aria-label="Main navigation">
        <button class="brand" data-route="upload" aria-label="Auto-Insight home">
          <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
          <span><span class="brand-name">Auto-Insight</span><span class="brand-caption">Data workspace</span></span>
        </button>
        <p class="nav-label">Workspace</p>
        <nav class="sidebar-nav">${NAV.map(([key, label]) => `<button class="nav-link" data-route="${key}" aria-current="${state.page === key ? "page" : "false"}"><span class="nav-symbol" aria-hidden="true">${navGlyph(key)}</span><span>${escapeHtml(label)}</span></button>`).join("")}</nav>
        <div class="sidebar-bottom">
          <div class="connection-state"><span class="connection-dot ${modifier}"></span><span>${escapeHtml(connection)}</span></div>
          <div class="workspace-file" title="${escapeHtml(datasetName)}">${escapeHtml(datasetName)}</div>
        </div>
      </aside>
      <div class="main-area">
        <header class="topbar">
          <div class="topbar-context">Auto-Insight <span aria-hidden="true">/</span> ${escapeHtml(currentInfo[1])}</div>
          <div class="topbar-actions">
            <span class="topbar-status ${modifier}"><span class="connection-dot ${modifier}"></span>${escapeHtml(connection)}</span>
            <button class="button button-subtle" data-action="check-connection">Check connection</button>
          </div>
        </header>
        <main class="content" id="content" tabindex="-1"></main>
      </div>
    </div>
    <div class="toast" id="toast" role="status" aria-live="polite"></div>`;

  const content = document.querySelector("#content");
  const body = renderPageBody();
  content.innerHTML = `${demoBanner()}${pageHeader(state.page)}${body}`;
  bindPage();
  drawCurrentCharts();
}

function navGlyph(key) {
  const paths = {
    upload: '<path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M5 15v4h14v-4"/>',
    profile: '<path d="M4 5h16M4 10h10M4 15h16M4 20h8"/>',
    explore: '<path d="M4 19V5m0 14h17M8 15l3-4 3 2 5-7"/>',
    forecast: '<path d="M4 18 9 12l4 3 7-10"/><path d="M15 5h5v5"/>',
    insights: '<path d="M9 18h6m-5 3h4m-2-19a7 7 0 0 0-4 12.75c.5.35 1 1.15 1 2.25h6c0-1.1.5-1.9 1-2.25A7 7 0 0 0 12 2Z"/>',
    reports: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    saved: '<path d="M5 4h14v17l-7-4-7 4z"/>',
  };
  return `<svg viewBox="0 0 24 24" focusable="false">${paths[key] || ""}</svg>`;
}

function renderPageBody() {
  if (!state.bundle && state.page !== "upload") {
    return `<section class="empty-state"><div><h2>No analysis loaded</h2><p>Upload a dataset through the connected Python API, or open the explicitly labeled sample workspace to explore the interface.</p><button class="button button-primary" data-route="upload">Go to upload</button></div></section>`;
  }
  switch (state.page) {
    case "profile": return renderProfile();
    case "explore": return renderExplore();
    case "forecast": return renderForecast();
    case "insights": return renderInsights();
    case "reports": return renderReports();
    case "saved": return renderSaved();
    default: return renderUpload();
  }
}

function renderUpload() {
  const source = state.bundle?.source;
  const fileName = state.selectedFile ? state.selectedFile.name : "No file selected";
  const fileSize = state.selectedFile ? ` · ${formatBytes(state.selectedFile.size)}` : "";
  const filePanel = state.uploadTab === "file";
  const apiPanel = state.uploadTab === "url";
  const warning = state.mode === "offline"
    ? `<aside class="offline-banner"><div><strong>Python backend not connected</strong><p>Upload analysis needs an API endpoint. You can connect it using the included contract, or open the labeled synthetic sample.</p></div><button class="button button-primary" data-action="load-demo">Open demo workspace</button></aside>`
    : "";

  let previous = "";
  if (state.bundle) {
    previous = `<section class="stack" aria-label="Active dataset">
      <div class="metric-strip">${metric("Raw rows", state.bundle.source.rowsRaw)}${metric("Clean rows", state.bundle.clean.preview.totalRows)}${metric("Columns", state.bundle.profile.columnsCount)}${metric("Cleaning actions", state.bundle.clean.actions.length)}${metric("Charts", state.bundle.charts.length)}${metric("Forecast", state.bundle.forecast ? "Available" : "Not available")}</div>
      ${state.bundle.forecastError ? `<div class="notice notice-neutral">${escapeHtml(state.bundle.forecastError)}</div>` : ""}
      <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Source preview</h2><p class="panel-description">${escapeHtml(state.bundle.source.filename)} · ${escapeHtml(state.bundle.source.format?.toUpperCase())} · ${display(state.bundle.source.rowsRaw)} source rows</p></div><span class="tag">${state.mode === "demo" ? "DEMO SAMPLE" : "ACTIVE DATA"}</span></div>${renderTable(state.bundle.source.rawPreview, { maxRows: 8 })}</section>
      <div class="panel"><h2 class="panel-title">Next steps</h2><p class="panel-description">Move into a detail view when you're ready.</p><div class="button-row" style="margin-top:12px"><button class="button" data-route="profile">Review profile</button><button class="button" data-route="explore">Explore charts</button><button class="button" data-route="forecast">Forecast</button><button class="button" data-route="reports">Reports & export</button></div></div>
    </section>`;
  }

  return `${warning}
    <div class="stack">
      <div class="tabs" role="tablist" aria-label="Data source">
        <button class="tab-button" role="tab" aria-selected="${filePanel}" data-action="upload-tab" data-value="file">Upload file</button>
        <button class="tab-button" role="tab" aria-selected="${apiPanel}" data-action="upload-tab" data-value="url">Public JSON API</button>
      </div>
      ${filePanel ? `<div class="upload-grid">
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Choose a file</h2><p class="panel-description">CSV, JSON, XML, or TXT · 50 MB maximum</p></div></div>
          <label class="dropzone" id="dropzone" for="file-input"><input id="file-input" type="file" accept=".csv,.json,.xml,.txt,text/plain,text/csv,application/json,application/xml" aria-describedby="file-help"><span><span class="dropzone-mark" aria-hidden="true">↥</span><span class="dropzone-title">Drop a file here or choose one</span><span class="dropzone-hint" id="file-help">The frontend sends the selected file to the Python API contract. File contents stay in your browser until you run analysis.</span><span class="button">Choose file</span><span class="file-meta" id="file-meta">${escapeHtml(fileName)}${escapeHtml(fileSize)}</span></span></label>
        </section>
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Cleaning options</h2><p class="panel-description">These controls match the backend's documented configuration.</p></div></div>
          <div class="field"><label class="field-label" for="outlier-treatment">Outlier treatment</label><select class="select" id="outlier-treatment"><option value="flag">Flag only</option><option value="cap">Cap at IQR fences</option><option value="remove">Remove rows</option></select><span class="field-hint">Flag = log only · Cap = clip · Remove = drop affected rows.</span></div>
          <div class="field" style="margin-top:14px"><label class="field-label" for="missing-threshold">Drop columns above missing threshold <span id="threshold-label">60%</span></label><input class="input" type="range" id="missing-threshold" min="0.30" max="0.90" step="0.05" value="0.60"><span class="field-hint">Columns exceeding this missing-value fraction are removed.</span></div>
          <div class="option-row" style="margin-top:15px"><input id="auto-forecast" type="checkbox" checked><label for="auto-forecast">Auto-forecast when a date column is detected<small>Uses the backend's existing automatic forecast defaults.</small></label></div>
        </section>
      </div>
      <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Run analysis</h2><p class="panel-description">Processing and progress are provided by the Python service; no analysis runs in the browser.</p></div></div>
        <div class="run-panel"><p>Choose a supported file and run the Python analysis pipeline.</p><button class="button button-primary" id="run-file" ${!state.selectedFile || state.running ? "disabled" : ""}>Run analysis</button></div>
        ${progressHtml()}
      </section>`
      : `<div class="grid-two">
        <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Public JSON endpoint</h2><p class="panel-description">Enter a public HTTP or HTTPS URL that returns tabular JSON.</p></div></div>
          <label class="field"><span class="field-label">JSON API URL</span><input class="input" id="api-url" type="url" value="${escapeHtml(state.apiUrl)}" placeholder="https://example.com/data.json" autocomplete="url"></label>
          <p class="field-hint" style="margin-top:8px">The existing project supports public JSON URL ingestion. Credentials and private endpoints are not requested by this frontend.</p>
          <div class="run-panel" style="margin-top:16px"><p>Fetch and analyze through the connected Python service.</p><button class="button button-primary" id="run-url" ${state.running ? "disabled" : ""}>Analyze URL</button></div>
          ${progressHtml()}
        </section>
        <section class="panel"><h2 class="panel-title">Cleaning options</h2><p class="panel-description">Same settings are applied to file and URL sources.</p>
          <div class="field" style="margin-top:14px"><label class="field-label" for="outlier-treatment-url">Outlier treatment</label><select class="select" id="outlier-treatment-url"><option value="flag">Flag only</option><option value="cap">Cap at IQR fences</option><option value="remove">Remove rows</option></select></div>
          <div class="field" style="margin-top:13px"><label class="field-label" for="missing-threshold-url">Missing threshold</label><input class="input" type="range" id="missing-threshold-url" min="0.30" max="0.90" step="0.05" value="0.60"><span class="field-hint">Default 60%.</span></div>
          <div class="option-row" style="margin-top:14px"><input id="auto-forecast-url" type="checkbox" checked><label for="auto-forecast-url">Auto-forecast when a date column is detected</label></div>
        </section>
      </div>`}
      ${previous}
    </div>`;
}

function progressHtml() {
  return `<div class="progress-block" id="progress-block" aria-live="polite"><div class="progress-header"><span id="progress-stage">Waiting for the Python service…</span><span id="progress-value">0%</span></div><div class="progress-track" role="progressbar" aria-label="Analysis progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="progress-fill" id="progress-fill"></div></div></div>`;
}

function renderProfile() {
  const bundle = state.bundle;
  const kinds = bundle.profile.columns.reduce((map, column) => { map[column.kind] = (map[column.kind] || 0) + 1; return map; }, {});
  const columns = bundle.profile.columns.map((column) => ({
    Column: column.name, Kind: column.kind, Type: column.dtype,
    Missing: `${display(column.missing)} (${formatPercent(column.missingPct)})`,
    Unique: column.unique, Samples: (column.sampleValues || []).join(", "),
  }));
  const qualityRows = [
    { Measure: "Rows", Before: bundle.clean.qualityBefore?.n_rows, After: bundle.clean.qualityAfter?.n_rows },
    { Measure: "Columns", Before: bundle.clean.qualityBefore?.n_cols, After: bundle.clean.qualityAfter?.n_cols },
    { Measure: "Missing cells", Before: bundle.clean.qualityBefore?.missing_cells, After: bundle.clean.qualityAfter?.missing_cells },
    { Measure: "Duplicate rows", Before: bundle.clean.qualityBefore?.duplicate_rows, After: bundle.clean.qualityAfter?.duplicate_rows },
    { Measure: "Outlier cells", Before: bundle.clean.qualityBefore?.outlier_cells, After: bundle.clean.qualityAfter?.outlier_cells },
  ];
  const actions = bundle.clean.actions.map((action) => ({ Step: titleCase(action.step), Column: action.column || "—", Description: action.description, "Rows affected": action.rowsAffected }));
  const viewKeys = Object.keys(bundle.transform?.views || {});
  const transform = bundle.transform?.views?.[state.selectedTransform];
  const descriptive = bundle.analysis.descriptive;
  const renameRows = Object.entries(bundle.clean.renameMap || {}).filter(([oldName, newName]) => oldName !== newName).map(([original, renamed]) => ({ Original: original, "Renamed to": renamed }));

  return `<div class="stack">
    <div class="metric-strip">${metric("Rows", bundle.profile.rows)}${metric("Columns", bundle.profile.columnsCount)}${metric("Numeric", kinds.numeric || 0)}${metric("Categorical", kinds.categorical || 0)}${metric("Dates", kinds.datetime || 0)}${metric("Memory", `${display(bundle.profile.memoryMb)} MB`)}</div>
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Column profile</h2><p class="panel-description">Type, completeness, cardinality, and example values.</p></div></div>${renderTable({ columns: ["Column", "Kind", "Type", "Missing", "Unique", "Samples"], rows: columns, totalRows: columns.length })}</section>
    <div class="grid-two">
      <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Quality · before and after</h2><p class="panel-description">Changes performed by the existing cleaning pipeline.</p></div></div>${renderTable({ columns: ["Measure", "Before", "After"], rows: qualityRows, totalRows: qualityRows.length })}</section>
      <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Cleaning log</h2><p class="panel-description">The pipeline's recorded cleaning actions.</p></div></div>${actions.length ? renderTable({ columns: ["Step", "Column", "Description", "Rows affected"], rows: actions, totalRows: actions.length }) : `<p class="table-empty">No cleaning actions were recorded.</p>`}</section>
    </div>
    ${renameRows.length ? `<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Column renames</h2><p class="panel-description">Names changed during cleaning.</p></div></div>${renderTable({ columns: ["Original", "Renamed to"], rows: renameRows, totalRows: renameRows.length })}</section>` : ""}
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Descriptive statistics</h2><p class="panel-description">Values returned by the backend's existing analysis.</p></div></div>${descriptive ? renderTable(descriptive) : `<p class="table-empty">Descriptive statistics are not available for this input.</p>`}</section>
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Transformed data</h2><p class="panel-description">Preview of the backend-generated feature view.</p></div>${viewKeys.length ? `<label class="field" style="min-width:220px"><span class="sr-only">Transformed view</span><select class="select" id="transform-view">${viewKeys.map((key) => `<option value="${escapeHtml(key)}" ${key === state.selectedTransform ? "selected" : ""}>${escapeHtml(titleCase(key))}</option>`).join("")}</select></label>` : ""}</div>${transform ? renderTable(transform, { maxRows: 15 }) : `<p class="table-empty">Transformed data is not available for this dataset.</p>`}</section>
  </div>`;
}

function renderExplore() {
  const bundle = state.bundle;
  const charts = [...(bundle.charts || []), ...(bundle.forecastCharts || [])];
  if (!charts.length) return `<section class="empty-state"><div><h2>No visualizations available</h2><p>The selected dataset did not produce charts for these fields.</p></div></section>`;
  const groups = [...new Set(charts.map((chart) => chart.group))];
  if (!groups.includes(state.selectedGroup)) state.selectedGroup = groups[0];
  const groupCharts = charts.filter((chart) => chart.group === state.selectedGroup);
  const regression = bundle.analysis.regression;
  return `<div class="stack">
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Generated visualizations</h2><p class="panel-description">Grouped by analysis purpose. Use the controls to change category; no analysis reruns for these display-only changes.</p></div><span class="tag">${charts.length} CHARTS</span></div>
      <div class="tabs" role="tablist" aria-label="Chart group">${groups.map((group) => `<button class="tab-button" role="tab" aria-selected="${group === state.selectedGroup}" data-action="chart-group" data-value="${escapeHtml(group)}">${escapeHtml(GROUP_LABELS[group] || titleCase(group))}</button>`).join("")}</div>
      <div class="chart-grid">${groupCharts.map((chart, index) => chartCard(chart, index)).join("")}</div>
    </section>
    ${regression ? `<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Linear regression</h2><p class="panel-description">Existing backend summary for ${escapeHtml(regression.x)} against ${escapeHtml(regression.y)}.</p></div><span class="tag">MODEL SUMMARY</span></div><div class="metric-strip">${metric("Coefficient", display(regression.coef))}${metric("Intercept", display(regression.intercept))}${metric("R²", display(regression.r2))}${metric("MAE", display(regression.mae))}${metric("RMSE", display(regression.rmse))}${metric("Train rows", display(regression.n_train))}${metric("Test rows", display(regression.n_test))}</div></section>` : ""}
  </div>`;
}

function chartCard(chart, index) {
  const wide = chart.kind === "heatmap" || chart.kind === "decomposition" || chart.kind === "forecast" || chart.kind === "line";
  return `<article class="chart-card ${wide ? "chart-card-wide" : ""}"><div class="chart-card-head"><div><h3 class="chart-title">${escapeHtml(chart.title)}</h3><p class="chart-description">${escapeHtml(chart.description || (chart.columns || []).join(" · "))}</p></div><span class="tag">${escapeHtml(titleCase(chart.kind))}</span></div><div class="chart-canvas" data-chart-id="${escapeHtml(chart.id)}" role="img" aria-label="${escapeHtml(chart.title)}"></div></article>`;
}

function renderForecast() {
  const bundle = state.bundle;
  const dateColumns = bundle.profile.columns.filter((column) => column.kind === "datetime").map((column) => column.name);
  const numericColumns = bundle.profile.columns.filter((column) => column.kind === "numeric").map((column) => column.name);
  const forecast = bundle.forecast;
  const defaultDate = forecast?.params?.date_col || bundle.profile.primaryDateColumn || dateColumns[0] || "";
  const defaultTarget = forecast?.params?.target_col || numericColumns[0] || "";
  const warnings = forecast?.warnings || [];

  if (!dateColumns.length || !numericColumns.length) {
    return `<div class="stack">${bundle.forecastError ? `<div class="notice notice-neutral">${escapeHtml(bundle.forecastError)}</div>` : ""}<section class="empty-state"><div><h2>Forecast unavailable for this dataset</h2><p>Forecasting needs at least one datetime column and one numeric target. The profile currently exposes ${dateColumns.length} date column(s) and ${numericColumns.length} numeric column(s).</p></div></section></div>`;
  }

  const charts = bundle.forecastCharts || [];
  const forecastRows = forecast?.forecast || [];
  const warningsHtml = warnings.length ? `<div class="stack">${warnings.map((warning) => `<div class="notice">${escapeHtml(warning)}</div>`).join("")}</div>` : "";
  const resultBlock = forecast ? `<div class="stack">
    ${warningsHtml}
    <div class="metric-strip">${metric("ARIMA order", (forecast.order || []).join(", "))}${metric("AIC", display(forecast.aic))}${metric("Frequency", forecast.freq || "—")}${metric("Seasonal period", display(forecast.seasonalPeriod))}${metric("ADF p-value", display(forecast.adfPvalue))}</div>
    ${forecast.backtest ? `<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Backtest evaluation</h2><p class="panel-description">Evaluation metrics returned by the backend for the held-out observations.</p></div></div><div class="metric-strip">${metric("MAE", display(forecast.backtest.mae))}${metric("RMSE", display(forecast.backtest.rmse))}${metric("MAPE", forecast.backtest.mape == null ? "Not available" : `${display(forecast.backtest.mape)}%`)}</div></section>` : ""}
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Forecast views</h2><p class="panel-description">History and moving averages · decomposition, when available · forecast interval.</p></div></div><div class="chart-grid">${charts.map(chartCard).join("")}</div></section>
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Forecast values</h2><p class="panel-description">Point estimates and prediction bounds returned by the model.</p></div></div>${forecastRows.length ? renderTable({ columns: ["date", "forecast", "lower", "upper"], rows: forecastRows, totalRows: forecastRows.length }) : `<p class="table-empty">No forecast rows are available.</p>`}</section>
  </div>` : `<div class="notice notice-neutral">${escapeHtml(bundle.forecastError || "No forecast has been generated for this dataset yet.")}</div>`;

  return `<div class="stack">
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Forecast parameters</h2><p class="panel-description">Controls are sent to the Python forecast endpoint. The backend validates its configured horizon limit.</p></div></div>
      <div class="form-grid">
        <label class="field"><span class="field-label">Date column</span><select class="select" id="forecast-date">${dateColumns.map((column) => `<option value="${escapeHtml(column)}" ${column === defaultDate ? "selected" : ""}>${escapeHtml(column)}</option>`).join("")}</select></label>
        <label class="field"><span class="field-label">Target column</span><select class="select" id="forecast-target">${numericColumns.map((column) => `<option value="${escapeHtml(column)}" ${column === defaultTarget ? "selected" : ""}>${escapeHtml(column)}</option>`).join("")}</select></label>
        <label class="field"><span class="field-label">Aggregation</span><select class="select" id="forecast-aggregation"><option value="sum" ${forecast?.params?.agg === "mean" ? "" : "selected"}>Sum</option><option value="mean" ${forecast?.params?.agg === "mean" ? "selected" : ""}>Mean</option></select></label>
        <label class="field"><span class="field-label">Forecast horizon (steps)</span><input class="input" id="forecast-horizon" type="number" min="1" step="1" value="${escapeHtml(forecast?.params?.horizon || 3)}"></label>
        <label class="field"><span class="field-label">Decomposition model</span><select class="select" id="forecast-model"><option value="additive" ${forecast?.params?.decomposition_model === "multiplicative" ? "" : "selected"}>Additive</option><option value="multiplicative" ${forecast?.params?.decomposition_model === "multiplicative" ? "selected" : ""}>Multiplicative</option></select></label>
      </div>
      <div class="button-row" style="margin-top:16px"><button class="button button-primary" id="run-forecast">Run forecast</button><span class="field-hint">Frequency and model diagnostics are inferred by the backend.</span></div>
    </section>
    ${resultBlock}
  </div>`;
}

function renderInsights() {
  const insights = state.bundle.insights || [];
  const categories = ["all", ...new Set(insights.map((item) => item.category))];
  const filtered = state.insightFilter === "all" ? insights : insights.filter((item) => item.category === state.insightFilter);
  return `<div class="stack">
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Rule-based observations</h2><p class="panel-description">These observations are the backend's deterministic outputs; the frontend does not generate narrative claims.</p></div><span class="tag">${insights.length} ITEMS</span></div>
      <div class="tabs" role="tablist" aria-label="Filter insights">${categories.map((category) => `<button class="tab-button" role="tab" aria-selected="${category === state.insightFilter}" data-action="insight-filter" data-value="${escapeHtml(category)}">${escapeHtml(category === "all" ? "All" : titleCase(category))}</button>`).join("")}</div>
      ${filtered.length ? `<div class="insight-list">${filtered.map((item) => `<article class="insight-item ${item.level === "warning" ? "warning" : ""}"><span class="insight-rule" aria-hidden="true"></span><div><span class="insight-category">${escapeHtml(titleCase(item.category))} · ${escapeHtml(titleCase(item.level))}</span><p class="insight-text">${escapeHtml(item.text)}</p></div></article>`).join("")}</div>` : `<p class="table-empty">No insights were returned in this category.</p>`}
    </section>
  </div>`;
}

function renderReports() {
  const isDemo = state.mode === "demo";
  const bundle = state.bundle;
  return `<div class="stack">
    ${isDemo ? `<div class="notice">Report and file-download buttons are disabled in demo mode. They require the connected Python report builder and export endpoints.</div>` : ""}
    <div class="grid-two">
      <section class="panel"><div class="panel-header"><div><h2 class="panel-title">HTML report</h2><p class="panel-description">Downloads the existing self-contained report with interactive Plotly charts.</p></div></div><div class="button-row"><button class="button button-primary" data-action="download-report" ${isDemo ? "disabled" : ""}>Download HTML report</button></div></section>
      <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Data exports</h2><p class="panel-description">Export the cleaned table or the ML-ready transformed view.</p></div></div><div class="button-row"><button class="button" data-action="download-clean" ${isDemo ? "disabled" : ""}>Cleaned CSV</button><button class="button" data-action="download-ml" ${isDemo || !bundle.transform ? "disabled" : ""}>ML-ready CSV</button></div></section>
    </div>
    <section class="panel"><div class="panel-header"><div><h2 class="panel-title">Save this result</h2><p class="panel-description">Stores the cleaned dataset and analysis metadata using the project's SQLite persistence.</p></div></div><div class="form-grid"><label class="field"><span class="field-label">Display name</span><input class="input" id="save-name" placeholder="Optional name for this dataset" maxlength="120"></label></div><div class="button-row" style="margin-top:14px"><button class="button button-primary" data-action="save-bundle" ${isDemo ? "disabled" : ""}>Save dataset</button>${state.mode === "offline" ? `<span class="field-hint">Backend not connected; save is unavailable.</span>` : ""}</div></section>
    <section class="panel"><h2 class="panel-title">Report contents</h2><p class="panel-description">This dataset includes ${display(bundle.charts.length)} generated charts, ${display(bundle.clean.actions.length)} cleaning actions, ${bundle.forecast ? "a forecast result" : "no forecast result"}, and ${display((bundle.insights || []).length)} deterministic insights.</p></section>
  </div>`;
}

function renderSaved() {
  if (state.mode === "demo") return `<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Saved datasets</h2><p class="panel-description">SQLite persistence is a backend feature, not simulated in the demo.</p></div></div><div class="notice">Demo mode never writes to a database. Exit demo and connect the Python API to use saved datasets.</div></section>`;
  if (state.mode !== "connected") return `<section class="empty-state"><div><h2>Saved-dataset API unavailable</h2><p>Connect the Python API to list, preview, download, and delete SQLite-backed datasets.</p><button class="button" data-action="check-connection">Check connection</button></div></section>`;
  if (state.savedDatasets === null) return `<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Saved datasets</h2><p class="panel-description">Loading summaries from the connected API.</p></div></div><button class="button" data-action="refresh-saved">Load saved datasets</button></section>`;
  if (!state.savedDatasets.length) return `<section class="empty-state"><div><h2>No saved datasets</h2><p>Save a result from Reports & export to see it here.</p><button class="button button-primary" data-route="reports">Go to reports</button></div></section>`;
  return `<div class="stack"><section class="panel"><div class="panel-header"><div><h2 class="panel-title">Saved datasets</h2><p class="panel-description">Stored in the connected SQLite database.</p></div><button class="button" data-action="refresh-saved">Refresh</button></div><div class="saved-list">${state.savedDatasets.map((item) => `<article class="saved-row"><div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.filename)} · ${display(item.rows)} rows · ${display(item.columns)} columns · ${escapeHtml(item.savedAt || "")}</small></div><div class="button-row"><button class="button" data-action="preview-saved" data-id="${escapeHtml(item.id)}">Preview</button><button class="button" data-action="download-saved" data-id="${escapeHtml(item.id)}">CSV</button><button class="button button-danger" data-action="delete-saved" data-id="${escapeHtml(item.id)}">Delete</button></div></article>`).join("")}</div></section>${state.savedPreview ? `<section class="panel"><div class="panel-header"><div><h2 class="panel-title">Dataset preview</h2><p class="panel-description">Preview from SQLite. Full export is available from the CSV action.</p></div></div>${renderTable(state.savedPreview, { maxRows: 20 })}</section>` : ""}</div>`;
}

function metric(label, value, note = "") {
  return `<div class="metric"><span class="metric-label">${escapeHtml(label)}</span><strong class="metric-value">${escapeHtml(display(value))}</strong>${note ? `<span class="metric-note">${escapeHtml(note)}</span>` : ""}</div>`;
}

function renderTable(data, options = {}) {
  if (!data || !Array.isArray(data.columns) || !Array.isArray(data.rows) || !data.rows.length) return `<div class="table-empty">No table values are available.</div>`;
  const maxRows = options.maxRows || data.rows.length;
  const rows = data.rows.slice(0, maxRows);
  const hasIndex = rows.some((row) => Object.prototype.hasOwnProperty.call(row, "__index"));
  const columns = [...(hasIndex ? ["__index"] : []), ...data.columns.filter((column) => column !== "__index")];
  const headers = columns.map((column) => `<th scope="col">${escapeHtml(column === "__index" ? "Row" : column)}</th>`).join("");
  const body = rows.map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(display(row[column]))}</td>`).join("")}</tr>`).join("");
  const total = Number.isFinite(data.totalRows) ? data.totalRows : data.rows.length;
  const truncated = data.truncated || total > rows.length;
  return `<div class="table-wrap"><table><thead><tr>${headers}</tr></thead><tbody>${body}</tbody></table></div><div class="table-footer"><span>Showing ${rows.length.toLocaleString()} of ${total.toLocaleString()} rows</span><span>${truncated ? "Preview truncated" : "Complete view"}</span></div>`;
}

function currentCharts() {
  if (!state.bundle) return [];
  if (state.page === "forecast") return state.bundle.forecastCharts || [];
  const all = [...(state.bundle.charts || []), ...(state.bundle.forecastCharts || [])];
  return all.filter((chart) => chart.group === state.selectedGroup);
}

function drawCurrentCharts() {
  const container = document.querySelector("#content");
  if (!container || !["explore", "forecast"].includes(state.page) || !state.bundle) return;
  renderCharts(container, currentCharts());
}

function bindPage() {
  const fileInput = document.querySelector("#file-input");
  const fileMeta = document.querySelector("#file-meta");
  if (fileInput) {
    fileInput.addEventListener("change", () => {
      state.selectedFile = fileInput.files?.[0] || null;
      if (fileMeta) fileMeta.innerHTML = state.selectedFile ? `<strong>${escapeHtml(state.selectedFile.name)}</strong> · ${escapeHtml(formatBytes(state.selectedFile.size))}` : "No file selected";
      const button = document.querySelector("#run-file");
      if (button) button.disabled = !state.selectedFile || state.running;
    });
    const dropzone = document.querySelector("#dropzone");
    if (dropzone) {
      for (const eventName of ["dragenter", "dragover"]) dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.add("dragging"); });
      for (const eventName of ["dragleave", "drop"]) dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.remove("dragging"); });
      dropzone.addEventListener("drop", (event) => {
        const file = event.dataTransfer?.files?.[0];
        if (!file) return;
        state.selectedFile = file;
        if (fileMeta) fileMeta.innerHTML = `<strong>${escapeHtml(file.name)}</strong> · ${escapeHtml(formatBytes(file.size))}`;
        const button = document.querySelector("#run-file");
        if (button) button.disabled = state.running;
      });
    }
  }
  const slider = document.querySelector("#missing-threshold") || document.querySelector("#missing-threshold-url");
  slider?.addEventListener("input", () => {
    const label = document.querySelector("#threshold-label");
    if (label) label.textContent = `${Math.round(Number(slider.value) * 100)}%`;
  });
  document.querySelector("#api-url")?.addEventListener("input", (event) => { state.apiUrl = event.target.value; });
  document.querySelector("#transform-view")?.addEventListener("change", (event) => {
    state.selectedTransform = event.target.value;
    renderShell();
  });
  document.querySelector("#run-file")?.addEventListener("click", runFileAnalysis);
  document.querySelector("#run-url")?.addEventListener("click", runUrlAnalysis);
  document.querySelector("#run-forecast")?.addEventListener("click", submitForecast);
}

function getOptions(suffix = "") {
  const treatment = document.querySelector(`#outlier-treatment${suffix}`)?.value || "flag";
  const threshold = Number(document.querySelector(`#missing-threshold${suffix}`)?.value || 0.60);
  const autoForecast = document.querySelector(`#auto-forecast${suffix}`)?.checked ?? true;
  return { outlierTreatment: treatment, missingThreshold: threshold, autoForecast };
}

async function runFileAnalysis() {
  if (!state.selectedFile || state.running) return;
  if (state.selectedFile.size > 50 * 1024 * 1024) return notify("The selected file exceeds the documented 50 MB limit.", true);
  const supported = /\.(csv|json|xml|txt)$/i.test(state.selectedFile.name);
  if (!supported) return notify("Choose a CSV, JSON, XML, or TXT file.", true);
  await runJob(() => api.analyzeFile(state.selectedFile, getOptions()), "Uploading file and starting analysis");
}

async function runUrlAnalysis() {
  const url = document.querySelector("#api-url")?.value.trim() || state.apiUrl.trim();
  state.apiUrl = url;
  if (!/^https?:\/\//i.test(url)) return notify("Enter a valid public HTTP or HTTPS JSON URL.", true);
  await runJob(() => api.analyzeUrl(url, getOptions("-url")), "Fetching JSON and starting analysis");
}

async function runJob(createJob, initialLabel) {
  state.running = true;
  const buttonFile = document.querySelector("#run-file");
  const buttonUrl = document.querySelector("#run-url");
  if (buttonFile) buttonFile.disabled = true;
  if (buttonUrl) buttonUrl.disabled = true;
  const block = document.querySelector("#progress-block");
  if (block) block.classList.add("visible");
  updateProgress(initialLabel, 0);
  try {
    const { jobId } = await createJob();
    let result;
    do {
      await new Promise((resolve) => setTimeout(resolve, 500));
      result = await api.job(jobId);
      updateProgress(result.stage || "Analysis running", result.progress || 0);
      if (result.status === "error") throw new Error(result.error || "Analysis failed.");
    } while (!["complete", "error"].includes(result.status));
    const session = await api.session();
    if (!session.bundle) throw new Error("The job completed but did not return an analysis bundle.");
    state.bundle = session.bundle;
    state.mode = "connected";
    state.savedDatasets = null;
    state.selectedGroup = state.bundle.charts?.[0]?.group || "distribution";
    state.page = "profile";
    window.location.hash = "#/profile";
    renderShell();
    notify("Analysis completed. Results are from the connected Python backend.");
  } catch (error) {
    notify(error.message || "Unable to run analysis.", true);
    const stage = document.querySelector("#progress-stage");
    if (stage) stage.textContent = "Analysis could not start or failed.";
  } finally {
    state.running = false;
    const button = document.querySelector("#run-file");
    if (button) button.disabled = !state.selectedFile;
    const urlButton = document.querySelector("#run-url");
    if (urlButton) urlButton.disabled = false;
  }
}

function updateProgress(label, fraction) {
  const stage = document.querySelector("#progress-stage");
  const value = document.querySelector("#progress-value");
  const fill = document.querySelector("#progress-fill");
  const bar = document.querySelector('[role="progressbar"]');
  const percent = Math.max(0, Math.min(100, Math.round(Number(fraction) * 100)));
  if (stage) stage.textContent = label;
  if (value) value.textContent = `${percent}%`;
  if (fill) fill.style.width = `${percent}%`;
  if (bar) bar.setAttribute("aria-valuenow", String(percent));
}

async function submitForecast() {
  if (state.mode === "demo") return notify("Demo mode cannot run the Python forecasting algorithm. This sample forecast is illustrative only.", true);
  const settings = {
    dateColumn: document.querySelector("#forecast-date")?.value,
    targetColumn: document.querySelector("#forecast-target")?.value,
    aggregation: document.querySelector("#forecast-aggregation")?.value || "sum",
    horizon: Number(document.querySelector("#forecast-horizon")?.value),
    decompositionModel: document.querySelector("#forecast-model")?.value || "additive",
  };
  const button = document.querySelector("#run-forecast");
  if (button) { button.disabled = true; button.textContent = "Running…"; }
  try {
    const response = await api.forecast(settings);
    state.bundle = response.bundle;
    state.mode = "connected";
    renderShell();
    notify("Forecast updated by the connected Python backend.");
  } catch (error) {
    notify(error.message || "Forecast request failed.", true);
  } finally {
    const currentButton = document.querySelector("#run-forecast");
    if (currentButton) { currentButton.disabled = false; currentButton.textContent = "Run forecast"; }
  }
}

async function refreshConnection(showFeedback = true) {
  try {
    const response = await api.session();
    state.mode = "connected";
    state.bundle = response.bundle || null;
    if (!state.bundle && state.page !== "upload" && state.page !== "saved") state.page = "upload";
    renderShell();
    if (state.bundle) notify("Connected to the Python API.");
  } catch (error) {
    state.mode = "offline";
    if (state.page !== "upload" && !state.bundle) state.page = "upload";
    renderShell();
    if (showFeedback && error?.message) notify(error.message, true);
  }
}

function openDemo() {
  state.bundle = DEMO_BUNDLE;
  state.mode = "demo";
  state.page = "profile";
  state.selectedGroup = "category";
  state.selectedTransform = "scaled_minmax";
  state.savedDatasets = null;
  window.location.hash = "#/profile";
  renderShell();
  notify("Demo sample loaded. All results are synthetic and labeled.");
}

function exitDemo() {
  state.bundle = null;
  state.mode = "offline";
  state.page = "upload";
  state.savedDatasets = null;
  window.location.hash = "#/upload";
  renderShell();
}

function navigate(page) {
  if (!PAGE_INFO[page]) return;
  state.page = page;
  if (page === "saved" && state.mode === "connected") state.savedDatasets = null;
  const targetHash = `#/${page}`;
  if (window.location.hash !== targetHash) window.location.hash = targetHash;
  renderShell();
  if (page === "saved" && state.mode === "connected") loadSaved();
}

async function loadSaved() {
  try {
    const response = await api.saved();
    state.savedDatasets = response.datasets || [];
    renderShell();
  } catch (error) {
    state.savedDatasets = [];
    renderShell();
    notify(error.message || "Saved dataset list is unavailable.", true);
  }
}

async function downloadResponse(requestPromise, filename) {
  try {
    const response = await requestPromise;
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
    notify(`${filename} is ready to download.`);
  } catch (error) {
    notify(error.message || "Download failed.", true);
  }
}

async function handleAction(action, target) {
  const id = target.dataset.id;
  switch (action) {
    case "load-demo": openDemo(); break;
    case "exit-demo": exitDemo(); break;
    case "check-connection": await refreshConnection(); break;
    case "upload-tab": state.uploadTab = target.dataset.value; renderShell(); break;
    case "chart-group": state.selectedGroup = target.dataset.value; renderShell(); break;
    case "insight-filter": state.insightFilter = target.dataset.value; renderShell(); break;
    case "download-report":
      if (state.mode === "demo") return notify("Reports are disabled for synthetic demo data.", true);
      await downloadResponse(api.report(), "insight_report.html");
      break;
    case "download-clean":
      if (state.mode === "demo") return notify("CSV export needs the connected Python backend.", true);
      await downloadResponse(api.downloadClean(), "cleaned_data.csv");
      break;
    case "download-ml":
      if (state.mode === "demo") return notify("CSV export needs the connected Python backend.", true);
      await downloadResponse(api.downloadMlReady(), "ml_ready_data.csv");
      break;
    case "save-bundle": await saveBundle(); break;
    case "refresh-saved": await loadSaved(); break;
    case "preview-saved": await previewSaved(id); break;
    case "download-saved": await downloadResponse(api.savedCsv(id), `dataset_${id}.csv`); break;
    case "delete-saved": await deleteSaved(id); break;
  }
}

async function saveBundle() {
  const name = document.querySelector("#save-name")?.value.trim() || null;
  if (state.mode === "demo") return notify("Demo mode never writes to SQLite.", true);
  try {
    const result = await api.save(name);
    notify(`Dataset saved with ID ${display(result.datasetId)}.`);
  } catch (error) {
    notify(error.message || "Save failed.", true);
  }
}

async function previewSaved(id) {
  try {
    const result = await api.savedPreview(id);
    state.savedPreview = result.data;
    renderShell();
  } catch (error) {
    notify(error.message || "Could not load saved preview.", true);
  }
}

async function deleteSaved(id) {
  if (!window.confirm("Delete this saved dataset and its stored cleaned table? This cannot be undone.")) return;
  try {
    await api.removeSaved(id);
    state.savedPreview = null;
    await loadSaved();
    notify("Saved dataset deleted.");
  } catch (error) {
    notify(error.message || "Delete failed.", true);
  }
}

function notify(message, isError = false) {
  const toast = document.querySelector("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  window.clearTimeout(notify.timer);
  notify.timer = window.setTimeout(() => toast.classList.remove("visible"), 4200);
}

document.addEventListener("click", async (event) => {
  const route = event.target.closest("[data-route]");
  if (route) return navigate(route.dataset.route);
  const action = event.target.closest("[data-action]");
  if (action) await handleAction(action.dataset.action, action);
});

window.addEventListener("hashchange", () => {
  const page = routeFromHash();
  if (page !== state.page) {
    state.page = page;
    renderShell();
    if (page === "saved" && state.mode === "connected" && state.savedDatasets === null) loadSaved();
  }
});

renderShell();
refreshConnection(false);
