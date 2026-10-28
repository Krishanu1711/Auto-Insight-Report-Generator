"""
tests/conftest.py — Shared pytest fixtures.

Provides:
- dirty_df         : a messy DataFrame for cleaning tests
- monthly_series   : a 36-month seasonal series with trend for forecast tests
- sample_profile   : a hand-built DatasetProfile
- sample_bundle    : a stub AnalysisBundle for UI / report tests
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from src.models import (
    AnalysisBundle,
    AnalysisResult,
    ChartGroup,
    ChartKind,
    ChartSpec,
    CleanResult,
    CleaningAction,
    CleaningConfig,
    CleaningStep,
    ColumnKind,
    ColumnProfile,
    DatasetProfile,
    ForecastParams,
    Insight,
    PipelineConfig,
    QualityStats,
    SourceFormat,
    SourceInfo,
    TransformResult,
)


# ---------------------------------------------------------------------------
# dirty_df — for cleaning tests
# ---------------------------------------------------------------------------

@pytest.fixture
def dirty_df() -> pd.DataFrame:
    """A DataFrame with nulls, duplicates, case variants, numeric-as-text and outliers."""
    data = {
        "Order ID": ["ORD-001", "ORD-002", "ORD-003", "ORD-002", "ORD-004", "ORD-005"],
        "Region": ["West", "west", "WEST", "west", "East", "east"],
        "Sales": ["$1,234.56", "500", "N/A", "$500", "750.00", "99999"],  # outlier at end
        "Discount": ["0.1", "0.2", "?", "0.2", "0.3", "0.1"],
        "Profit": [100.0, 200.0, None, 200.0, 150.0, 180.0],
        "Date": ["2023-01-01", "2023-01-02", "null", "2023-01-02", "2023-01-04", "2023-01-05"],
        "Notes": ["ok", "fine", "  good  ", "fine", "", "great"],
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# monthly_series — for forecast tests
# ---------------------------------------------------------------------------

@pytest.fixture
def monthly_series() -> pd.DataFrame:
    """36-month seasonal series with a linear trend."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2021-01-01", periods=36, freq="MS")
    trend = np.linspace(100, 200, 36)
    seasonal = 20 * np.sin(2 * np.pi * np.arange(36) / 12)
    noise = rng.normal(0, 5, 36)
    values = trend + seasonal + noise
    return pd.DataFrame({"date": dates, "sales": values})


# ---------------------------------------------------------------------------
# sample_profile — for transform/analyze/visualize tests
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_profile() -> DatasetProfile:
    """A hand-built DatasetProfile with numeric, categorical and datetime columns."""
    columns = [
        ColumnProfile(
            name="sales", dtype="float64", kind=ColumnKind.NUMERIC,
            n_missing=0, pct_missing=0.0, n_unique=100, unique_ratio=1.0,
            sample_values=["100.0", "200.0", "300.0"],
            numeric_stats={"min": 10.0, "max": 2000.0, "mean": 500.0,
                           "median": 450.0, "std": 300.0, "skew": 0.5},
            top_values=None, date_range=None,
        ),
        ColumnProfile(
            name="profit", dtype="float64", kind=ColumnKind.NUMERIC,
            n_missing=0, pct_missing=0.0, n_unique=80, unique_ratio=0.8,
            sample_values=["50.0", "100.0", "150.0"],
            numeric_stats={"min": -100.0, "max": 800.0, "mean": 200.0,
                           "median": 180.0, "std": 150.0, "skew": -0.3},
            top_values=None, date_range=None,
        ),
        ColumnProfile(
            name="region", dtype="object", kind=ColumnKind.CATEGORICAL,
            n_missing=0, pct_missing=0.0, n_unique=4, unique_ratio=0.04,
            sample_values=["East", "West", "North"],
            numeric_stats=None,
            top_values=[("East", 40), ("West", 30), ("North", 20), ("South", 10)],
            date_range=None,
        ),
        ColumnProfile(
            name="order_date", dtype="datetime64[ns]", kind=ColumnKind.DATETIME,
            n_missing=0, pct_missing=0.0, n_unique=365, unique_ratio=0.9,
            sample_values=["2021-01-01", "2021-06-15", "2022-12-31"],
            numeric_stats=None, top_values=None,
            date_range=("2021-01-01", "2022-12-31"),
        ),
    ]
    return DatasetProfile(
        n_rows=100,
        n_cols=4,
        columns=columns,
        primary_date_col="order_date",
        memory_mb=0.05,
    )


