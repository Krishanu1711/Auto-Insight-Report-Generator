"""tests/test_transform_analyze.py"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analyze import analyze, summarize_text
from src.models import ColumnKind
from src.profile import profile
from src.transform import transform


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

@pytest.fixture
def tabular_df():
    rng = np.random.default_rng(42)
    n = 100
    return pd.DataFrame({
        "sales": rng.uniform(10, 2000, n),
        "profit": rng.uniform(-100, 800, n),
        "region": np.random.choice(["East", "West", "North", "South"], n),
        "flag": np.random.choice([True, False], n),
    })


def test_minmax_range(tabular_df):
    p = profile(tabular_df)
    result = transform(tabular_df, p)
    mm = result.scaled_minmax
    if not mm.empty:
        assert mm.min().min() >= -0.01
        assert mm.max().max() <= 1.01


def test_standard_scale_mean_std(tabular_df):
    p = profile(tabular_df)
    result = transform(tabular_df, p)
    ss = result.scaled_standard
    if not ss.empty:
        assert abs(ss.mean().mean()) < 0.01
        assert abs(ss.std().mean() - 1.0) < 0.05


def test_binned_columns(tabular_df):
    p = profile(tabular_df)
    result = transform(tabular_df, p)
    # Should have _bin columns for numeric cols
    assert not result.binned.empty
    for col in result.binned.columns:
        assert col.endswith("_bin")


def test_one_hot_non_negative(tabular_df):
    p = profile(tabular_df)
    result = transform(tabular_df, p)
    if not result.one_hot.empty:
        assert result.one_hot.min().min() >= 0
        assert result.one_hot.max().max() <= 1


def test_ml_ready_shape(tabular_df):
    p = profile(tabular_df)
    result = transform(tabular_df, p)
    ml = result.ml_ready
    expected_cols = result.scaled_standard.shape[1] + result.one_hot.shape[1]
    assert ml.shape[1] == expected_cols


def test_transform_does_not_mutate(tabular_df):
    original = tabular_df.copy()
    p = profile(tabular_df)
    transform(tabular_df, p)
    pd.testing.assert_frame_equal(tabular_df, original)


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------

def test_descriptive_stats(tabular_df):
    p = profile(tabular_df)
    result = analyze(tabular_df, p)
    assert result.descriptive is not None
    assert "mean" in result.descriptive.columns


def test_correlation_pearson(tabular_df):
    p = profile(tabular_df)
    result = analyze(tabular_df, p)
    if result.correlation is not None:
        # Diagonal should be 1
        for col in result.correlation.columns:
            assert abs(result.correlation.loc[col, col] - 1.0) < 0.001


def test_text_summary():
    df = pd.DataFrame({
        "line_no": [1, 2, 3],
        "text": [
            "The quick brown fox jumps over the lazy dog.",
            "Data analysis is fascinating and useful.",
            "Machine learning models require clean data.",
        ]
    })
    summary = summarize_text(df)
    assert summary.n_lines == 3
    assert summary.n_words > 0
    assert len(summary.top_words) > 0
    # Stop words should be removed
    words = [w for w, _ in summary.top_words]
    assert "the" not in words
    assert "is" not in words

