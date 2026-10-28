"""
src/visualize.py — Automatic chart selection using Plotly.

Public API
----------
build_charts(df, profile, analysis, transform)  -> list[ChartSpec]
build_text_charts(summary)                       -> list[ChartSpec]
build_forecast_charts(result)                    -> list[ChartSpec]
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import (
    CHART_MAX_POINTS,
    COLOR_SEQUENCE,
    MAX_CATEGORICAL_CHART_COLS,
    MAX_NUMERIC_CHART_COLS,
    MAX_SCATTER_PAIRS,
    PLOTLY_TEMPLATE,
    RANDOM_STATE,
    TOP_N_BAR,
    TOP_WORDS_N,
)
from src.models import (
    AnalysisResult,
    ChartGroup,
    ChartKind,
    ChartSpec,
    ColumnKind,
    DatasetProfile,
    ForecastResult,
    TextSummary,
    TransformResult,
)
from src.utils import get_logger

_log = get_logger(__name__)

_rng = np.random.default_rng(RANDOM_STATE)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def build_charts(
    df: pd.DataFrame,
    profile: DatasetProfile,
    analysis: AnalysisResult,
    transform: TransformResult,
) -> list[ChartSpec]:
    """Build all automatic charts for a tabular dataset."""
    _log.info("Building charts for %d rows × %d cols", len(df), df.shape[1])
    specs: list[ChartSpec] = []

    numeric_cols = profile.cols_of(ColumnKind.NUMERIC)
    cat_cols = (
        profile.cols_of(ColumnKind.CATEGORICAL)
        + profile.cols_of(ColumnKind.BOOLEAN)
    )
    hc_cols = profile.cols_of(ColumnKind.HIGH_CARDINALITY)

    # -- Distributions: histogram + box per numeric column --
    for col in numeric_cols[:MAX_NUMERIC_CHART_COLS]:
        if col not in df.columns:
            continue
        specs.append(_histogram(df, col))
        specs.append(_box_plot(df, col))

    # -- Categories: pie / donut / bar per categorical column --
    for col in cat_cols[:MAX_CATEGORICAL_CHART_COLS]:
        if col not in df.columns:
            continue
        specs.append(_cat_chart(df, col))

    # -- High-cardinality: top-N bar (max 2) --
    for col in hc_cols[:2]:
        if col not in df.columns:
            continue
        specs.append(_top_n_bar(df, col, id_prefix="top"))

    # -- Aggregation charts --
    for agg_key, agg_df in transform.aggregations.items():
        cat_col = agg_key[len("by_"):]
        num_cols_in_agg = [
            c.split("_mean")[0]
            for c in agg_df.columns
            if c.endswith("_mean")
        ]
        for num_col in num_cols_in_agg[:2]:
            mean_col = f"{num_col}_mean"
            if mean_col in agg_df.columns and cat_col in agg_df.columns:
                specs.append(_agg_bar(agg_df, cat_col, num_col, mean_col))

        # Grouped box (first cat × first numeric)
        if num_cols_in_agg and cat_col in df.columns:
            num_col = num_cols_in_agg[0]
            if num_col in df.columns:
                specs.append(_grouped_box(df, cat_col, num_col))

    # -- Scatter plots for correlated pairs --
    for pair in analysis.top_pairs[:MAX_SCATTER_PAIRS]:
        if pair.x in df.columns and pair.y in df.columns:
            specs.append(_scatter(df, pair.x, pair.y, pair.r))

    # -- Correlation heatmap --
    if analysis.correlation is not None:
        specs.append(_heatmap(analysis.correlation))

    _log.info("Built %d chart(s).", len(specs))
    return specs


def build_text_charts(summary: TextSummary) -> list[ChartSpec]:
    """Build a word-frequency bar chart from a TextSummary."""
    if not summary.top_words:
        return []

    words = [w for w, _ in summary.top_words]
    counts = [c for _, c in summary.top_words]

    fig = go.Figure(
        go.Bar(
            x=counts[::-1],
            y=words[::-1],
            orientation="h",
            marker_color=COLOR_SEQUENCE[0],
        )
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Top Words",
        xaxis_title="Count",
        yaxis_title="Word",
        margin={"l": 120},
    )
    return [
        ChartSpec(
            id="text__top_words",
            title="Top Words",
            kind=ChartKind.BAR,
            group=ChartGroup.TEXT,
            columns=[],
            figure=fig,
            description=f"Top {len(words)} most frequent words after removing stop words.",
        )
    ]


def build_forecast_charts(result: ForecastResult) -> list[ChartSpec]:
    """Build the three forecast-related charts from a ForecastResult."""
    specs: list[ChartSpec] = []
    col_name = result.params.target_col

    # --- ts__trend: series + SMA + EMA ---
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=result.series.index, y=result.series.values,
        name="Observed", line=dict(color=COLOR_SEQUENCE[0]),
    ))
    fig_trend.add_trace(go.Scatter(
        x=result.sma.index, y=result.sma.values,
        name=f"SMA({result.sma_window})", line=dict(color=COLOR_SEQUENCE[1], dash="dash"),
    ))
    fig_trend.add_trace(go.Scatter(
        x=result.ema.index, y=result.ema.values,
        name=f"EMA({result.ema_span})", line=dict(color=COLOR_SEQUENCE[2], dash="dot"),
    ))
    fig_trend.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Trend and Moving Averages — {col_name}",
        xaxis_title="Date",
        yaxis_title=col_name,
    )
    specs.append(ChartSpec(
        id="ts__trend",
        title=f"Trend and Moving Averages — {col_name}",
        kind=ChartKind.LINE,
        group=ChartGroup.TIME_SERIES,
        columns=[col_name],
        figure=fig_trend,
        description=f"Observed {col_name} with SMA and EMA overlays.",
    ))

    # --- ts__decomposition ---
    if result.decomposition is not None:
        dec = result.decomposition
        fig_dec = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            subplot_titles=["Observed", "Trend", "Seasonal", "Residual"],
            vertical_spacing=0.06,
        )
        for row, (series, color) in enumerate(
            zip(
                [dec.observed, dec.trend, dec.seasonal, dec.resid],
                COLOR_SEQUENCE[:4],
            ),
            start=1,
        ):
            fig_dec.add_trace(
                go.Scatter(x=series.index, y=series.values, line=dict(color=color)),
                row=row, col=1,
            )
        fig_dec.update_layout(
            template=PLOTLY_TEMPLATE,
            title=f"Seasonal Decomposition ({dec.model}) — {col_name}",
            showlegend=False,
            height=700,
        )
        specs.append(ChartSpec(
            id="ts__decomposition",
            title=f"Seasonal Decomposition — {col_name}",
            kind=ChartKind.DECOMPOSITION,
            group=ChartGroup.TIME_SERIES,
            columns=[col_name],
            figure=fig_dec,
            description=f"Seasonal decomposition ({dec.model}) of {col_name}.",
        ))

    # --- ts__forecast ---
    horizon = result.params.horizon
    n_history = max(24, 5 * horizon)
    history_series = result.series.iloc[-n_history:]

    fig_fc = go.Figure()
    fig_fc.add_trace(go.Scatter(
        x=history_series.index, y=history_series.values,
        name="History", line=dict(color=COLOR_SEQUENCE[0]),
    ))

    if result.backtest is not None:
        bt = result.backtest
        fig_fc.add_trace(go.Scatter(
            x=bt.actual.index, y=bt.predicted.values,
            name="Backtest", line=dict(color=COLOR_SEQUENCE[3], dash="dash"),
        ))

    fc_df = result.forecast
    fig_fc.add_trace(go.Scatter(
        x=fc_df.index, y=fc_df["forecast"].values,
        name="Forecast", line=dict(color=COLOR_SEQUENCE[1]),
    ))
    fig_fc.add_trace(go.Scatter(
        x=list(fc_df.index) + list(fc_df.index[::-1]),
        y=list(fc_df["upper"].values) + list(fc_df["lower"].values[::-1]),
        fill="toself",
        fillcolor=f"rgba(99,110,250,0.15)",
        line=dict(color="rgba(0,0,0,0)"),
        name="95% CI",
    ))
    fig_fc.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Forecast — {col_name}",
        xaxis_title="Date",
        yaxis_title=col_name,
    )
    specs.append(ChartSpec(
        id="ts__forecast",
        title=f"Forecast — {col_name}",
        kind=ChartKind.FORECAST,
        group=ChartGroup.TIME_SERIES,
        columns=[col_name],
        figure=fig_fc,
        description=f"ARIMA{result.order} forecast of {col_name} for {horizon} step(s) ahead.",
    ))

    return specs


# ---------------------------------------------------------------------------
# Individual chart builders
# ---------------------------------------------------------------------------

def _histogram(df: pd.DataFrame, col: str) -> ChartSpec:
    data = df[col].dropna().values.astype(float)
    counts, bin_edges = np.histogram(data, bins=30)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    fig = go.Figure(
        go.Bar(x=bin_centers, y=counts, marker_color=COLOR_SEQUENCE[0])
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Distribution of {col}",
        xaxis_title=col,
        yaxis_title="Count",
        bargap=0.02,
    )
    return ChartSpec(
        id=f"hist__{col}",
        title=f"Distribution of {col}",
        kind=ChartKind.HISTOGRAM,
        group=ChartGroup.DISTRIBUTION,
        columns=[col],
        figure=fig,
        description=f"Distribution of {col} across {len(data):,} rows.",
    )


def _box_plot(df: pd.DataFrame, col: str) -> ChartSpec:
    data = df[col].dropna().values.astype(float)
    if len(data) > CHART_MAX_POINTS:
        idx = _rng.choice(len(data), CHART_MAX_POINTS, replace=False)
        data = data[idx]

    fig = go.Figure(
        go.Box(y=data, name=col, marker_color=COLOR_SEQUENCE[1], boxmean=True)
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Box Plot of {col}",
        yaxis_title=col,
    )
    return ChartSpec(
        id=f"box__{col}",
        title=f"Box Plot of {col}",
        kind=ChartKind.BOX,
        group=ChartGroup.DISTRIBUTION,
        columns=[col],
        figure=fig,
        description=f"Box plot of {col} showing median, IQR and outliers.",
    )


def _cat_chart(df: pd.DataFrame, col: str) -> ChartSpec:
    vc = df[col].value_counts()
    n_unique = len(vc)

    if n_unique <= 4:
        kind = ChartKind.PIE
        fig = go.Figure(
            go.Pie(
                labels=vc.index.astype(str).tolist(),
                values=vc.values.tolist(),
                marker_colors=COLOR_SEQUENCE,
            )
        )
    elif n_unique <= 8:
        kind = ChartKind.DONUT
        fig = go.Figure(
            go.Pie(
                labels=vc.index.astype(str).tolist(),
                values=vc.values.tolist(),
                hole=0.45,
                marker_colors=COLOR_SEQUENCE,
            )
        )
    else:
        kind = ChartKind.BAR
        top = vc.head(TOP_N_BAR)
        fig = go.Figure(
            go.Bar(
                x=top.values[::-1].tolist(),
                y=top.index.astype(str).tolist()[::-1],
                orientation="h",
                marker_color=COLOR_SEQUENCE[0],
            )
        )
        fig.update_layout(margin={"l": 140})

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Distribution of {col}",
    )
    return ChartSpec(
        id=f"cat__{col}",
        title=f"Distribution of {col}",
        kind=kind,
        group=ChartGroup.CATEGORY,
        columns=[col],
        figure=fig,
        description=f"Breakdown of {n_unique} category values in '{col}'.",
    )


def _top_n_bar(df: pd.DataFrame, col: str, id_prefix: str = "top") -> ChartSpec:
    vc = df[col].value_counts().head(TOP_N_BAR)
    fig = go.Figure(
        go.Bar(
            x=vc.values[::-1].tolist(),
            y=vc.index.astype(str).tolist()[::-1],
            orientation="h",
            marker_color=COLOR_SEQUENCE[2],
        )
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Top {TOP_N_BAR} values in {col}",
        margin={"l": 140},
    )
    return ChartSpec(
        id=f"{id_prefix}__{col}",
        title=f"Top values in {col}",
        kind=ChartKind.BAR,
        group=ChartGroup.CATEGORY,
        columns=[col],
        figure=fig,
        description=f"Top {min(TOP_N_BAR, len(vc))} most frequent values in '{col}'.",
    )


def _agg_bar(
    agg_df: pd.DataFrame,
    cat_col: str,
    num_col: str,
    mean_col: str,
) -> ChartSpec:
    fig = go.Figure(
        go.Bar(
            x=agg_df[cat_col].astype(str).tolist(),
            y=agg_df[mean_col].tolist(),
            marker_color=COLOR_SEQUENCE[3],
        )
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"Mean {num_col} by {cat_col}",
        xaxis_title=cat_col,
        yaxis_title=f"Mean {num_col}",
    )
    return ChartSpec(
        id=f"catnum__{cat_col}__{num_col}",
        title=f"Mean {num_col} by {cat_col}",
        kind=ChartKind.BAR,
        group=ChartGroup.CATEGORY,
        columns=[cat_col, num_col],
        figure=fig,
        description=f"Average {num_col} for each value of {cat_col}.",
    )


def _grouped_box(df: pd.DataFrame, cat_col: str, num_col: str) -> ChartSpec:
    categories = df[cat_col].dropna().unique()
    fig = go.Figure()
    for i, cat in enumerate(categories):
        subset = df[df[cat_col] == cat][num_col].dropna()
        fig.add_trace(go.Box(
            y=subset.values.tolist(),
            name=str(cat),
            marker_color=COLOR_SEQUENCE[i % len(COLOR_SEQUENCE)],
        ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"{num_col} by {cat_col}",
        yaxis_title=num_col,
        xaxis_title=cat_col,
        showlegend=False,
    )
    return ChartSpec(
        id=f"boxby__{cat_col}__{num_col}",
        title=f"{num_col} by {cat_col}",
        kind=ChartKind.BOX,
        group=ChartGroup.CATEGORY,
        columns=[cat_col, num_col],
        figure=fig,
        description=f"Distribution of {num_col} grouped by {cat_col}.",
    )


def _scatter(df: pd.DataFrame, x: str, y: str, r: float) -> ChartSpec:
    subset = df[[x, y]].dropna()
    if len(subset) > CHART_MAX_POINTS:
        subset = subset.sample(CHART_MAX_POINTS, random_state=RANDOM_STATE)

    xv = subset[x].values.astype(float)
    yv = subset[y].values.astype(float)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xv.tolist(), y=yv.tolist(),
        mode="markers",
        marker=dict(color=COLOR_SEQUENCE[0], opacity=0.6, size=5),
        name="Data",
    ))

    # Trend line
    if len(xv) >= 2:
        coefs = np.polyfit(xv, yv, deg=1)
        x_line = np.linspace(xv.min(), xv.max(), 100)
        y_line = np.polyval(coefs, x_line)
        fig.add_trace(go.Scatter(
            x=x_line.tolist(), y=y_line.tolist(),
            mode="lines",
            line=dict(color=COLOR_SEQUENCE[1], dash="dash"),
            name="Trend",
        ))

    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=f"{x} vs {y} (r = {r:.2f})",
        xaxis_title=x,
        yaxis_title=y,
    )
    return ChartSpec(
        id=f"scatter__{x}__{y}",
        title=f"{x} vs {y}",
        kind=ChartKind.SCATTER,
        group=ChartGroup.RELATIONSHIP,
        columns=[x, y],
        figure=fig,
        description=f"Scatter plot of {x} vs {y} with correlation r = {r:.2f}.",
    )


def _heatmap(corr_df: pd.DataFrame) -> ChartSpec:
    cols = corr_df.columns.tolist()
    z = corr_df.values.tolist()
    text = [[f"{v:.2f}" for v in row] for row in corr_df.values]

    fig = go.Figure(
        go.Heatmap(
            x=cols, y=cols, z=z,
            zmin=-1, zmax=1,
            colorscale="RdBu",
            text=text,
            texttemplate="%{text}",
            showscale=True,
        )
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title="Correlation Heatmap",
        height=max(400, 50 * len(cols)),
    )
    return ChartSpec(
        id="heatmap__corr",
        title="Correlation Heatmap",
        kind=ChartKind.HEATMAP,
        group=ChartGroup.RELATIONSHIP,
        columns=cols,
        figure=fig,
        description=f"Pearson correlation matrix for {len(cols)} numeric columns.",
    )

