"""
src/transform.py — Scaling, encoding, binning, and aggregation.

Public API
----------
transform(df, profile) -> TransformResult
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, OrdinalEncoder, StandardScaler

from src.config import ENCODED_MAX_COLUMNS, RANDOM_STATE
from src.models import ColumnKind, DatasetProfile, TransformResult
from src.utils import get_logger

_log = get_logger(__name__)


def transform(df: pd.DataFrame, profile: DatasetProfile) -> TransformResult:
    """Produce all transformed views of the cleaned DataFrame *df*.

    The input DataFrame is never mutated.
    """
    _log.info("Transforming %d rows × %d cols", len(df), df.shape[1])
    df = df.copy()
    warnings: list[str] = []

    numeric_cols = profile.cols_of(ColumnKind.NUMERIC)
    cat_cols = profile.cols_of(ColumnKind.CATEGORICAL) + profile.cols_of(ColumnKind.BOOLEAN)

    # --- Min-max scaling ---
    scaled_minmax = _scale(df, numeric_cols, MinMaxScaler(), "min-max", warnings)

    # --- Standard scaling ---
    scaled_standard = _scale(df, numeric_cols, StandardScaler(), "standard", warnings)

    # --- Label encoding ---
    label_encoded = _label_encode(df, cat_cols, warnings)

    # --- One-hot encoding ---
    one_hot = _one_hot(df, cat_cols, warnings)

    # --- Binning ---
    binned = _bin(df, numeric_cols, warnings)

    # --- Aggregations ---
    aggregations = _aggregate(df, profile, numeric_cols, warnings)

    # --- ML-ready (scaled_standard + one_hot) ---
    ml_ready = _ml_ready(scaled_standard, one_hot)

    _log.info("Transform complete.")

    return TransformResult(
        scaled_minmax=scaled_minmax,
        scaled_standard=scaled_standard,
        label_encoded=label_encoded,
        one_hot=one_hot,
        binned=binned,
        aggregations=aggregations,
        ml_ready=ml_ready,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scale(
    df: pd.DataFrame,
    cols: list[str],
    scaler,
    label: str,
    warnings: list[str],
) -> pd.DataFrame:
    """Apply *scaler* to *cols* and return a DataFrame with the same index."""
    valid_cols = [c for c in cols if c in df.columns]
    if not valid_cols:
        return pd.DataFrame(index=df.index)

    subset = df[valid_cols].copy()
    # Drop rows with NaN for fitting (shouldn't happen after cleaning, but defensive)
    try:
        scaled = scaler.fit_transform(subset.values.astype(float))
    except Exception as exc:
        warnings.append(f"{label} scaling failed: {exc}")
        return pd.DataFrame(index=df.index)

    return pd.DataFrame(scaled, columns=valid_cols, index=df.index)


def _label_encode(
    df: pd.DataFrame,
    cols: list[str],
    warnings: list[str],
) -> pd.DataFrame:
    """Ordinal-encode categorical and boolean columns."""
    valid_cols = [c for c in cols if c in df.columns]
    if not valid_cols:
        return pd.DataFrame(index=df.index)

    result = pd.DataFrame(index=df.index)
    enc = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        encoded_missing_value=-1,
    )
    for col in valid_cols:
        series = df[[col]].astype(str)
        try:
            codes = enc.fit_transform(series).flatten().astype(int)
            result[col] = codes
        except Exception as exc:
            warnings.append(f"Label encoding failed for '{col}': {exc}")

    return result


def _one_hot(
    df: pd.DataFrame,
    cols: list[str],
    warnings: list[str],
) -> pd.DataFrame:
    """One-hot encode categorical and boolean columns."""
    valid_cols = [c for c in cols if c in df.columns]
    if not valid_cols:
        return pd.DataFrame(index=df.index)

    subset = df[valid_cols].astype(str)
    ohe = pd.get_dummies(subset, dtype=int)

    if ohe.shape[1] > ENCODED_MAX_COLUMNS:
        warnings.append(
            f"One-hot encoding would produce {ohe.shape[1]} columns "
            f"(max {ENCODED_MAX_COLUMNS}). Skipped."
        )
        return pd.DataFrame(index=df.index)

    ohe.index = df.index
    return ohe


def _bin(
    df: pd.DataFrame,
    numeric_cols: list[str],
    warnings: list[str],
) -> pd.DataFrame:
    """Quantile-bin each numeric column into 4 quartiles."""
    valid_cols = [c for c in numeric_cols if c in df.columns]
    if not valid_cols:
        return pd.DataFrame(index=df.index)

    result = pd.DataFrame(index=df.index)
    labels = ["Q1 (low)", "Q2", "Q3", "Q4 (high)"]

    for col in valid_cols:
        out_col = f"{col}_bin"
        try:
            result[out_col] = pd.qcut(df[col], q=4, labels=labels, duplicates="drop")
        except Exception:
            try:
                gen_labels = ["Low", "Mid-Low", "Mid-High", "High"]
                result[out_col] = pd.cut(df[col], bins=4, labels=gen_labels)
            except Exception as exc:
                warnings.append(f"Binning failed for '{col}': {exc}")

    return result


def _aggregate(
    df: pd.DataFrame,
    profile: DatasetProfile,
    numeric_cols: list[str],
    warnings: list[str],
) -> dict[str, pd.DataFrame]:
    """Group by up to 2 low-cardinality categorical columns, agg 3 numeric cols."""
    cat_profiles = [
        c for c in profile.columns
        if c.kind == ColumnKind.CATEGORICAL and c.n_unique >= 2 and c.name in df.columns
    ]
    # Sort by cardinality ascending, then by column order
    cat_profiles_sorted = sorted(cat_profiles, key=lambda c: c.n_unique)[:2]

    valid_numeric = [c for c in numeric_cols[:3] if c in df.columns]
    agg_dict: dict[str, pd.DataFrame] = {}

    for cp in cat_profiles_sorted:
        cat_col = cp.name
        if not valid_numeric:
            break
        try:
            grouped = (
                df.groupby(cat_col)[valid_numeric]
                .agg(["mean", "sum", "min", "max", "count"])
            )
            # Flatten multi-level columns
            grouped.columns = [f"{col}_{stat}" for col, stat in grouped.columns]
            grouped = grouped.reset_index()
            agg_dict[f"by_{cat_col}"] = grouped
        except Exception as exc:
            warnings.append(f"Aggregation by '{cat_col}' failed: {exc}")

    return agg_dict


def _ml_ready(
    scaled_standard: pd.DataFrame,
    one_hot: pd.DataFrame,
) -> pd.DataFrame:
    """Concatenate scaled numeric and one-hot encoded data."""
    parts = [df for df in [scaled_standard, one_hot] if not df.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, axis=1)

