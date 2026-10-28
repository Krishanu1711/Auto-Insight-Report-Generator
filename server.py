"""
server.py — Production-grade FastAPI HTTP Adapter for Auto-Insight Report Generator.
Complies with frontend/API_CONTRACT.md and INTEGRATION_GUIDE.md.
"""
from __future__ import annotations

import asyncio
import io
import ipaddress
import json
import logging
import math
import os
import re
import socket
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import requests
from fastapi import (
    BackgroundTasks,
    Cookie,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import config, database, forecast, ingest, pipeline, report
from src.config import DB_PATH, MAX_UPLOAD_MB, RAW_PREVIEW_ROWS
from src.exceptions import ForecastError, IngestError
from src.models import (
    AnalysisBundle,
    CleaningConfig,
    ForecastParams,
    OutlierTreatment,
    PipelineConfig,
)
from src.utils import get_logger

_log = get_logger("server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Auto-Insight API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = database.get_engine(DB_PATH)
database.init_db(_engine)

_executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------------
# Session & Job State Management (Thread-safe)
# ---------------------------------------------------------------------------
_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}
_jobs: dict[str, dict[str, Any]] = {}

SESSION_COOKIE_NAME = "auto_insight_session"


def _extract_error_message(detail: Any, fallback: str = "Request failed.") -> str:
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, dict):
        for key in ("error", "message", "detail"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
            msg = first.get("msg")
            if loc and msg:
                return f"{loc}: {msg}"
            if isinstance(msg, str) and msg.strip():
                return msg
    return fallback


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    message = _extract_error_message(exc.detail, fallback="Request failed.")
    details = exc.detail if isinstance(exc.detail, (dict, list)) else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message, "details": details},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": _extract_error_message(exc.errors(), fallback="Invalid request."),
            "details": exc.errors(),
        },
    )


def _get_or_create_session_id(request: Request, response: Response) -> str:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        session_id = str(uuid.uuid4())
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = {"bundle": None, "active_job_id": None}
    return session_id


