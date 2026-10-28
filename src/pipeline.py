"""
src/pipeline.py — Orchestrator: run_pipeline and rerun_forecast.

Public API
----------
run_pipeline(filename, content, config, progress)   -> AnalysisBundle
rerun_forecast(bundle, params)                      -> AnalysisBundle
"""
from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable
from datetime import datetime, timezone

import pandas as pd

from src import analyze, clean, forecast, ingest, insights, profile, transform, visualize
from src.config import RAW_PREVIEW_ROWS
from src.exceptions import ForecastError
from src.models import (
    AnalysisBundle,
    AnalysisResult,
    ForecastParams,
    PipelineConfig,
    SourceInfo,
)
from src.utils import get_logger

_log = get_logger(__name__)

ProgressFn = Callable[[str, float], None]


# ---------------------------------------------------------------------------
# run_pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    filename: str,
    content: bytes,
    config: PipelineConfig,
    progress: ProgressFn | None = None,
) -> AnalysisBundle:
    """Run all pipeline stages and return an :class:`AnalysisBundle`.

    *progress* is an optional callback ``(stage_label, fraction)`` → None,
    called at the start of each stage.
    """

    def _progress(label: str, frac: float) -> None:
        _log.info("[%.0f%%] %s", frac * 100, label)
        if progress:
            progress(label, frac)

    t0 = time.perf_counter()

    # ── Stage 1: Ingest ──────────────────────────────────────────────────
    _progress("Reading file", 0.10)
    ingest_result = ingest.load(filename, content)

    source = SourceInfo(
        filename=filename,
        source_format=ingest_result.source_format,
        file_sha256=ingest_result.file_sha256,
        n_rows_raw=len(ingest_result.df),
        n_cols_raw=ingest_result.df.shape[1],
        is_unstructured=ingest_result.is_unstructured,
        raw_preview=ingest_result.df.head(RAW_PREVIEW_ROWS).copy(),
        warnings=ingest_result.warnings,
    )

    # ── Stage 2: Clean ───────────────────────────────────────────────────
    _progress("Cleaning", 0.30)
    clean_result = clean.clean(
        ingest_result.df,
        config.cleaning,
        is_unstructured=ingest_result.is_unstructured,
    )

    # ── Stage 3: Profile ─────────────────────────────────────────────────
    _progress("Profiling", 0.45)
    dataset_profile = profile.profile(clean_result.df)

    # ────────────────────────────────────────────────────────────────────
    # Unstructured path
    # ────────────────────────────────────────────────────────────────────
    if ingest_result.is_unstructured:
        _progress("Analyzing text", 0.70)
        text_summary = analyze.summarize_text(clean_result.df)

        analysis_result = AnalysisResult(
            descriptive=None,
            correlation=None,
            top_pairs=[],
            regression=None,
            text_summary=text_summary,
        )

        _progress("Building charts", 0.85)
        charts = visualize.build_text_charts(text_summary)

        _progress("Generating insights", 0.95)
        insight_list = insights.generate_insights(
            clean_result, dataset_profile, analysis_result, None
        )

        _progress("Done", 1.00)
        _log.info("Pipeline (unstructured) done in %.2f s.", time.perf_counter() - t0)

        return AnalysisBundle(
            source=source,
            clean=clean_result,
            profile=dataset_profile,
            transform=None,
            analysis=analysis_result,
            charts=charts,
            forecast=None,
            forecast_charts=[],
            forecast_error="Forecasting is not available for free text.",
            insights=insight_list,
            config=config,
            created_at=datetime.now(timezone.utc),
        )

    # ────────────────────────────────────────────────────────────────────
    # Tabular path
    # ────────────────────────────────────────────────────────────────────

    # ── Stage 4: Transform ───────────────────────────────────────────────
    _progress("Transforming", 0.60)
    transform_result = transform.transform(clean_result.df, dataset_profile)

    # ── Stage 5: Analyze ─────────────────────────────────────────────────
    _progress("Analyzing", 0.70)
    analysis_result = analyze.analyze(clean_result.df, dataset_profile)

    # ── Stage 6: Visualize ───────────────────────────────────────────────
    _progress("Building charts", 0.85)
    charts = visualize.build_charts(
        clean_result.df, dataset_profile, analysis_result, transform_result
    )

    # ── Stage 7: Forecast (optional) ─────────────────────────────────────
    _progress("Forecasting", 0.95)
    forecast_result = None
    forecast_charts: list = []
    forecast_error: str | None = None

    if config.auto_forecast:
        default_fp = forecast.default_params(clean_result.df, dataset_profile)
        if default_fp is not None:
            try:
                forecast_result = forecast.run_forecast(clean_result.df, default_fp)
                forecast_charts = visualize.build_forecast_charts(forecast_result)
            except ForecastError as exc:
                forecast_error = exc.user_message
                _log.warning("Auto-forecast failed: %s", exc.user_message)
        else:
            forecast_error = "No date column found, so no forecast was created."
    else:
        forecast_error = "Auto-forecast is disabled."

    # ── Stage 8: Insights ────────────────────────────────────────────────
    insight_list = insights.generate_insights(
        clean_result, dataset_profile, analysis_result, forecast_result
    )

    _progress("Done", 1.00)
    _log.info("Pipeline (tabular) done in %.2f s.", time.perf_counter() - t0)

    return AnalysisBundle(
        source=source,
        clean=clean_result,
        profile=dataset_profile,
        transform=transform_result,
        analysis=analysis_result,
        charts=charts,
        forecast=forecast_result,
        forecast_charts=forecast_charts,
        forecast_error=forecast_error,
        insights=insight_list,
        config=config,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# rerun_forecast
# ---------------------------------------------------------------------------

def rerun_forecast(bundle: AnalysisBundle, params: ForecastParams) -> AnalysisBundle:
    """Re-run the forecast with new *params* and return a **new** bundle.

    Raises :class:`ForecastError` if the new forecast fails; the caller is
    expected to catch it and display the message.
    """
    _log.info(
        "Re-running forecast: date='%s', target='%s'",
        params.date_col, params.target_col,
    )

    new_forecast = forecast.run_forecast(bundle.clean.df, params)
    new_forecast_charts = visualize.build_forecast_charts(new_forecast)

    new_insights = insights.generate_insights(
        bundle.clean,
        bundle.profile,
        bundle.analysis,
        new_forecast,
    )

    new_bundle = dataclasses.replace(
        bundle,
        forecast=new_forecast,
        forecast_charts=new_forecast_charts,
        forecast_error=None,
        insights=new_insights,
        created_at=datetime.now(timezone.utc),
    )
    return new_bundle

