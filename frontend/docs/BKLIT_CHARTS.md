# Bklit chart integration notes

## Official sources consulted

- Bklit chart gallery: https://bklit.com/charts
- Bklit component installation: https://bklit.com/docs/installation
- Bklit BarChart documentation: https://bklit.com/docs/components/bar-chart
- Bklit LineChart documentation: https://bklit.com/docs/components/line-chart
- Official bar-chart registry manifest: https://bklit.com/r/bar-chart.json
- Upstream source repository: https://github.com/bklit/bklit-ui

The Bklit components are installed as actual source components from the official registry (via the documented shadcn registry flow), not recreated placeholders. Their React code stays under `src/components/charts/` and is mounted through small React islands in `src/charts/`; the surrounding application shell and pages remain vanilla HTML, CSS, and JavaScript.

## Where Bklit is used

- **Categorical bar charts:** backend chart specs with `kind: "bar"` and ordinary `bar` traces (`x`/`y` arrays) are mapped to Bklit's `BarChart`, `Bar`, `BarYAxis`, `Grid`, and `ChartTooltip` components. Actual categories and numeric values are passed into the component; long lists are ranked and capped for legibility.
- **Time-series line charts:** `kind: "line"` chart specs in the `time_series` group are mapped to Bklit's `LineChart`, `Line`, `Grid`, `XAxis`, and `ChartTooltip` when their traces contain aligned, parseable date arrays and numeric values. Series labels and colors are preserved in a compact legend.

## Where Plotly remains

Plotly.js is dynamically imported as a real interactive fallback for figure types whose meaning would be lost by the current Bklit adapters: histograms/box plots, scatter and heatmap matrices, decomposition panels, and forecast charts with prediction intervals. The frontend consumes the returned figure data, not rasterized chart screenshots. Chart libraries are split into on-demand chunks; the Plotly chunk is not loaded on initial upload/profile pages.

## Dark chart styling

The document defaults to the dark theme. `src/styles.css` is the single source for graphite surfaces, warm-white text, muted ice-blue accents, and the coordinated chart series palette. `src/tailwind.css` maps those tokens into the Bklit chart utilities; Bklit axes, grid, tooltip, date ticker, series legend, focus and selected-point states inherit them. Chart surfaces are transparent so no light plot area can appear inside a dark page. The Plotly renderer applies the same palette and readable axis, legend, tooltip and colorbar styling to fallback figures, including a graphite-to-ice scale for heatmaps. Synthetic chart specs deliberately omit presentation colors so charts do not carry a competing default palette.

## Demonstration data

`src/demo/demo-data.js` contains a synthetic monthly-sales sample solely to demonstrate navigation, tables, and the real interactive chart components before a backend is connected. It is only loaded after an explicit “Open demo workspace” action, and every screen carries a “Demo data · synthetic sample” notice. Demo actions never call a report download, execute a Python forecast, or write to SQLite.
