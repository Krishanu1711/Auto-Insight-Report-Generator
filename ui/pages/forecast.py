"""
ui/pages/forecast.py — Time-series analysis and ARIMA forecast page.
"""
from __future__ import annotations

import streamlit as st

from src import pipeline as pipe
from src.config import MAX_HORIZON
from src.exceptions import ForecastError
from src.models import ColumnKind, ForecastParams
from ui import components, state

st.title("🔮 Time-Series Forecast")

bundle = components.require_bundle()

# Show forecast error if no forecast yet
if bundle.forecast_error and bundle.forecast is None:
    st.warning(bundle.forecast_error, icon="⚠️")

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
datetime_cols = bundle.profile.cols_of(ColumnKind.DATETIME)
numeric_cols = bundle.profile.cols_of(ColumnKind.NUMERIC)

if not datetime_cols or not numeric_cols:
    st.info(
        "Forecast requires at least one datetime column and one numeric column. "
        "This dataset does not meet those criteria."
    )
    st.stop()

# Default values from existing forecast or profile
default_date = (
    bundle.forecast.params.date_col
    if bundle.forecast else bundle.profile.primary_date_col or datetime_cols[0]
)
default_target = (
    bundle.forecast.params.target_col
    if bundle.forecast else numeric_cols[0]
)
default_agg = bundle.forecast.params.agg if bundle.forecast else "sum"
default_horizon = bundle.forecast.params.horizon if bundle.forecast else 3
default_decomp = bundle.forecast.params.decomposition_model if bundle.forecast else "additive"

with st.form("forecast_form"):
    st.subheader("⚙️ Forecast Parameters")
    col1, col2 = st.columns(2)
    with col1:
        date_col = st.selectbox("Date column", datetime_cols,
                                index=datetime_cols.index(default_date) if default_date in datetime_cols else 0)
        agg = st.selectbox("Aggregation", ["sum", "mean"],
                           index=0 if default_agg == "sum" else 1)
        decomp_model = st.selectbox("Decomposition model", ["additive", "multiplicative"],
                                    index=0 if default_decomp == "additive" else 1)
    with col2:
        target_col = st.selectbox("Target column", numeric_cols,
                                  index=numeric_cols.index(default_target) if default_target in numeric_cols else 0)
        horizon = st.number_input("Forecast horizon (steps)", min_value=1, max_value=MAX_HORIZON,
                                  value=default_horizon)

    submitted = st.form_submit_button("🚀 Run Forecast", type="primary")

if submitted:
    params = ForecastParams(
        date_col=date_col,
        target_col=target_col,
        agg=agg,
        horizon=int(horizon),
        decomposition_model=decomp_model,
    )
    try:
        with st.spinner("Running forecast …"):
            new_bundle = pipe.rerun_forecast(bundle, params)
        state.set_bundle(new_bundle)
        bundle = new_bundle
        st.success("Forecast complete!")
    except ForecastError as exc:
        components.show_error(exc)

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if bundle.forecast is not None:
    fc = bundle.forecast
    components.show_warnings(fc.warnings)

    tab_trend, tab_decomp, tab_fcast = st.tabs(
        ["📈 Trend & Moving Averages", "🔬 Decomposition", "🔮 Forecast"]
    )

    # Find charts by id
    chart_map = {s.id: s for s in bundle.forecast_charts}

    with tab_trend:
        if "ts__trend" in chart_map:
            components.render_chart(chart_map["ts__trend"])

    with tab_decomp:
        if "ts__decomposition" in chart_map:
            components.render_chart(chart_map["ts__decomposition"])
        else:
            st.info("Decomposition not available (insufficient data points).")

    with tab_fcast:
        if "ts__forecast" in chart_map:
            components.render_chart(chart_map["ts__forecast"])

        st.subheader("Forecast Details")
        components.metric_row([
            ("ARIMA Order", str(fc.order)),
            ("AIC", f"{fc.aic:.4f}"),
            ("Frequency", fc.freq),
            ("Seasonal Period", fc.seasonal_period),
        ])

        if fc.backtest is not None:
            st.subheader("Backtest Metrics")
            bt = fc.backtest
            metrics = [
                ("MAE", f"{bt.mae:.4f}"),
                ("RMSE", f"{bt.rmse:.4f}"),
            ]
            if bt.mape is not None:
                metrics.append(("MAPE", f"{bt.mape:.1f}%"))
            components.metric_row(metrics)

        st.subheader("Forecast Table")
        st.dataframe(fc.forecast.round(4), use_container_width=True)

