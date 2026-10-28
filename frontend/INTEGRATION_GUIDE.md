# Antigravity integration guide

## Current boundary

This directory is a frontend-only project. It does not contain an HTTP API server and does not change or bundle the Python backend. The supplied GitHub project is a Streamlit application; its current source has no browser API matching the frontend routes. The API definitions in [`API_CONTRACT.md`](./API_CONTRACT.md) are the integration target, not evidence of a completed connection.

Keep the Streamlit entrypoint and Python core unchanged unless you intentionally make a separate integration change in your own project. Add an HTTP adapter as a new layer around the existing functions; do not put HTTP/session concerns into `src/pipeline.py`, `src/models.py`, cleaning, analysis, chart, or report modules.

## 1. Place the frontend beside your Python project

Copy this entire directory into your working project, for example:

```text
Auto-Insight-Report-Generator/
  app.py                    # existing Streamlit entrypoint; leave unchanged
  src/                      # existing analysis engine; leave unchanged
  frontend/                 # copy this standalone deliverable here
```

Then install and build the frontend from `frontend/`:

```bash
cd frontend
npm ci
cp .env.example .env.local
```

Set `VITE_API_PROXY_TARGET` in `.env.local` to the local address of the API service you add. The default is `http://127.0.0.1:8000`. `VITE_API_BASE_URL=/api` keeps browser requests same-origin through Vite in development.

## 2. Add an API adapter separately

The Python code paths to adapt are:

- `src.pipeline.run_pipeline(filename, content, config, progress)` creates the `AnalysisBundle` and calls a `(stage_label, fraction)` progress callback.
- `src.pipeline.rerun_forecast(bundle, ForecastParams(...))` returns a new bundle containing the recalculated forecast, charts, and insights.
- `src.report.build_report(bundle)` returns UTF-8 bytes for the self-contained HTML report.
- `src.database.get_engine()`, `init_db(engine)`, `save_bundle(bundle, name, engine)`, `list_datasets(engine)`, `load_clean_table(dataset_id, limit, engine)`, and `delete_dataset(dataset_id, engine)` are the existing SQLite helpers.
- `src.ingest.load_from_url(url)` parses an API JSON URL into an `IngestResult`; the existing Streamlit URL path converts its parsed table back to JSON bytes and passes it through `run_pipeline`. Mirror that existing path rather than adding a new analysis implementation.

Create one session-aware service/adapter layer that owns the active bundle and in-flight job records. For file analysis, parse multipart `file` and JSON-string `options`, map the options to the existing `PipelineConfig`/`CleaningConfig`/`OutlierTreatment` classes, then run `run_pipeline` as a background job. The progress callback updates the session's job state. `GET /api/jobs/{jobId}` reports it; on completion store the final bundle for `GET /api/session`.

For the URL endpoint, accept only public HTTP/HTTPS JSON sources, use the existing ingestion limits/timeouts, and add server-side protections against loopback/private/link-local destinations, DNS rebinding, embedded credentials, and redirects to private addresses. The current `load_from_url` helper checks HTTP/HTTPS and its timeout/response-size cap but does not implement a complete SSRF policy; do not expose unrestricted server-side fetch to arbitrary browser input.

For forecasting, map `dateColumn`, `targetColumn`, `aggregation`, `horizon`, and `decompositionModel` to `ForecastParams(date_col=..., target_col=..., agg=..., horizon=..., decomposition_model=...)`. Replace the active session bundle with the returned value from `rerun_forecast` and serialize it back as `{ "bundle": ... }`.

For report/download routes, use the active session bundle. `build_report` already returns the self-contained HTML bytes; send them as `text/html; charset=utf-8` with an attachment filename. Use `bundle.clean.df.to_csv(index=False)` for the cleaned CSV and `bundle.transform.ml_ready.to_csv(index=False)` for the ML-ready CSV (return a clear 409 when no transform exists). These endpoints must not generate output from the synthetic frontend sample.

For SQLite operations, initialize/reuse an engine consistently. Map `DatasetRecord` fields to the summary names consumed by the frontend (`id`, `name`, `filename`, `rows`, `columns`, `savedAt`). Use `load_clean_table(id, limit=100, engine)` for a preview and `load_clean_table(id, limit=None, engine)` for the saved CSV route. The delete action is destructive; the UI asks for confirmation before it sends `DELETE`.

## 3. Serialize for the browser

The core returns dataclasses, enums, pandas objects, Plotly figures, and timestamps. Normalize these in the adapter instead of changing core models:

1. Enum values become their `.value` strings.
2. Dataclasses become plain objects with the frontend field names documented in `API_CONTRACT.md` (including the small casing differences such as `quality_before` → `qualityBefore`, `forecast_charts` → `forecastCharts`, and `rows_affected` → `rowsAffected`).
3. DataFrames and Series become bounded `TablePreview` objects or arrays of `{date,value}` records. Represent timestamps as ISO strings, missing values as JSON `null`, and never send pandas/numpy scalar objects directly.
4. For `ChartSpec`, include `id`, `title`, enum `kind`/`group`, `columns`, `description`, and `figure`. Serialize Plotly traces/layout to JSON and convert all arrays to ordinary JSON arrays. The Bklit adapters need `bar` traces with `x`/`y` arrays and date-aligned `scatter` line traces; other chart specs fall back to Plotly.js.
5. Keep table previews bounded (the pipeline raw preview uses `RAW_PREVIEW_ROWS`, currently 200) and avoid returning entire datasets in the session bundle. Full CSVs use their dedicated download routes.

The frontend session must be isolated per browser. Use an HTTP-only session cookie; avoid putting raw data or access tokens in local storage. Validate every object identifier on the server, enforce request-size/time limits, and do not expose the development API server to the public internet without authentication and an explicit security review.

## 4. Run both services locally

Terminal 1: start the API adapter on `127.0.0.1:8000`.

Terminal 2:

```bash
cd frontend
npm run dev
```

Vite proxies `/api/*` to `VITE_API_PROXY_TARGET`. For production, run `npm run build`, serve `frontend/dist/` as static files, and reverse-proxy `/api/*` to the Python adapter on the same origin. Avoid a separate cross-origin API if you can; if required, enable narrowly scoped credentialed CORS and CSRF protection.

## 5. Verify before calling it integrated

1. `GET /api/session` succeeds with `bundle:null` in a fresh session.
2. Upload small CSV, JSON, XML, and TXT fixtures. Verify file-size rejection, parse errors, progress updates, and `GET /api/session` returning the completed bundle.
3. Test a public JSON source and rejected private/loopback URL destinations.
4. Verify the Profile, Explore, Forecast, Insights, Reports, and Saved datasets pages use server-returned data. Confirm compatible category bars and date-series lines render through Bklit and other chart types use Plotly.
5. Run a forecast, download the self-contained HTML report and both CSV exports, save/list/preview/delete a dataset, and confirm the UI reports each error accurately.
6. Check browser console/network requests and Python logs. Test responsive layouts on narrow viewports.
7. Test that demo mode still makes no analysis, report, export, forecast, or database writes.

Only after these checks should you describe backend integration as complete. This frontend-only delivery has been verified against its isolated synthetic demo and local Vite build, not against the Python API.
