"""
src/forecast.py — Time-series resampling, moving averages, decomposition and ARIMA.

Public API
----------
default_params(df, profile) -> ForecastParams | None
run_forecast(df, params)    -> ForecastResult          (raises ForecastError)
"""
from __future__ import annotations

import re
import warnings as _warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller

from src.config import (
    ADF_ALPHA,
    ARIMA_MAX_D,
    ARIMA_MAX_P,
    ARIMA_MAX_Q,
    DEFAULT_HORIZON,
    FORECAST_CONF_LEVEL,
    FORECAST_MIN_POINTS,
    FREQ_SETTINGS,
)
from src.exceptions import ForecastError
from src.models import (
    BacktestResult,
    ColumnKind,
    DatasetProfile,
    DecompositionResult,
    ForecastParams,
    ForecastResult,
)
from src.utils import get_logger

_log = get_logger(__name__)

_SALES_RE = re.compile(
    r"(sales|revenue|profit|quantity|qty|amount|count|total|cost|orders)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Default parameters
# ---------------------------------------------------------------------------

def default_params(df: pd.DataFrame, profile: DatasetProfile) -> ForecastParams | None:
    """Return sensible default ForecastParams, or None if forecasting is not possible.

    Returns None when there is no primary date column or no numeric column.
    """
    if profile.primary_date_col is None:
        return None

    numeric_cols = profile.cols_of(ColumnKind.NUMERIC)
    if not numeric_cols:
        return None

    target_col = numeric_cols[0]
    agg = "sum" if _SALES_RE.search(target_col) else "mean"

    return ForecastParams(
        date_col=profile.primary_date_col,
        target_col=target_col,
        agg=agg,
        horizon=DEFAULT_HORIZON,
        decomposition_model="additive",
    )


# ---------------------------------------------------------------------------
# Main forecast runner
# ---------------------------------------------------------------------------

def run_forecast(df: pd.DataFrame, params: ForecastParams) -> ForecastResult:
    """Run the full time-series analysis pipeline and return a :class:`ForecastResult`.

    Raises :class:`ForecastError` if the data cannot be forecast.
    """
    _log.info(
        "Starting forecast: date='%s', target='%s', agg='%s', horizon=%d",
        params.date_col, params.target_col, params.agg, params.horizon,
    )
    warn: list[str] = []

    # --- Step 1: Prepare the series ---
    if params.date_col not in df.columns:
        raise ForecastError(f"Date column '{params.date_col}' not found in data.")
    if params.target_col not in df.columns:
        raise ForecastError(f"Target column '{params.target_col}' not found in data.")

    work = df[[params.date_col, params.target_col]].copy()
    work = work.dropna(subset=[params.date_col, params.target_col])
    work[params.date_col] = pd.to_datetime(work[params.date_col], errors="coerce")
    work = work.dropna(subset=[params.date_col])
    work = work.sort_values(params.date_col)

    n_distinct_dates = work[params.date_col].nunique()
    if n_distinct_dates < 2:
        raise ForecastError("Fewer than 2 distinct dates in the data. Cannot forecast.")

    # --- Step 2: Determine frequency ---
    unique_dates = work[params.date_col].drop_duplicates().sort_values()
    gaps = unique_dates.diff().dropna().dt.days
    median_gap = float(gaps.median()) if len(gaps) > 0 else 1.0

    if median_gap <= 1.5:
        freq = "D"
    elif median_gap <= 10:
        freq = "W"
    else:
        freq = "MS"

    _log.info("Detected frequency: %s (median gap %.1f days)", freq, median_gap)

    # --- Step 3: Resample ---
    work = work.set_index(params.date_col)
    series_raw = work[params.target_col].astype(float)

    full_idx = pd.date_range(series_raw.index.min(), series_raw.index.max(), freq=freq)
    if params.agg == "sum":
        series_resampled = series_raw.resample(freq).sum()
    else:
        series_resampled = series_raw.resample(freq).mean()

    series_resampled = series_resampled.reindex(full_idx)
    n_filled = int(series_resampled.isna().sum())
    if len(full_idx) > 0 and n_filled / len(full_idx) > 0.10:
        warn.append(
            f"{n_filled}/{len(full_idx)} periods had no data and were filled by interpolation."
        )

    series_resampled = series_resampled.interpolate(method="time").ffill().bfill()

    # --- Step 4: Check minimum length ---
    if len(series_resampled) < FORECAST_MIN_POINTS:
        raise ForecastError(
            f"Series has only {len(series_resampled)} points after resampling "
            f"(minimum {FORECAST_MIN_POINTS} required)."
        )

    # --- Step 5: Frequency settings ---
    settings = FREQ_SETTINGS[freq]
    seasonal_period: int = settings["period"]
    sma_window: int = settings["sma_window"]
    ema_span: int = settings["ema_span"]

    # --- Step 6: SMA / EMA ---
    sma = series_resampled.rolling(window=sma_window, min_periods=1).mean()
    ema = series_resampled.ewm(span=ema_span, adjust=False).mean()

    # --- Step 7: Decomposition ---
    decomposition: DecompositionResult | None = None
    if len(series_resampled) >= 2 * seasonal_period:
        model_type = params.decomposition_model
        if model_type == "multiplicative" and (series_resampled <= 0).any():
            warn.append(
                "Series contains non-positive values; "
                "falling back from multiplicative to additive decomposition."
            )
            model_type = "additive"
        try:
            result = seasonal_decompose(
                series_resampled,
                model=model_type,
                period=seasonal_period,
                extrapolate_trend="period",
            )
            decomposition = DecompositionResult(
                model=model_type,
                observed=result.observed,
                trend=result.trend,
                seasonal=result.seasonal,
                resid=result.resid,
                period=seasonal_period,
            )
        except Exception as exc:
            warn.append(f"Decomposition failed: {exc}")
    else:
        warn.append(
            f"Series too short for decomposition "
            f"({len(series_resampled)} < 2 × {seasonal_period} periods)."
        )

    # --- Step 8: Stationarity (ADF) ---
    adf_result = adfuller(series_resampled.dropna(), result_object=False)
    adf_pvalue = float(adf_result[1])

    d = 0
    if adf_pvalue >= ADF_ALPHA:
        diff1 = series_resampled.diff().dropna()
        if len(diff1) > 0:
            adf2 = adfuller(diff1, result_object=False)
            if adf2[1] < ADF_ALPHA:
                d = 1
            else:
                d = min(2, ARIMA_MAX_D)
        else:
            d = 1

    # --- Step 9: ARIMA order selection (grid search, min AIC) ---
    best_aic = float("inf")
    best_order: tuple[int, int, int] = (1, d, 1)

    for p in range(ARIMA_MAX_P + 1):
        for q in range(ARIMA_MAX_Q + 1):
            order = (p, d, q)
            try:
                with _warnings.catch_warnings():
                    _warnings.simplefilter("ignore")
                    trend_arg = "c" if d == 0 else "n"
                    fit = ARIMA(series_resampled, order=order, trend=trend_arg).fit()
                    if fit.aic < best_aic:
                        best_aic = fit.aic
                        best_order = order
            except Exception:
                continue

    if best_aic == float("inf"):
        raise ForecastError("All ARIMA fits failed. The series may be unsuitable for ARIMA.")

    _log.info("Best ARIMA order: %s, AIC: %.4f", best_order, best_aic)

    # --- Step 10: Backtest ---
    backtest: BacktestResult | None = None
    horizon = params.horizon
    if len(series_resampled) - horizon >= FORECAST_MIN_POINTS:
        train = series_resampled.iloc[:-horizon]
        actual = series_resampled.iloc[-horizon:]
        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")
                trend_arg = "c" if best_order[1] == 0 else "n"
                bt_fit = ARIMA(train, order=best_order, trend=trend_arg).fit()
                bt_pred = bt_fit.forecast(steps=horizon)

            mae = float(np.mean(np.abs(actual.values - bt_pred.values)))
            rmse = float(np.sqrt(np.mean((actual.values - bt_pred.values) ** 2)))
            nonzero = actual.values != 0
            mape: float | None = None
            if nonzero.any():
                mape = float(
                    np.mean(
                        np.abs((actual.values[nonzero] - bt_pred.values[nonzero])
                               / actual.values[nonzero])
                    ) * 100
                )

            backtest = BacktestResult(
                actual=actual,
                predicted=bt_pred,
                mae=mae,
                rmse=rmse,
                mape=mape,
            )
        except Exception as exc:
            warn.append(f"Backtest failed: {exc}")
    else:
        warn.append(
            f"Series too short for backtest "
            f"({len(series_resampled)} - {horizon} < {FORECAST_MIN_POINTS})."
        )

    # --- Step 11: Final forecast ---
    try:
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore")
            trend_arg = "c" if best_order[1] == 0 else "n"
            final_fit = ARIMA(series_resampled, order=best_order, trend=trend_arg).fit()
            fcast = final_fit.get_forecast(steps=horizon)
            summary_frame = fcast.summary_frame(alpha=1 - FORECAST_CONF_LEVEL)

        forecast_df = pd.DataFrame(
            {
                "forecast": summary_frame["mean"],
                "lower": summary_frame["mean_ci_lower"],
                "upper": summary_frame["mean_ci_upper"],
            },
            index=summary_frame.index,
        )
    except Exception as exc:
        raise ForecastError(f"Final ARIMA forecast failed: {exc}") from exc

    _log.info("Forecast complete: %d steps ahead.", horizon)

    return ForecastResult(
        params=params,
        freq=freq,
        seasonal_period=seasonal_period,
        series=series_resampled,
        sma=sma,
        ema=ema,
        sma_window=sma_window,
        ema_span=ema_span,
        decomposition=decomposition,
        adf_pvalue=adf_pvalue,
        order=best_order,
        aic=best_aic,
        backtest=backtest,
        forecast=forecast_df,
        warnings=warn,
    )

