# Auto-Insight Frontend

A standalone, responsive frontend for the Auto-Insight Report Generator. The application shell and page views are vanilla HTML, CSS, and JavaScript. React is used only inside isolated chart mounts for official Bklit chart components; Vite bundles the app and its chart modules.

> **Backend status:** This deliverable is not connected to a running Python API. The existing repository exposes its application through Streamlit and does not currently provide the HTTP routes specified in [`API_CONTRACT.md`](./API_CONTRACT.md). The frontend is ready for Antigravity integration, but upload, forecast, report generation/download, SQLite persistence, and connected results are not claimed as working until the API is implemented and tested. The existing Python code has not been changed by this standalone frontend project.

## Requirements

- Node.js `^20.19.0` or `>=22.12.0`
- npm 10 or a compatible npm version
- A Python API implementing the routes in `API_CONTRACT.md` for connected functionality

## Run locally

```bash
npm ci
cp .env.example .env.local
# Edit VITE_API_PROXY_TARGET if your Python API is not at http://127.0.0.1:8000
npm run dev
```

Open the local URL printed by Vite (normally `http://127.0.0.1:5173`). The development server proxies same-origin `/api/*` requests to `VITE_API_PROXY_TARGET`. Without a backend, the app clearly shows **Backend not connected**; choose **Open demo workspace** to inspect the interface with isolated synthetic data.

Create and preview a production bundle:

```bash
npm run build
npm run preview
```

The compiled static site is written to `dist/`. In production, route `/api/*` to the Python API on the same origin where practical. For a different API origin, set `VITE_API_BASE_URL` at build time and configure credentialed CORS and CSRF protection appropriately.

## What's included

- Upload workflow for CSV, JSON, XML, and TXT, cleaning controls, progress state, and JSON URL ingestion form.
- Profile and cleaning review, transformation previews, chart exploration, insights, forecast controls/results, report/CSV export controls, and saved-dataset views.
- Genuine official Bklit interactive bar and time-series line components for compatible chart specs. Plotly.js is loaded as a lazy fallback for chart types whose semantics are not covered by those adapters.
- A deliberately isolated synthetic demonstration sample, loaded only after an explicit action. Every demo view is labeled as synthetic; forecast, report/export, and save actions are disabled or explicitly unavailable in demo mode.
- A proposed, concrete HTTP interface in [`API_CONTRACT.md`](./API_CONTRACT.md) and step-by-step backend mapping in [`INTEGRATION_GUIDE.md`](./INTEGRATION_GUIDE.md).

The demo is illustrative, not a pipeline result, not a model forecast, and not a backend integration test. It does not send its synthetic rows to the API or write to SQLite.

## Project structure

```text
index.html
vite.config.js
components.json
package.json
package-lock.json
.env.example
public/
  manus-routes.json
src/
  main.js                 Vanilla application shell, route views, and interactions
  api.js                  Same-origin HTTP client for the documented API contract
  styles.css              Application design system and responsive styles
  tailwind.css            Tailwind entry/theme variables required by Bklit source components
  chart-island.css        Isolated Bklit chart-surface styles
  charts/
    renderer.jsx          Lazy Bklit/Plotly chart bridge
    BklitBar.jsx          Official Bklit bar-component adapter
    BklitLine.jsx         Official Bklit line-component adapter
  components/charts/      Source files installed from the official Bklit registry
  demo/demo-data.js       Synthetic-only showcase bundle
  docs/BKLIT_CHARTS.md    Official chart sources and compatibility notes
```

## Design and behavior notes

The visual direction is editorial and restrained, with a dark graphite canvas, subtly varied charcoal surfaces, warm-white primary text, muted secondary text, and a selective ice-blue accent. Reusable CSS tokens cover the application and both chart systems. Bklit charts use transparent surfaces, subdued grids, readable labels, graphite tooltips, and a coordinated ice/sage/ochre/clay/slate series palette; Plotly fallbacks receive the same theme. Layouts reflow to a horizontal mobile navigation and single-column content; table wrappers remain horizontally scrollable for wide results. Focus indicators are visible and reduced-motion preferences are respected.

For the exact Bklit registry source references and chart-type selection rationale, see [`docs/BKLIT_CHARTS.md`](./docs/BKLIT_CHARTS.md).
