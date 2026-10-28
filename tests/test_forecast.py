"""tests/test_forecast.py"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.exceptions import ForecastError
from src.forecast import default_params, run_forecast
from src.models import ForecastParams
from src.profile import profile


def test_forecast_monthly_series(monthly_series):
    """36-month seasonal series should produce a valid ForecastResult."""
    result = run_forecast(monthly_series, ForecastParams(
        date_col="date", target_col="sales", agg="sum", horizon=3
    ))
    assert result.freq == "MS"
    assert len(result.forecast) == 3
    assert result.order is not None
    assert result.aic < float("inf")
    assert "forecast" in result.forecast.columns
    assert "lower" in result.forecast.columns
    assert "upper" in result.forecast.columns


def test_forecast_result_has_sma_ema(monthly_series):
    result = run_forecast(monthly_series, ForecastParams(
        date_col="date", target_col="sales", agg="mean", horizon=3
    ))
    assert len(result.sma) == len(result.series)
    assert len(result.ema) == len(result.series)


def test_forecast_decomposition(monthly_series):
    result = run_forecast(monthly_series, ForecastParams(
        date_col="date", target_col="sales", agg="sum", horizon=3
    ))
    # 36 months >= 2 * 12 seasonal period, so decomposition should work
    assert result.decomposition is not None


def test_forecast_too_short_raises():
    df = pd.DataFrame({
        "date": pd.date_range("2021-01-01", periods=5, freq="MS"),
        "sales": [100, 110, 120, 130, 140],
    })
    with pytest.raises(ForecastError):
        run_forecast(df, ForecastParams(date_col="date", target_col="sales"))


def test_default_params_with_date_col(monthly_series):
    p = profile(monthly_series)
    fp = default_params(monthly_series, p)
    assert fp is not None
    assert fp.date_col == "date"
    assert fp.target_col == "sales"


def test_default_params_no_date_col():
    df = pd.DataFrame({"sales": [1, 2, 3, 4, 5]})
    p = profile(df)
    fp = default_params(df, p)
    assert fp is None


def test_forecast_charts_generated(monthly_series):
    from src.visualize import build_forecast_charts
    result = run_forecast(monthly_series, ForecastParams(
        date_col="date", target_col="sales", agg="sum", horizon=3
    ))
    charts = build_forecast_charts(result)
    ids = [c.id for c in charts]
    assert "ts__trend" in ids
    assert "ts__forecast" in ids

