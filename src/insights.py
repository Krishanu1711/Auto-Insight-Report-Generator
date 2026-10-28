"""
src/insights.py — Rule-based plain-language insights.

Public API
----------
generate_insights(clean, profile, analysis, forecast) -> list[Insight]
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import (
    AnalysisResult,
    CleanResult,
    CleaningStep,
    ColumnKind,
    DatasetProfile,
    ForecastResult,
    Insight,
)
from src.utils import get_logger

_log = get_logger(__name__)


def generate_insights(
    clean: CleanResult,
    profile: DatasetProfile,
    analysis: AnalysisResult,
    forecast: ForecastResult | None,
) -> list[Insight]:
    """Apply fixed insight rules and return a list of :class:`Insight` objects."""
    _log.info("Generating insights.")
    insights: list[Insight] = []

    _r1_imputation(clean, insights)
    _r2_duplicates(clean, insights)
    _r3_outliers(clean, insights, profile)
    _r4_skewness(analysis, insights)
    _r5_correlations(analysis, insights)
    _r6_dominant_category(profile, insights)
    _r7_regression(analysis, insights)
    _r8_forecast(forecast, insights)
    _r9_excluded_columns(profile, insights)

    _log.info("Generated %d insight(s).", len(insights))
    return insights


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def _r1_imputation(clean: CleanResult, insights: list[Insight]) -> None:
    """R1: Top 3 imputation actions by rows affected."""
    impute_actions = [
        a for a in clean.actions
        if a.step == CleaningStep.IMPUTE and a.rows_affected > 0
    ]
    impute_actions.sort(key=lambda a: a.rows_affected, reverse=True)
    for action in impute_actions[:3]:
        fill_type = "median" if "median" in action.description else "Unknown"
        insights.append(Insight(
            level="info",
            category="quality",
            text=action.description,
        ))


def _r2_duplicates(clean: CleanResult, insights: list[Insight]) -> None:
    """R2: Duplicate rows removed."""
    for action in clean.actions:
        if action.step == CleaningStep.DROP_DUPLICATES and action.rows_affected > 0:
            insights.append(Insight(
                level="info",
                category="quality",
                text=action.description,
            ))


def _r3_outliers(
    clean: CleanResult,
    insights: list[Insight],
    profile: DatasetProfile,
) -> None:
    """R3: Columns where IQR outliers exceed 5% of rows."""
    n_rows = profile.n_rows
    if n_rows == 0:
        return
    for action in clean.actions:
        if action.step == CleaningStep.OUTLIERS and action.rows_affected > 0:
            pct = action.rows_affected / n_rows
            if pct > 0.05:
                insights.append(Insight(
                    level="warning",
                    category="quality",
                    text=(
                        f"'{action.column}' has {action.rows_affected:,} outlier(s) "
                        f"({pct:.1%} of rows). Consider reviewing these values."
                    ),
                ))


def _r4_skewness(analysis: AnalysisResult, insights: list[Insight]) -> None:
    """R4: Highly skewed numeric columns."""
    if analysis.descriptive is None:
        return
    for col, row in analysis.descriptive.iterrows():
        skew = row.get("skew", 0)
        if pd.isna(skew):
            continue
        if abs(skew) > 1:
            direction = "right" if skew > 0 else "left"
            insights.append(Insight(
                level="info",
                category="distribution",
                text=(
                    f"'{col}' is highly {direction}-skewed (skew = {skew:.2f}). "
                    "Consider a log transform if using it in a model."
                ),
            ))


def _r5_correlations(analysis: AnalysisResult, insights: list[Insight]) -> None:
    """R5: Strong correlations (|r| >= 0.7)."""
    for pair in analysis.top_pairs[:3]:
        if abs(pair.r) >= 0.7:
            direction = "positive" if pair.r > 0 else "negative"
            insights.append(Insight(
                level="info",
                category="relationship",
                text=(
                    f"'{pair.x}' and '{pair.y}' have a strong {direction} relationship "
                    f"(r = {pair.r:.2f})."
                ),
            ))


def _r6_dominant_category(profile: DatasetProfile, insights: list[Insight]) -> None:
    """R6: Categorical column where top value occupies >= 50% of rows."""
    for cp in profile.columns:
        if cp.kind != ColumnKind.CATEGORICAL or not cp.top_values:
            continue
        top_label, top_count = cp.top_values[0]
        if profile.n_rows == 0:
            continue
        share = top_count / profile.n_rows
        if share >= 0.50:
            insights.append(Insight(
                level="info",
                category="distribution",
                text=(
                    f"'{top_label}' is the dominant value in '{cp.name}' "
                    f"({share:.1%} of rows)."
                ),
            ))


def _r7_regression(analysis: AnalysisResult, insights: list[Insight]) -> None:
    """R7: Report regression R² quality."""
    if analysis.regression is None:
        return
    reg = analysis.regression
    level = "info" if reg.r2 >= 0.1 else "warning"
    quality = "good" if reg.r2 >= 0.5 else ("moderate" if reg.r2 >= 0.1 else "weak")
    insights.append(Insight(
        level=level,
        category="regression",
        text=(
            f"Linear regression of '{reg.y}' on '{reg.x}': "
            f"R² = {reg.r2:.3f} ({quality} linear relationship). "
            f"MAE = {reg.mae:.4g}, RMSE = {reg.rmse:.4g} "
            f"(test set: {reg.n_test} rows)."
        ),
    ))


def _r8_forecast(
    forecast: ForecastResult | None,
    insights: list[Insight],
) -> None:
    """R8: Trend direction, seasonality, forecast direction, backtest quality."""
    if forecast is None:
        return

    series = forecast.series
    if len(series) < 2:
        return

    # Trend via OLS slope
    x = np.arange(len(series), dtype=float)
    y = series.values.astype(float)
    if np.std(y) == 0 or len(x) < 2:
        trend_text = "flat"
    else:
        coef = np.polyfit(x, y, 1)
        slope = coef[0]
        total_change = slope * len(x)
        mean_val = np.mean(y)
        if mean_val != 0 and abs(total_change / mean_val) < 0.05:
            trend_text = "flat"
        elif slope > 0:
            trend_text = "upward"
        else:
            trend_text = "downward"

    target = forecast.params.target_col
    insights.append(Insight(
        level="info",
        category="timeseries",
        text=f"'{target}' shows a {trend_text} trend over the historical period.",
    ))

    # Seasonal period from decomposition
    if forecast.decomposition is not None:
        insights.append(Insight(
            level="info",
            category="timeseries",
            text=(
                f"Seasonal decomposition found a period of {forecast.seasonal_period} "
                f"({forecast.freq}) for '{target}'."
            ),
        ))

    # Forecast direction
    last_actual = float(series.iloc[-1])
    last_forecast = float(forecast.forecast["forecast"].iloc[-1])
    fc_dir = "upward" if last_forecast > last_actual else ("flat" if last_forecast == last_actual else "downward")
    insights.append(Insight(
        level="info",
        category="timeseries",
        text=(
            f"The {forecast.params.horizon}-step forecast for '{target}' "
            f"points {fc_dir} (from {last_actual:.4g} to {last_forecast:.4g})."
        ),
    ))

    # Backtest MAPE quality
    if forecast.backtest is not None and forecast.backtest.mape is not None:
        mape = forecast.backtest.mape
        if mape < 10:
            quality = "good"
        elif mape <= 25:
            quality = "fair"
        else:
            quality = "poor"
        insights.append(Insight(
            level="info",
            category="timeseries",
            text=(
                f"Backtest MAPE = {mape:.1f}% ({quality} forecast accuracy). "
                f"MAE = {forecast.backtest.mae:.4g}, RMSE = {forecast.backtest.rmse:.4g}."
            ),
        ))


def _r9_excluded_columns(profile: DatasetProfile, insights: list[Insight]) -> None:
    """R9: ID-like and constant columns excluded from analysis."""
    excluded = [
        c.name
        for c in profile.columns
        if c.kind in (ColumnKind.ID_LIKE, ColumnKind.CONSTANT)
    ]
    if excluded:
        insights.append(Insight(
            level="info",
            category="quality",
            text=(
                f"{len(excluded)} column(s) classified as ID-like or constant were "
                f"excluded from charts and scaling: {', '.join(excluded)}."
            ),
        ))

