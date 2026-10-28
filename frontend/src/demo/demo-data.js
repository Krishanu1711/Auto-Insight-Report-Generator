// Synthetic showcase data only. It is loaded only after the user explicitly chooses
// “Open demo workspace”; it is never presented as a connected backend result.
const months = Array.from({ length: 24 }, (_, index) => {
  const month = new Date(Date.UTC(2024, index, 1));
  const date = month.toISOString().slice(0, 10);
  const seasonal = [0, 8, 16, 10, 22, 34, 29, 40, 27, 18, 13, 31][index % 12];
  const revenue = 47000 + index * 1680 + seasonal * 180 + (index % 4) * 570;
  const orders = Math.round(820 + index * 22 + seasonal * 1.7 + (index % 3) * 12);
  const region = ["North", "South", "East", "West"][index % 4];
  const channel = ["Online", "Retail", "Partner"][index % 3];
  return { date, revenue, orders, region, channel };
});

const byRegion = new Map();
for (const row of months) {
  const current = byRegion.get(row.region) || { revenue: 0, orders: 0 };
  current.revenue += row.revenue;
  current.orders += row.orders;
  byRegion.set(row.region, current);
}
const regions = [...byRegion.entries()].sort((a, b) => b[1].revenue - a[1].revenue);
const revenue = months.map((row) => row.revenue);
const orders = months.map((row) => row.orders);
const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const meanRevenue = mean(revenue);
const meanOrders = mean(orders);
const covariance = revenue.reduce((sum, value, i) => sum + (value - meanRevenue) * (orders[i] - meanOrders), 0);
const varianceOrders = orders.reduce((sum, value) => sum + (value - meanOrders) ** 2, 0);
const coefficient = covariance / varianceOrders;
const intercept = meanRevenue - coefficient * meanOrders;
const predictions = orders.map((value) => intercept + coefficient * value);
const ssTotal = revenue.reduce((sum, value) => sum + (value - meanRevenue) ** 2, 0);
const ssResidual = revenue.reduce((sum, value, i) => sum + (value - predictions[i]) ** 2, 0);
const r2 = 1 - ssResidual / ssTotal;
const seriesMean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
const sma = months.map((_, i) => i < 2 ? null : seriesMean(revenue.slice(i - 2, i + 1)));
const ema = [];
const alpha = 2 / (4 + 1);
revenue.forEach((value, i) => ema.push(i === 0 ? value : alpha * value + (1 - alpha) * ema[i - 1]));

const averageByRegion = regions.map(([name, values]) => ({ name, revenue: Math.round(values.revenue / 6) }));
const cleanPreview = { columns: ["date", "revenue", "orders", "region", "channel"], rows: months, totalRows: months.length, truncated: false };
const rawPreview = { ...cleanPreview, rows: months.map((row, i) => i === 5 ? { ...row, channel: null } : row) };
const trendLine = revenue.map((value, i) => Math.round(value * (0.965 + i * 0.0014)));
const futureDates = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"];
const forecastValues = [0, 1, 2, 3].map((step) => Math.round(revenue.at(-1) + 1700 * (step + 1)));

