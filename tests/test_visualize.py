"""tests/test_visualize.py"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analyze import analyze
from src.models import ChartGroup, ChartKind, TextSummary
from src.profile import profile
from src.transform import transform
from src.visualize import build_charts, build_forecast_charts, build_text_charts


@pytest.fixture
def tabular_df():
    rng = np.random.default_rng(42)
    n = 100
    return pd.DataFrame({
        "sales": rng.uniform(10, 2000, n),
        "profit": rng.uniform(-100, 800, n),
        "region": np.random.choice(["East", "West", "North", "South"], n),
    })


def test_build_charts_produces_expected_ids(tabular_df):
    p = profile(tabular_df)
    tr = transform(tabular_df, p)
    an = analyze(tabular_df, p)
    charts = build_charts(tabular_df, p, an, tr)
    ids = [c.id for c in charts]
    assert "hist__sales" in ids
    assert "box__sales" in ids


def test_build_charts_empty_no_usable_cols():
    df = pd.DataFrame({"id_col": range(100)})
    p = profile(df)
    from src.models import TransformResult, AnalysisResult
    tr = TransformResult(
        scaled_minmax=pd.DataFrame(), scaled_standard=pd.DataFrame(),
        label_encoded=pd.DataFrame(), one_hot=pd.DataFrame(),
        binned=pd.DataFrame(), aggregations={}, ml_ready=pd.DataFrame(),
    )
    an = AnalysisResult(
        descriptive=None, correlation=None, top_pairs=[],
        regression=None, text_summary=None,
    )
    charts = build_charts(df, p, an, tr)
    # Should return empty list (only ID_LIKE column)
    assert charts == []


def test_all_charts_serializable(tabular_df):
    p = profile(tabular_df)
    tr = transform(tabular_df, p)
    an = analyze(tabular_df, p)
    charts = build_charts(tabular_df, p, an, tr)
    for c in charts:
        json_str = c.figure.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 10


def test_build_text_charts():
    summary = TextSummary(
        n_lines=5,
        n_words=30,
        avg_words_per_line=6.0,
        top_words=[("data", 5), ("analysis", 4), ("python", 3)],
    )
    charts = build_text_charts(summary)
    assert len(charts) == 1
    assert charts[0].id == "text__top_words"
    assert charts[0].group == ChartGroup.TEXT


def test_build_text_charts_empty():
    summary = TextSummary(n_lines=0, n_words=0, avg_words_per_line=0.0, top_words=[])
    charts = build_text_charts(summary)
    assert charts == []