# ---------------------------------------------------------------------------
# sample_bundle — stub AnalysisBundle for UI and report tests
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_bundle(sample_profile: DatasetProfile) -> AnalysisBundle:
    """A minimal but complete AnalysisBundle for UI / report tests."""
    import plotly.graph_objects as go

    rng = np.random.default_rng(42)
    n = 100
    dates = pd.date_range("2021-01-01", periods=n)
    df = pd.DataFrame({
        "sales": rng.uniform(10, 2000, n),
        "profit": rng.uniform(-100, 800, n),
        "region": rng.choice(["East", "West", "North", "South"], n),
        "order_date": dates,
    })

    source = SourceInfo(
        filename="test_orders.csv",
        source_format=SourceFormat.CSV,
        file_sha256="abc123",
        n_rows_raw=n,
        n_cols_raw=4,
        is_unstructured=False,
        raw_preview=df.head(5).copy(),
    )

    quality = QualityStats(n_rows=n, n_cols=4, missing_cells=0,
                           duplicate_rows=0, outlier_cells=2)
    clean_result = CleanResult(
        df=df,
        actions=[
            CleaningAction(
                step=CleaningStep.RENAME_COLUMNS,
                column=None,
                description="Renamed 0 column(s) to snake_case.",
                rows_affected=0,
            )
        ],
        quality_before=quality,
        quality_after=quality,
        rename_map={c: c for c in df.columns},
    )

    from src.models import CorrPair
    analysis = AnalysisResult(
        descriptive=pd.DataFrame(
            {"mean": [500.0, 200.0], "std": [300.0, 150.0]},
            index=["sales", "profit"],
        ),
        correlation=pd.DataFrame(
            [[1.0, 0.6], [0.6, 1.0]],
            index=["sales", "profit"],
            columns=["sales", "profit"],
        ),
        top_pairs=[CorrPair(x="sales", y="profit", r=0.6)],
        regression=None,
        text_summary=None,
    )

    transform_result = TransformResult(
        scaled_minmax=pd.DataFrame({"sales": [0.5], "profit": [0.6]}),
        scaled_standard=pd.DataFrame({"sales": [0.1], "profit": [0.2]}),
        label_encoded=pd.DataFrame({"region": [0]}),
        one_hot=pd.DataFrame({"region_East": [1], "region_West": [0]}),
        binned=pd.DataFrame({"sales_bin": ["Q2"]}),
        aggregations={},
        ml_ready=pd.DataFrame({"sales": [0.1], "profit": [0.2], "region_East": [1]}),
    )

    dummy_fig = go.Figure()
    charts = [
        ChartSpec(
            id="hist__sales",
            title="Distribution of sales",
            kind=ChartKind.HISTOGRAM,
            group=ChartGroup.DISTRIBUTION,
            columns=["sales"],
            figure=dummy_fig,
            description="Distribution of sales across 100 rows.",
        )
    ]

    return AnalysisBundle(
        source=source,
        clean=clean_result,
        profile=sample_profile,
        transform=transform_result,
        analysis=analysis,
        charts=charts,
        forecast=None,
        forecast_charts=[],
        forecast_error="No date column found, so no forecast was created.",
        insights=[
            Insight(level="info", category="quality", text="Test insight."),
        ],
        config=PipelineConfig(),
        created_at=datetime.now(timezone.utc),
    )