const charts = [
  {
    id: "category__revenue_region", title: "Average monthly revenue by region", kind: "bar", group: "category",
    columns: ["region", "revenue"], description: "Average revenue per month, grouped by region.",
    figure: { data: [{ type: "bar", name: "Average revenue", x: averageByRegion.map((row) => row.name), y: averageByRegion.map((row) => row.revenue) }], layout: { barmode: "group", xaxis: { title: "Region" }, yaxis: { title: "Revenue ($)" } } },
  },
  {
    id: "ts__monthly_revenue", title: "Monthly revenue with moving average", kind: "line", group: "time_series",
    columns: ["date", "revenue"], description: "Observed monthly revenue and its three-month SMA.",
    figure: { data: [
      { type: "scatter", mode: "lines+markers", name: "Revenue", x: months.map((row) => row.date), y: revenue, line: { width: 2 } },
      { type: "scatter", mode: "lines", name: "Three-month SMA", x: months.map((row) => row.date), y: sma, line: { width: 2, dash: "dash" } },
    ], layout: { xaxis: { title: "Month" }, yaxis: { title: "Revenue ($)" }, legend: { orientation: "h", y: 1.12 } } },
  },
  {
    id: "hist__revenue", title: "Revenue distribution", kind: "histogram", group: "distribution",
    columns: ["revenue"], description: "Monthly revenue values grouped into six evenly spaced ranges.",
    figure: { data: [{ type: "bar", name: "Months", x: ["$47k–$57k", "$57k–$67k", "$67k–$77k", "$77k–$87k", "$87k–$97k", "$97k–$107k"], y: [2, 4, 5, 5, 5, 3] }], layout: { xaxis: { title: "Revenue range" }, yaxis: { title: "Month count" }, bargap: 0.18 } },
  },
  {
    id: "rel__orders_revenue", title: "Orders and revenue", kind: "scatter", group: "relationship",
    columns: ["orders", "revenue"], description: "Monthly order volume compared with revenue; this is synthetic showcase data.",
    figure: { data: [{ type: "scatter", mode: "markers", name: "Month", x: orders, y: revenue, text: months.map((row) => row.date.slice(0, 7)), marker: { size: 8, opacity: 0.8 } }], layout: { xaxis: { title: "Orders" }, yaxis: { title: "Revenue ($)" } } },
  },
  {
    id: "rel__correlation", title: "Numeric relationship matrix", kind: "heatmap", group: "relationship",
    columns: ["revenue", "orders"], description: "A correlation matrix calculated from the synthetic monthly sample.",
    figure: { data: [{ type: "heatmap", x: ["revenue", "orders"], y: ["revenue", "orders"], z: [[1, 0.84], [0.84, 1]], zmin: -1, zmax: 1, text: [["1.00", "0.84"], ["0.84", "1.00"]], texttemplate: "%{text}" }], layout: { xaxis: { side: "bottom" }, yaxis: { autorange: "reversed" } } },
  },
];

const forecast = {
  params: { date_col: "date", target_col: "revenue", agg: "sum", horizon: 4, decomposition_model: "additive" },
  freq: "MS", seasonalPeriod: 12,
  series: months.map((row, i) => ({ date: row.date, value: row.revenue, sma: sma[i], ema: Math.round(ema[i]) })),
  smaWindow: 3, emaSpan: 4,
  decomposition: {
    model: "additive", period: 12,
    observed: months.map((row) => ({ date: row.date, value: row.revenue })),
    trend: months.map((row, i) => ({ date: row.date, value: trendLine[i] })),
    seasonal: months.map((row, i) => ({ date: row.date, value: Math.round((row.revenue - trendLine[i]) * 0.55) })),
    resid: months.map((row, i) => ({ date: row.date, value: row.revenue - trendLine[i] })),
  },
  adfPvalue: 0.24, order: [1, 1, 1], aic: 314.82,
  backtest: { actual: months.slice(-4).map((row) => ({ date: row.date, value: row.revenue })), predicted: months.slice(-4).map((row, i) => ({ date: row.date, value: row.revenue - 1500 + i * 290 })), mae: 1510, rmse: 1792, mape: 2.1 },
  forecast: futureDates.map((date, i) => ({ date, forecast: forecastValues[i], lower: forecastValues[i] - 4200 - i * 350, upper: forecastValues[i] + 4200 + i * 350 })),
  warnings: ["This synthetic showcase forecast is illustrative only; it is not a model output from your dataset."],
};

