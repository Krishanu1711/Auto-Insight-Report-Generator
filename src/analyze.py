"""
src/analyze.py — Descriptive statistics, correlation, regression, text summary.

Public API
----------
analyze(df, profile)      -> AnalysisResult
summarize_text(df)        -> TextSummary
"""
from __future__ import annotations

import collections
import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from src.config import (
    HEATMAP_MAX_COLS,
    RANDOM_STATE,
    REGRESSION_MIN_ROWS,
    REGRESSION_TEST_SIZE,
    SCATTER_MIN_ABS_R,
    TOP_PAIRS_N,
    TOP_WORDS_N,
)
from src.models import (
    AnalysisResult,
    ColumnKind,
    CorrPair,
    DatasetProfile,
    RegressionResult,
    TextSummary,
)
from src.utils import get_logger

_log = get_logger(__name__)


def analyze(df: pd.DataFrame, profile: DatasetProfile) -> AnalysisResult:
    """Compute descriptive statistics, correlation, and regression for *df*.

    Never raises for missing column types; returns empty results with warnings.
    """
    _log.info("Analyzing %d rows × %d cols", len(df), df.shape[1])
    warnings: list[str] = []

    numeric_cols = profile.cols_of(ColumnKind.NUMERIC)
    valid_numeric = [c for c in numeric_cols if c in df.columns]

    # --- Descriptive statistics ---
    descriptive = _descriptive(df, valid_numeric, warnings)

    # --- Correlation matrix ---
    correlation, top_pairs = _correlation(df, valid_numeric, warnings)

    # --- Linear regression ---
    regression = _regression(df, top_pairs, warnings)

    _log.info("Analysis complete.")

    return AnalysisResult(
        descriptive=descriptive,
        correlation=correlation,
        top_pairs=top_pairs,
        regression=regression,
        text_summary=None,
        warnings=warnings,
    )


def summarize_text(df: pd.DataFrame) -> TextSummary:
    """Compute a word-frequency summary for an unstructured text DataFrame.

    *df* must have a ``text`` column.
    """
    if "text" not in df.columns:
        return TextSummary(n_lines=0, n_words=0, avg_words_per_line=0.0, top_words=[])

    lines = df["text"].dropna().tolist()
    n_lines = len(lines)

    token_re = re.compile(r"[a-z']+")
    all_tokens: list[str] = []
    for line in lines:
        tokens = token_re.findall(line.lower())
        filtered = [t for t in tokens if t not in ENGLISH_STOP_WORDS and len(t) > 1]
        all_tokens.extend(filtered)

    n_words = len(all_tokens)
    avg_words_per_line = n_words / n_lines if n_lines > 0 else 0.0

    counter = collections.Counter(all_tokens)
    top_words = counter.most_common(TOP_WORDS_N)

    return TextSummary(
        n_lines=n_lines,
        n_words=n_words,
        avg_words_per_line=round(avg_words_per_line, 2),
        top_words=top_words,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _descriptive(
    df: pd.DataFrame,
    numeric_cols: list[str],
    warnings: list[str],
) -> pd.DataFrame | None:
    """One row per numeric column with key statistics."""
    if not numeric_cols:
        warnings.append("No numeric columns found; skipping descriptive statistics.")
        return None

    rows = []
    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        mode_vals = s.mode()
        mode_val = float(mode_vals.iloc[0]) if len(mode_vals) > 0 else float("nan")
        q1 = float(s.quantile(0.25))
        q3 = float(s.quantile(0.75))
        rows.append({
            "column": col,
            "mean": float(s.mean()),
            "median": float(s.median()),
            "mode": mode_val,
            "std": float(s.std()),
            "variance": float(s.var()),
            "min": float(s.min()),
            "max": float(s.max()),
            "range": float(s.max() - s.min()),
            "q1": q1,
            "q3": q3,
            "skew": float(s.skew()),
        })

    if not rows:
        return None
    return pd.DataFrame(rows).set_index("column")


def _correlation(
    df: pd.DataFrame,
    numeric_cols: list[str],
    warnings: list[str],
) -> tuple[pd.DataFrame | None, list[CorrPair]]:
    """Pearson correlation matrix and top pairs."""
    if len(numeric_cols) < 2:
        if numeric_cols:
            warnings.append("Fewer than 2 numeric columns; no correlation matrix computed.")
        return None, []

    cols = numeric_cols[:HEATMAP_MAX_COLS]
    corr_df = df[cols].corr(method="pearson", numeric_only=True)

    pairs: list[CorrPair] = []
    seen: set[frozenset] = set()
    for i, x in enumerate(cols):
        for y in cols[i + 1:]:
            key = frozenset([x, y])
            if key in seen:
                continue
            seen.add(key)
            r = corr_df.loc[x, y]
            if pd.isna(r):
                continue
            if abs(r) >= SCATTER_MIN_ABS_R:
                pairs.append(CorrPair(x=x, y=y, r=float(r)))

    pairs.sort(key=lambda p: abs(p.r), reverse=True)
    top_pairs = pairs[:TOP_PAIRS_N]

    return corr_df, top_pairs


def _regression(
    df: pd.DataFrame,
    top_pairs: list[CorrPair],
    warnings: list[str],
) -> RegressionResult | None:
    """Fit OLS on the strongest correlated pair (if available)."""
    if not top_pairs:
        return None

    pair = top_pairs[0]
    x_col, y_col = pair.x, pair.y
    subset = df[[x_col, y_col]].dropna()

    if len(subset) < REGRESSION_MIN_ROWS:
        warnings.append(
            f"Only {len(subset)} rows for regression (min {REGRESSION_MIN_ROWS}). Skipped."
        )
        return None

    X = subset[[x_col]].values
    y = subset[y_col].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=REGRESSION_TEST_SIZE, random_state=RANDOM_STATE
    )

    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(np.mean((y_test - y_pred) ** 2)))
    r2 = float(model.score(X_test, y_test))

    return RegressionResult(
        x=x_col,
        y=y_col,
        coef=float(model.coef_[0]),
        intercept=float(model.intercept_),
        r2=r2,
        mae=mae,
        rmse=rmse,
        n_train=len(X_train),
        n_test=len(X_test),
        y_test=y_test.tolist(),
        y_pred=y_pred.tolist(),
    )

