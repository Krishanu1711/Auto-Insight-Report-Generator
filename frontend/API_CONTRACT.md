# Frontend ↔ Python API contract

## Status and conventions

This is the interface the standalone frontend expects; it is **not implemented by this deliverable**. The current Python project has no HTTP API for these routes. Do not treat a successful frontend build or synthetic demo as backend integration.

- Base path: `/api`
- JSON: UTF-8, `Content-Type: application/json`
- Frontend requests use `credentials: "same-origin"`; maintain a per-browser session with an HTTP-only, `SameSite=Lax` cookie. Use `Secure` over HTTPS.
- Same-origin proxying is preferred. If the API is on another origin, configure credentialed CORS and CSRF protection; do not use wildcard CORS with cookies.
- Errors: non-2xx responses should be JSON such as `{"error":"Readable explanation","code":"OPTIONAL_CODE","details":{}}`. The UI displays `error` (or `message`) and otherwise falls back to the HTTP status.
- JSON `NaN`/infinity values must be converted to `null`; datetimes must be ISO-8601 strings; enums must be serialized to their string values.

## Routes

| Method | Path | Purpose | Expected success response |
| --- | --- | --- | --- |
| `GET` | `/api/session` | Test API/session availability and retrieve the active analysis | `200 {"bundle": AnalysisBundleJSON \| null}` |
| `POST` | `/api/analyze` | Start file analysis | `202 {"jobId":"opaque-id"}` |
| `POST` | `/api/analyze-url` | Start analysis from a public JSON URL | `202 {"jobId":"opaque-id"}` |
| `GET` | `/api/jobs/{jobId}` | Read progress/result state | `200 JobStatusJSON` |
| `POST` | `/api/forecast` | Rerun the forecast on the active session bundle | `200 {"bundle": AnalysisBundleJSON}` |
| `POST` | `/api/report` | Build/download the existing HTML report | `200 text/html` bytes with `Content-Disposition: attachment` |
| `GET` | `/api/download/clean.csv` | Download cleaned data for the active session | `200 text/csv` bytes with `Content-Disposition: attachment` |
| `GET` | `/api/download/ml-ready.csv` | Download the active bundle's ML-ready transform | `200 text/csv` bytes with `Content-Disposition: attachment` |
| `POST` | `/api/save` | Persist the active bundle through the project's SQLite layer | `201 {"datasetId":123}` |
| `GET` | `/api/saved` | List saved-dataset summaries | `200 {"datasets":[SavedDatasetSummary...]}` |
| `GET` | `/api/saved/{id}?limit=100` | Return a saved cleaned-table preview | `200 {"data":TablePreview}` |
| `GET` | `/api/saved/{id}/csv` | Download the complete saved cleaned table | `200 text/csv` bytes with `Content-Disposition: attachment` |
| `DELETE` | `/api/saved/{id}` | Delete one saved dataset and its cleaned table | `204` or `200 {"ok":true}` |

### Session and jobs

A fresh session returns `{"bundle":null}`. A successful analysis job updates that session's active bundle. Job state follows:

```json
{
  "jobId": "opaque-id",
  "status": "queued",
  "stage": "Reading file",
  "progress": 0.1
}
```

`status` is `queued`, `running`, `complete`, or `error`; `progress` is a number from `0` to `1`. When failed, include `error` with a user-readable message. The frontend polls every 500 ms until `complete` or `error`, then fetches `GET /api/session` and requires `bundle` to be non-null. Keep the job and session associated with the same user/session. Do not report artificial progress as analysis progress.

## Analysis requests

### Multipart upload

`POST /api/analyze` uses `multipart/form-data` with:

- `file`: the uploaded file; the frontend accepts `.csv`, `.json`, `.xml`, `.txt` and blocks files larger than 50 MiB before sending.
- `options`: a JSON string, for example:

```json
{
  "outlierTreatment": "flag",
  "missingThreshold": 0.6,
  "autoForecast": true
}
```

`outlierTreatment` is `flag`, `cap`, or `remove`; `missingThreshold` is a fraction in the UI range `0.30–0.90`; `autoForecast` is boolean. The server must independently validate extensions, file size, configuration, and parsing errors. Return `202 {"jobId":"..."}` only once work has been accepted.

### Public JSON URL

`POST /api/analyze-url` JSON:

```json
{
  "url": "https://public.example/data.json",
  "options": {
    "outlierTreatment": "flag",
    "missingThreshold": 0.6,
    "autoForecast": true
  }
}
```

The UI only offers HTTP/HTTPS URLs. The server must enforce its own timeout and response-size limits, deny embedded credentials and private/link-local/loopback IPs, and re-check destinations after redirects to prevent SSRF. The original ingestion helper limits URL fetch time/size but does not itself provide a complete private-network/redirect SSRF policy; add that protection in the HTTP adapter if it can receive untrusted URLs.

## Forecast request

`POST /api/forecast` JSON:

```json
{
  "dateColumn": "date",
  "targetColumn": "revenue",
  "aggregation": "sum",
  "horizon": 3,
  "decompositionModel": "additive"
}
```

`aggregation` is `sum` or `mean`; `decompositionModel` is `additive` or `multiplicative`. Validate the horizon using the existing backend's configured limit (the current project defines a maximum of 24). Return the updated bundle as `{ "bundle": ... }`; return a 4xx JSON error if the active session has no bundle or parameters are invalid.

## Analysis bundle JSON consumed by the UI

The shape below normalizes the project's Python dataclasses to browser-safe JSON. Field names are intentionally explicit; preserve nulls for unavailable optional analyses.