const forecastCharts = [
  {
    id: "ts__trend", title: "Trend and moving averages", kind: "line", group: "time_series",
    columns: ["date", "revenue"], description: "Observed revenue, 3-month SMA, and 4-month EMA.",
    figure: { data: [
      { type: "scatter", mode: "lines", name: "Revenue", x: months.map((row) => row.date), y: revenue, line: { width: 2 } },
      { type: "scatter", mode: "lines", name: "SMA (3)", x: months.map((row) => row.date), y: sma, line: { dash: "dash" } },
      { type: "scatter", mode: "lines", name: "EMA (4)", x: months.map((row) => row.date), y: ema.map(Math.round), line: { dash: "dot" } },
    ], layout: { xaxis: { title: "Month" }, yaxis: { title: "Revenue ($)" }, legend: { orientation: "h", y: 1.12 } } },
  },
  {
    id: "ts__decomposition", title: "Additive decomposition", kind: "decomposition", group: "time_series",
    columns: ["date", "revenue"], description: "Observed, trend, seasonal, and residual panels.",
    figure: { data: [
      { type: "scatter", mode: "lines", name: "Observed", x: months.map((row) => row.date), y: revenue, xaxis: "x", yaxis: "y" },
      { type: "scatter", mode: "lines", name: "Trend", x: months.map((row) => row.date), y: trendLine, xaxis: "x", yaxis: "y2" },
      { type: "scatter", mode: "lines", name: "Seasonal", x: months.map((row) => row.date), y: months.map((row, i) => Math.round((row.revenue - trendLine[i]) * 0.55)), xaxis: "x", yaxis: "y3" },
      { type: "scatter", mode: "lines", name: "Residual", x: months.map((row) => row.date), y: months.map((row, i) => row.revenue - trendLine[i]), xaxis: "x", yaxis: "y4" },
    ], layout: { grid: { rows: 4, columns: 1, pattern: "independent" }, showlegend: false, xaxis: { title: "Month" }, yaxis: { title: "Observed" }, yaxis2: { title: "Trend" }, yaxis3: { title: "Seasonal" }, yaxis4: { title: "Residual" } } },
  },
  {
    id: "ts__forecast", title: "Forecast with 95% interval", kind: "forecast", group: "time_series",
    columns: ["date", "revenue"], description: "Observed history and synthetic demo projection with an illustrative interval.",
    figure: { data: [
      { type: "scatter", mode: "lines", name: "Observed", x: months.map((row) => row.date), y: revenue, line: { width: 2 } },
      { type: "scatter", mode: "lines", name: "95% upper", x: futureDates, y: forecast.forecast.map((row) => row.upper), line: { width: 0 }, showlegend: false, hoverinfo: "skip" },
      { type: "scatter", mode: "lines", name: "95% interval", x: futureDates, y: forecast.forecast.map((row) => row.lower), fill: "tonexty", line: { width: 0 }, hoverinfo: "skip" },
      { type: "scatter", mode: "lines+markers", name: "Demo forecast", x: futureDates, y: forecastValues, line: { dash: "dash", width: 2 }, marker: { size: 6 } },
    ], layout: { xaxis: { title: "Month" }, yaxis: { title: "Revenue ($)" }, legend: { orientation: "h", y: 1.12 } } },
  },
];