# ---------------------------------------------------------------------------
# JSON Sanitization & Serialization Helpers
# ---------------------------------------------------------------------------
def _sanitize(val: Any) -> Any:
    """Recursively convert numpy/pandas/timestamp types to browser JSON-safe values."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.isoformat()
    if isinstance(val, np.ndarray):
        return [_sanitize(x) for x in val.tolist()]
    if isinstance(val, pd.Series):
        return [_sanitize(x) for x in val.tolist()]
    if isinstance(val, dict):
        return {str(k): _sanitize(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_sanitize(x) for x in val]
    return val


def _df_to_table_preview(df: pd.DataFrame | None, max_rows: int = 200) -> dict[str, Any]:
    if df is None or df.empty:
        return {"columns": list(df.columns) if df is not None else [], "rows": [], "totalRows": 0, "truncated": False}
    total_rows = len(df)
    truncated = total_rows > max_rows
    sub = df.head(max_rows)
    # Convert DataFrame records to python dicts with sanitized values
    records = []
    cols = list(df.columns)
    for row in sub.itertuples(index=False):
        row_dict = {}
        for col_name, cell_val in zip(cols, row):
            row_dict[col_name] = _sanitize(cell_val)
        records.append(row_dict)
    return {
        "columns": cols,
        "rows": records,
        "totalRows": total_rows,
        "truncated": truncated,
    }


def _serialize_figure(fig: Any) -> dict[str, Any]:
    """Serialize Plotly figure to clean dict matching contract."""
    fig_dict = fig.to_dict()
    return _sanitize(fig_dict)


def _serialize_chart_spec(spec: Any) -> dict[str, Any]:
    return {
        "id": spec.id,
        "title": spec.title,
        "kind": spec.kind.value if hasattr(spec.kind, "value") else str(spec.kind),
        "group": spec.group.value if hasattr(spec.group, "value") else str(spec.group),
        "columns": list(spec.columns),
        "description": spec.description,
        "figure": _serialize_figure(spec.figure),
    }


def serialize_bundle(bundle: AnalysisBundle | None) -> dict[str, Any] | None:
    if bundle is None:
        return None

    # Source
    source_json = {
        "filename": bundle.source.filename,
        "format": bundle.source.source_format.value,
        "rowsRaw": bundle.source.n_rows_raw,
        "columnsRaw": bundle.source.n_cols_raw,
        "unstructured": bundle.source.is_unstructured,
        "warnings": list(bundle.source.warnings),
        "rawPreview": _df_to_table_preview(bundle.source.raw_preview, RAW_PREVIEW_ROWS),
    }

    # Clean
    clean_preview = _df_to_table_preview(bundle.clean.df, RAW_PREVIEW_ROWS)
    quality_before = {
        "n_rows": bundle.clean.quality_before.n_rows,
        "n_cols": bundle.clean.quality_before.n_cols,
        "missing_cells": bundle.clean.quality_before.missing_cells,
        "duplicate_rows": bundle.clean.quality_before.duplicate_rows,
        "outlier_cells": bundle.clean.quality_before.outlier_cells,
    }
    quality_after = {
        "n_rows": bundle.clean.quality_after.n_rows,
        "n_cols": bundle.clean.quality_after.n_cols,
        "missing_cells": bundle.clean.quality_after.missing_cells,
        "duplicate_rows": bundle.clean.quality_after.duplicate_rows,
        "outlier_cells": bundle.clean.quality_after.outlier_cells,
    }
    actions = [
        {
            "step": a.step.value if hasattr(a.step, "value") else str(a.step),
            "column": a.column,
            "description": a.description,
            "rowsAffected": a.rows_affected,
        }
        for a in bundle.clean.actions
    ]
    clean_json = {
        "preview": clean_preview,
        "qualityBefore": quality_before,
        "qualityAfter": quality_after,
        "actions": actions,
        "renameMap": bundle.clean.rename_map or {},
        "warnings": list(bundle.clean.warnings),
    }

    # Profile
    cols_profile = []
    for c in bundle.profile.columns:
        cols_profile.append({
            "name": c.name,
            "dtype": str(c.dtype),
            "kind": c.kind.value if hasattr(c.kind, "value") else str(c.kind),
            "missing": c.n_missing,
            "missingPct": round(c.pct_missing, 4),
            "unique": c.n_unique,
            "uniqueRatio": round(c.unique_ratio, 4),
            "sampleValues": [str(x) for x in c.sample_values],
            "numericStats": _sanitize(c.numeric_stats) if c.numeric_stats else None,
            "topValues": [{"value": str(k), "count": int(v)} for k, v in c.top_values] if c.top_values else None,
            "dateRange": list(c.date_range) if c.date_range else None,
        })
    profile_json = {
        "rows": bundle.profile.n_rows,
        "columnsCount": bundle.profile.n_cols,
        "primaryDateColumn": bundle.profile.primary_date_col,
        "memoryMb": round(bundle.profile.memory_mb, 2),
        "columns": cols_profile,
    }

    # Transform
    transform_json = None
    if bundle.transform is not None:
        t = bundle.transform
        transform_json = {
            "views": {
                "scaled_minmax": _df_to_table_preview(t.scaled_minmax, 50),
                "scaled_standard": _df_to_table_preview(t.scaled_standard, 50),
                "label_encoded": _df_to_table_preview(t.label_encoded, 50),
                "one_hot": _df_to_table_preview(t.one_hot, 50),
                "binned": _df_to_table_preview(t.binned, 50),
                "ml_ready": _df_to_table_preview(t.ml_ready, 50),
            },
            "warnings": list(t.warnings),
        }

    # Analysis
    analysis_json = {
        "descriptive": _df_to_table_preview(bundle.analysis.descriptive) if bundle.analysis.descriptive is not None else None,
        "correlation": _df_to_table_preview(bundle.analysis.correlation) if bundle.analysis.correlation is not None else None,
        "topPairs": [{"x": p.x, "y": p.y, "r": round(float(p.r), 4)} for p in bundle.analysis.top_pairs],
        "regression": (
            {
                "x": bundle.analysis.regression.x,
                "y": bundle.analysis.regression.y,
                "coef": round(float(bundle.analysis.regression.coef), 4),
                "intercept": round(float(bundle.analysis.regression.intercept), 4),
                "r2": round(float(bundle.analysis.regression.r2), 4),
                "mae": round(float(bundle.analysis.regression.mae), 4),
                "rmse": round(float(bundle.analysis.regression.rmse), 4),
                "n_train": bundle.analysis.regression.n_train,
                "n_test": bundle.analysis.regression.n_test,
                "y_test": _sanitize(bundle.analysis.regression.y_test),
                "y_pred": _sanitize(bundle.analysis.regression.y_pred),
            }
            if bundle.analysis.regression
            else None
        ),
        "textSummary": (
            f"{bundle.analysis.text_summary.n_lines} lines, {bundle.analysis.text_summary.n_words} words "
            f"(avg {bundle.analysis.text_summary.avg_words_per_line:.1f} words/line)"
            if bundle.analysis.text_summary
            else None
        ),
        "warnings": list(bundle.analysis.warnings),
    }

    # Charts
    charts_json = [_serialize_chart_spec(spec) for spec in bundle.charts]
    fc_charts_json = [_serialize_chart_spec(spec) for spec in bundle.forecast_charts]

    # Forecast
    forecast_json = None
    if bundle.forecast is not None:
        fc = bundle.forecast
        forecast_table = []
        for dt_idx, row in fc.forecast.iterrows():
            d_str = str(dt_idx)[:10]
            forecast_table.append({
                "date": d_str,
                "forecast": round(float(row["forecast"]), 2),
                "lower": round(float(row["lower"]), 2) if "lower" in row and not math.isnan(row["lower"]) else None,
                "upper": round(float(row["upper"]), 2) if "upper" in row and not math.isnan(row["upper"]) else None,
            })

        hist_records = []
        for dt_idx, val in fc.series.items():
            d_str = str(dt_idx)[:10]
            sma_val = fc.sma.get(dt_idx, None)
            ema_val = fc.ema.get(dt_idx, None)
            hist_records.append({
                "date": d_str,
                "value": round(float(val), 2),
                "sma": round(float(sma_val), 2) if sma_val is not None and not math.isnan(sma_val) else None,
                "ema": round(float(ema_val), 2) if ema_val is not None and not math.isnan(ema_val) else None,
            })

        decomp_json = None
        if fc.decomposition:
            d = fc.decomposition
            decomp_json = {
                "model": d.model,
                "period": d.period,
                "observed": [{"date": str(dt)[:10], "value": round(float(v), 2)} for dt, v in d.observed.items()],
                "trend": [{"date": str(dt)[:10], "value": round(float(v), 2) if not math.isnan(v) else None} for dt, v in d.trend.items()],
                "seasonal": [{"date": str(dt)[:10], "value": round(float(v), 2) if not math.isnan(v) else None} for dt, v in d.seasonal.items()],
                "resid": [{"date": str(dt)[:10], "value": round(float(v), 2) if not math.isnan(v) else None} for dt, v in d.resid.items()],
            }

        backtest_json = None
        if fc.backtest:
            bt = fc.backtest
            backtest_json = {
                "actual": [{"date": str(dt)[:10], "value": round(float(v), 2)} for dt, v in bt.actual.items()],
                "predicted": [{"date": str(dt)[:10], "value": round(float(v), 2)} for dt, v in bt.predicted.items()],
                "mae": round(float(bt.mae), 2),
                "rmse": round(float(bt.rmse), 2),
                "mape": round(float(bt.mape), 2) if bt.mape is not None else None,
            }

        forecast_json = {
            "params": {
                "date_col": fc.params.date_col,
                "target_col": fc.params.target_col,
                "agg": fc.params.agg,
                "horizon": fc.params.horizon,
                "decomposition_model": fc.params.decomposition_model,
            },
            "freq": fc.freq,
            "seasonalPeriod": fc.seasonal_period,
            "series": hist_records,
            "smaWindow": fc.sma_window,
            "emaSpan": fc.ema_span,
            "decomposition": decomp_json,
            "adfPvalue": round(float(fc.adf_pvalue), 4),
            "order": list(fc.order),
            "aic": round(float(fc.aic), 2),
            "backtest": backtest_json,
            "forecast": forecast_table,
            "warnings": list(fc.warnings),
        }

    # Insights
    insights_json = [
        {"level": ins.level, "category": ins.category, "text": ins.text}
        for ins in bundle.insights
    ]

    return {
        "source": source_json,
        "clean": clean_json,
        "profile": profile_json,
        "transform": transform_json,
        "analysis": analysis_json,
        "charts": charts_json,
        "forecast": forecast_json,
        "forecastCharts": fc_charts_json,
        "forecastError": bundle.forecast_error,
        "insights": insights_json,
    }


# ---------------------------------------------------------------------------
# SSRF-Protected URL Fetching
# ---------------------------------------------------------------------------
def _validate_safe_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise IngestError("Only HTTP and HTTPS URLs are permitted.")
    if parsed.username or parsed.password:
        raise IngestError("Credentials in URLs are forbidden.")

    hostname = parsed.hostname
    if not hostname:
        raise IngestError("Invalid URL hostname.")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except Exception as exc:
        raise IngestError(f"Could not resolve hostname '{hostname}': {exc}")

    for info in addr_infos:
        ip_str = info[4][0]
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise IngestError(f"Access to private/loopback destination ({ip_str}) is blocked.")


# ---------------------------------------------------------------------------
# API Routes (per API_CONTRACT.md)
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def health_check():
    return {"status": "ok"}

@app.get("/api/session")
async def get_session(request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    with _lock:
        session_data = _sessions.get(session_id, {})
        bundle = session_data.get("bundle")
    return {"bundle": serialize_bundle(bundle)}


@app.post("/api/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_file(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    options: Optional[str] = Form(None),
):
    session_id = _get_or_create_session_id(request, response)
    filename = file.filename or "uploaded_data"
    content = await file.read()

    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {MAX_UPLOAD_MB} MB.",
        )

    # Parse options
    outlier_treatment = OutlierTreatment.FLAG
    missing_thresh = 0.60
    auto_forecast = True
    if options:
        try:
            opt_dict = json.loads(options)
            treatment_str = opt_dict.get("outlierTreatment", "flag").lower()
            if treatment_str == "cap":
                outlier_treatment = OutlierTreatment.CAP
            elif treatment_str == "remove":
                outlier_treatment = OutlierTreatment.REMOVE
            missing_thresh = float(opt_dict.get("missingThreshold", 0.60))
            auto_forecast = bool(opt_dict.get("autoForecast", True))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid options payload: {exc}")

    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "jobId": job_id,
            "sessionId": session_id,
            "status": "queued",
            "stage": "Reading file",
            "progress": 0.0,
            "error": None,
        }

    def _worker():
        try:
            with _lock:
                _jobs[job_id]["status"] = "running"

            def progress_cb(stage_label: str, frac: float):
                with _lock:
                    _jobs[job_id]["stage"] = stage_label
                    _jobs[job_id]["progress"] = round(frac, 2)

            cleaning_cfg = CleaningConfig(
                outlier_treatment=outlier_treatment,
                drop_column_missing_pct=missing_thresh,
            )
            pipe_cfg = PipelineConfig(cleaning=cleaning_cfg, auto_forecast=auto_forecast)

            bundle = pipeline.run_pipeline(filename, content, pipe_cfg, progress=progress_cb)

            with _lock:
                _sessions[session_id]["bundle"] = bundle
                _jobs[job_id]["status"] = "complete"
                _jobs[job_id]["progress"] = 1.0
                _jobs[job_id]["stage"] = "Done"
        except Exception as exc:
            _log.exception("Analysis worker failed")
            with _lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(exc)

    _executor.submit(_worker)
    return {"jobId": job_id}


class AnalyzeUrlRequest(BaseModel):
    url: str
    options: Optional[dict[str, Any]] = None


@app.post("/api/analyze-url", status_code=status.HTTP_202_ACCEPTED)
async def analyze_url(payload: AnalyzeUrlRequest, request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    url = payload.url.strip()

    try:
        _validate_safe_url(url)
    except IngestError as err:
        raise HTTPException(status_code=422, detail=str(err))

    # Parse options
    outlier_treatment = OutlierTreatment.FLAG
    missing_thresh = 0.60
    auto_forecast = True
    if payload.options:
        treatment_str = payload.options.get("outlierTreatment", "flag").lower()
        if treatment_str == "cap":
            outlier_treatment = OutlierTreatment.CAP
        elif treatment_str == "remove":
            outlier_treatment = OutlierTreatment.REMOVE
        missing_thresh = float(payload.options.get("missingThreshold", 0.60))
        auto_forecast = bool(payload.options.get("autoForecast", True))

    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            "jobId": job_id,
            "sessionId": session_id,
            "status": "queued",
            "stage": "Fetching URL",
            "progress": 0.0,
            "error": None,
        }

    def _worker():
        try:
            with _lock:
                _jobs[job_id]["status"] = "running"

            def progress_cb(stage_label: str, frac: float):
                with _lock:
                    _jobs[job_id]["stage"] = stage_label
                    _jobs[job_id]["progress"] = round(frac, 2)

            ingest_res = ingest.load_from_url(url)
            # Convert parsed dataframe back to JSON bytes to pass through standard pipeline
            json_bytes = ingest_res.df.to_json(orient="records").encode("utf-8")

            filename = Path(urllib.parse.urlparse(url).path).name or "api_data.json"
            if not filename.endswith(".json"):
                filename += ".json"

            cleaning_cfg = CleaningConfig(
                outlier_treatment=outlier_treatment,
                drop_column_missing_pct=missing_thresh,
            )
            pipe_cfg = PipelineConfig(cleaning=cleaning_cfg, auto_forecast=auto_forecast)

            bundle = pipeline.run_pipeline(filename, json_bytes, pipe_cfg, progress=progress_cb)

            with _lock:
                _sessions[session_id]["bundle"] = bundle
                _jobs[job_id]["status"] = "complete"
                _jobs[job_id]["progress"] = 1.0
                _jobs[job_id]["stage"] = "Done"
        except Exception as exc:
            _log.exception("URL analysis failed")
            with _lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(exc)

    _executor.submit(_worker)
    return {"jobId": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    res = {
        "jobId": job["jobId"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
    }
    if job.get("error"):
        res["error"] = job["error"]
    return res


class ForecastRequest(BaseModel):
    dateColumn: str
    targetColumn: str
    aggregation: str = "sum"
    horizon: int = 3
    decompositionModel: str = "additive"


@app.post("/api/forecast")
async def rerun_forecast_route(payload: ForecastRequest, request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    with _lock:
        bundle = _sessions.get(session_id, {}).get("bundle")

    if not bundle:
        raise HTTPException(status_code=409, detail="No active analysis session found. Upload a dataset first.")

    try:
        horizon = max(1, min(payload.horizon, config.MAX_HORIZON))
        params = ForecastParams(
            date_col=payload.dateColumn,
            target_col=payload.targetColumn,
            agg=payload.aggregation,
            horizon=horizon,
            decomposition_model=payload.decompositionModel,
        )
        updated_bundle = pipeline.rerun_forecast(bundle, params)
        with _lock:
            _sessions[session_id]["bundle"] = updated_bundle
        return {"bundle": serialize_bundle(updated_bundle)}
    except Exception as exc:
        _log.exception("Forecast rerun failed")
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/report")
async def generate_report_post(request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    with _lock:
        bundle = _sessions.get(session_id, {}).get("bundle")

    if not bundle:
        raise HTTPException(status_code=409, detail="No active dataset available to generate report.")

    try:
        html_bytes = report.build_report(bundle)
        return Response(
            content=html_bytes,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="insight_report.html"'},
        )
    except Exception as exc:
        _log.exception("Report generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/download/clean.csv")
async def download_clean_csv(request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    with _lock:
        bundle = _sessions.get(session_id, {}).get("bundle")

    if not bundle:
        raise HTTPException(status_code=409, detail="No active dataset available.")

    csv_data = bundle.clean.df.to_csv(index=False)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cleaned_data.csv"'},
    )


@app.get("/api/download/ml-ready.csv")
async def download_ml_ready_csv(request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    with _lock:
        bundle = _sessions.get(session_id, {}).get("bundle")

    if not bundle:
        raise HTTPException(status_code=409, detail="No active dataset available.")
    if not bundle.transform or bundle.transform.ml_ready is None or bundle.transform.ml_ready.empty:
        raise HTTPException(status_code=409, detail="No ML-ready transform available for this dataset.")

    csv_data = bundle.transform.ml_ready.to_csv(index=False)
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ml_ready_data.csv"'},
    )


class SaveRequest(BaseModel):
    name: Optional[str] = None


@app.post("/api/save", status_code=status.HTTP_201_CREATED)
async def save_active_dataset(payload: SaveRequest, request: Request, response: Response):
    session_id = _get_or_create_session_id(request, response)
    with _lock:
        bundle = _sessions.get(session_id, {}).get("bundle")

    if not bundle:
        raise HTTPException(status_code=409, detail="No active analysis dataset to save.")

    name = payload.name or bundle.source.filename or "Untitled Dataset"
    try:
        ds_id = database.save_bundle(bundle, name, _engine)
        return {"datasetId": ds_id}
    except Exception as exc:
        _log.exception("Save dataset failed")
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/saved")
async def list_saved_datasets():
    try:
        records = database.list_datasets(_engine)
        return {
            "datasets": [
                {
                    "id": r.id,
                    "name": r.name,
                    "filename": r.original_filename,
                    "rows": r.n_rows_clean,
                    "columns": r.n_cols_clean,
                    "savedAt": r.created_at.isoformat(),
                }
                for r in records
            ]
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/saved/{dataset_id}")
async def get_saved_dataset_preview(dataset_id: int, limit: int = 100):
    try:
        df = database.load_clean_table(dataset_id, limit=limit, engine=_engine)
        return {"data": _df_to_table_preview(df, limit)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Saved dataset #{dataset_id} not found: {exc}")


@app.get("/api/saved/{dataset_id}/csv")
async def download_saved_dataset_csv(dataset_id: int):
    try:
        df = database.load_clean_table(dataset_id, limit=None, engine=_engine)
        csv_data = df.to_csv(index=False)
        return Response(
            content=csv_data,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="dataset_{dataset_id}.csv"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Could not load table for dataset #{dataset_id}: {exc}")


@app.delete("/api/saved/{dataset_id}", status_code=status.HTTP_200_OK)
async def delete_saved_dataset(dataset_id: int):
    try:
        database.delete_dataset(dataset_id, _engine)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Static Web Assets (Frontend Dist)
# ---------------------------------------------------------------------------
_dist_dir = Path(__file__).parent / "frontend" / "dist"
if _dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(_dist_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