```json
{
  "source": {
    "filename": "sales.csv",
    "format": "csv",
    "rowsRaw": 1200,
    "columnsRaw": 8,
    "unstructured": false,
    "warnings": [],
    "rawPreview": {"columns": ["date", "revenue"], "rows": [], "totalRows": 1200, "truncated": true}
  },
  "clean": {
    "preview": {"columns": ["date", "revenue"], "rows": [], "totalRows": 1198, "truncated": true},
    "qualityBefore": {"n_rows": 1200, "n_cols": 8, "missing_cells": 2, "duplicate_rows": 0, "outlier_cells": 0},
    "qualityAfter": {"n_rows": 1198, "n_cols": 8, "missing_cells": 0, "duplicate_rows": 0, "outlier_cells": 0},
    "actions": [{"step": "impute", "column": "revenue", "description": "...", "rowsAffected": 2}],
    "renameMap": {"old name": "old_name"},
    "warnings": []
  },
  "profile": {
    "rows": 1198,
    "columnsCount": 8,
    "primaryDateColumn": "date",
    "memoryMb": 0.5,
    "columns": [{
      "name": "date", "dtype": "datetime64[ns]", "kind": "datetime",
      "missing": 0, "missingPct": 0, "unique": 120, "uniqueRatio": 0.1,
      "sampleValues": ["2025-01-01", "2025-02-01"],
      "numericStats": null, "topValues": null, "dateRange": ["2025-01-01", "2025-10-01"]
    }]
  },
  "transform": {
    "views": {
      "scaled_minmax": {"columns": ["revenue"], "rows": [], "totalRows": 1198, "truncated": true},
      "scaled_standard": {"columns": ["revenue"], "rows": [], "totalRows": 1198, "truncated": true},
      "label_encoded": {"columns": [], "rows": [], "totalRows": 0, "truncated": false},
      "one_hot": {"columns": [], "rows": [], "totalRows": 0, "truncated": false},
      "binned": {"columns": ["revenue_bin"], "rows": [], "totalRows": 1198, "truncated": true},
      "ml_ready": {"columns": ["revenue"], "rows": [], "totalRows": 1198, "truncated": true}
    },
    "warnings": []
  },
  "analysis": {
    "descriptive": {"columns": ["count", "mean", "std", "min", "25%", "50%", "75%", "max"], "rows": [], "totalRows": 1, "truncated": false},
    "correlation": {"columns": ["revenue", "orders"], "rows": [], "totalRows": 2, "truncated": false},
    "topPairs": [{"x": "orders", "y": "revenue", "r": 0.87}],
    "regression": null,
    "textSummary": null,
    "warnings": []
  },
  "charts": [],
  "forecast": null,
  "forecastCharts": [],
  "forecastError": "No date column found, so no forecast was created.",
  "insights": [{"level": "info", "category": "quality", "text": "..."}]
}
```

Additional required details:

- Table preview rows are arrays of objects keyed by column name. Include `columns`, `rows`, `totalRows`, and `truncated`. Keep raw/clean previews near 200 rows and transformation previews small; do not send entire wide or transformed datasets just to populate a preview.
- Column `kind` values should use the backend enum values (`numeric`, `categorical`, `boolean`, `datetime`, `text`, `high_cardinality`, `id_like`, `constant`). `sampleValues` are display-ready strings. `numericStats`, `topValues`, and `dateRange` may be null.
- `transform.views` uses the view keys shown in the sample. Each view is a `TablePreview`; include `ml_ready` when available.
- `charts` and `forecastCharts` entries have `{id,title,kind,group,columns,description,figure}`. `kind` is a backend chart kind (`histogram`, `box`, `bar`, `pie`, `donut`, `scatter`, `heatmap`, `line`, `decomposition`, `forecast`); `group` is `distribution`, `category`, `relationship`, `text`, or `time_series`. `figure` is a Plotly JSON object `{data:[...],layout:{...}}` with ordinary JSON arrays for `x`, `y`, and `z` (no pandas/numpy objects or opaque base64 arrays). Keep plot payloads within the backend's chart-point limit where applicable.
- `forecast.params` uses `{date_col,target_col,agg,horizon,decomposition_model}`. The frontend reads `freq`, `seasonalPeriod`, `order`, `aic`, `adfPvalue`, optional `backtest:{mae,rmse,mape}`, `warnings`, and `forecast:[{date,forecast,lower,upper}]`. `forecastCharts` carry displayable chart specs. `forecast` may be null when unavailable.
- `analysis.descriptive` and `analysis.correlation` use the `TablePreview` shape. `regression`, when available, uses `{x,y,coef,intercept,r2,mae,rmse,n_train,n_test,y_test,y_pred}`. `textSummary` may be a string or null.

## Save/list/preview response shapes

```json
{"name":"Optional display name"}
```

`POST /api/save` returns `{"datasetId":123}`. `GET /api/saved` returns:

```json
{"datasets":[{"id":123,"name":"Sales","filename":"sales.csv","rows":1198,"columns":8,"savedAt":"2026-10-28T12:00:00Z"}]}
```

`GET /api/saved/{id}?limit=100` returns `{"data":{"columns":["date","revenue"],"rows":[],"totalRows":1198,"truncated":true}}`. The `CSV` action downloads the full saved cleaned table, not only the preview.

## Loading and failure states

- The session check shows a connected state only when `GET /api/session` succeeds; a null bundle still means the service/session is reachable.
- Upload buttons disable during job submission/polling. Return an accurate `stage` and `progress`; on error return `status:"error"` plus `error`.
- Forecast and persistence/export buttons show errors from JSON; report and CSV downloads must return the correct binary/text response and `Content-Disposition` filename.
- A 404/409 should be used for missing datasets/session bundles; use 413 for over-size uploads; use 422 for invalid source/configuration; use 500 only for unexpected server errors. Never return a successful-looking empty bundle after analysis failure.