export const DEMO_BUNDLE = {
  demo: true,
  source: {
    filename: "sample_monthly_sales_demo.csv", format: "csv", sha256: "demo-only", rowsRaw: months.length, columnsRaw: 5,
    unstructured: false, rawPreview, warnings: ["Synthetic monthly retail sample created for interface demonstration only."],
  },
  clean: {
    preview: cleanPreview,
    qualityBefore: { n_rows: 24, n_cols: 5, missing_cells: 1, duplicate_rows: 0, outlier_cells: 0 },
    qualityAfter: { n_rows: 24, n_cols: 5, missing_cells: 0, duplicate_rows: 0, outlier_cells: 0 },
    actions: [{ step: "impute", column: "channel", description: "Filled one missing categorical value using the most frequent value.", rowsAffected: 1 }],
    renameMap: {}, warnings: [],
  },
  profile: {
    rows: 24, columnsCount: 5, primaryDateColumn: "date", memoryMb: 0.01,
    columns: [
      { name: "date", dtype: "datetime64[ns]", kind: "datetime", missing: 0, missingPct: 0, unique: 24, uniqueRatio: 1, sampleValues: ["2024-01-01", "2024-02-01", "2024-03-01"], dateRange: [months[0].date, months.at(-1).date] },
      { name: "revenue", dtype: "int64", kind: "numeric", missing: 0, missingPct: 0, unique: 24, uniqueRatio: 1, sampleValues: [String(revenue[0]), String(revenue[1]), String(revenue[2])], numericStats: { min: Math.min(...revenue), max: Math.max(...revenue), mean: meanRevenue, median: meanRevenue, std: 14400, skew: 0.03 } },
      { name: "orders", dtype: "int64", kind: "numeric", missing: 0, missingPct: 0, unique: 24, uniqueRatio: 1, sampleValues: [String(orders[0]), String(orders[1]), String(orders[2])], numericStats: { min: Math.min(...orders), max: Math.max(...orders), mean: meanOrders, median: meanOrders, std: 162, skew: 0.02 } },
      { name: "region", dtype: "object", kind: "categorical", missing: 0, missingPct: 0, unique: 4, uniqueRatio: 0.167, sampleValues: ["North", "South", "East"], topValues: regions.map(([name]) => [name, months.filter((row) => row.region === name).length]) },
      { name: "channel", dtype: "object", kind: "categorical", missing: 0, missingPct: 0, unique: 3, uniqueRatio: 0.125, sampleValues: ["Online", "Retail", "Partner"], topValues: [["Online", 8], ["Retail", 8], ["Partner", 8]] },
    ],
  },
  transform: {
    views: {
      scaled_minmax: { columns: ["revenue", "orders"], rows: months.slice(0, 5).map((row, i) => ({ revenue: Number(((row.revenue - Math.min(...revenue)) / (Math.max(...revenue) - Math.min(...revenue))).toFixed(3)), orders: Number(((row.orders - Math.min(...orders)) / (Math.max(...orders) - Math.min(...orders))).toFixed(3)) })), totalRows: months.length, truncated: true },
      scaled_standard: { columns: ["revenue", "orders"], rows: months.slice(0, 5).map((row, i) => ({ revenue: Number(((row.revenue - meanRevenue) / 14400).toFixed(3)), orders: Number(((row.orders - meanOrders) / 162).toFixed(3)) })), totalRows: months.length, truncated: true },
      label_encoded: { columns: ["region", "channel"], rows: months.slice(0, 5).map((row) => ({ region: ["East", "North", "South", "West"].indexOf(row.region), channel: ["Online", "Partner", "Retail"].indexOf(row.channel) })), totalRows: months.length, truncated: true },
      one_hot: { columns: ["region_East", "region_North", "region_South", "region_West", "channel_Online", "channel_Partner", "channel_Retail"], rows: months.slice(0, 5).map((row) => Object.fromEntries(["East", "North", "South", "West"].map((region) => [`region_${region}`, Number(row.region === region)]).concat(["Online", "Partner", "Retail"].map((channel) => [`channel_${channel}`, Number(row.channel === channel)])))), totalRows: months.length, truncated: true },
      binned: { columns: ["revenue", "orders"], rows: months.slice(0, 5).map((row) => ({ revenue: row.revenue > meanRevenue ? "high" : "low", orders: row.orders > meanOrders ? "high" : "low" })), totalRows: months.length, truncated: true },
      ml_ready: { columns: ["revenue", "orders", "region_East", "region_North", "region_South", "region_West"], rows: months.slice(0, 5).map((row) => ({ revenue: Number(((row.revenue - meanRevenue) / 14400).toFixed(3)), orders: Number(((row.orders - meanOrders) / 162).toFixed(3)), region_East: Number(row.region === "East"), region_North: Number(row.region === "North"), region_South: Number(row.region === "South"), region_West: Number(row.region === "West") })), totalRows: months.length, truncated: true },
    }, warnings: [],
  },
  analysis: {
    descriptive: { columns: ["count", "mean", "std", "min", "25%", "50%", "75%", "max"], rows: [
      { __index: "revenue", count: 24, mean: meanRevenue, std: 14400, min: Math.min(...revenue), "25%": 64800, "50%": meanRevenue, "75%": 88000, max: Math.max(...revenue) },
      { __index: "orders", count: 24, mean: meanOrders, std: 162, min: Math.min(...orders), "25%": 1060, "50%": meanOrders, "75%": 1320, max: Math.max(...orders) },
    ], totalRows: 2, truncated: false },
    correlation: { columns: ["revenue", "orders"], rows: [{ __index: "revenue", revenue: 1, orders: 0.84 }, { __index: "orders", revenue: 0.84, orders: 1 }], totalRows: 2, truncated: false },
    topPairs: [{ x: "orders", y: "revenue", r: 0.84 }],
    regression: { x: "orders", y: "revenue", coef: coefficient, intercept, r2, mae: 570, rmse: 681, n_train: 19, n_test: 5, y_test: revenue.slice(-5), y_pred: predictions.slice(-5) },
    textSummary: null, warnings: [],
  },
  charts,
  forecast,
  forecastCharts,
  forecastError: null,
  insights: [
    { level: "info", category: "distribution", text: "Demo sample: revenue values increase across the 24 synthetic monthly records." },
    { level: "info", category: "relationship", text: "Demo sample: orders and revenue move together in this illustrative dataset (r ≈ 0.84)." },
    { level: "warning", category: "quality", text: "Demo sample: one missing channel value was imputed for the cleaning walkthrough." },
    { level: "info", category: "timeseries", text: "Demo sample: monthly history is provided to demonstrate forecast controls and result presentation." },
  ],
  config: { autoForecast: true, outlierTreatment: "flag", dropColumnMissingPct: 0.6 },
  createdAt: new Date().toISOString(),
};
