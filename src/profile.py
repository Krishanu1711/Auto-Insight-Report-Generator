"""
src/profile.py — Column-type classification and per-column statistics.

Public API
----------
classify_column(s)  -> ColumnKind
profile(df)         -> DatasetProfile
"""
from __future__ import annotations

import pandas as pd

from src.config import (
    CATEGORICAL_MAX_UNIQUE,
    ID_UNIQUE_RATIO,
    TEXT_MIN_AVG_LEN,
)
from src.models import ColumnKind, ColumnProfile, DatasetProfile
from src.utils import get_logger

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Column classification
# ---------------------------------------------------------------------------

def classify_column(s: pd.Series) -> ColumnKind:
    """Classify *s* into a :class:`ColumnKind`.

    Rules are applied in order; the first match wins.
    ``n_unique`` and ``unique_ratio`` are computed on non-null values.
    """
    non_null = s.dropna()
    n_unique = int(non_null.nunique())
    total_non_null = len(non_null)
    unique_ratio = n_unique / total_non_null if total_non_null > 0 else 0.0

    # Rule 1: constant (including all-null)
    if n_unique <= 1:
        return ColumnKind.CONSTANT

    # Rule 2: datetime dtype
    if pd.api.types.is_datetime64_any_dtype(s):
        return ColumnKind.DATETIME

    # Rule 3: bool dtype
    if pd.api.types.is_bool_dtype(s):
        return ColumnKind.BOOLEAN

    # Rule 4: integer dtype with high unique ratio → id-like
    if pd.api.types.is_integer_dtype(s) and unique_ratio >= ID_UNIQUE_RATIO:
        return ColumnKind.ID_LIKE

    # Rule 5: any other numeric dtype
    if pd.api.types.is_numeric_dtype(s):
        return ColumnKind.NUMERIC

    # From here: object / string / category
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s) or hasattr(s, "cat"):
        # Rule 6: long average string → text
        avg_len = non_null.astype(str).str.len().mean() if total_non_null > 0 else 0.0
        if avg_len >= TEXT_MIN_AVG_LEN:
            return ColumnKind.TEXT

        # Rule 7: high unique ratio → id-like
        if unique_ratio >= ID_UNIQUE_RATIO:
            return ColumnKind.ID_LIKE

        # Rule 8: low cardinality → categorical
        if n_unique <= CATEGORICAL_MAX_UNIQUE:
            return ColumnKind.CATEGORICAL

        # Rule 9: high cardinality
        return ColumnKind.HIGH_CARDINALITY

    # Fallback
    return ColumnKind.HIGH_CARDINALITY


# ---------------------------------------------------------------------------
# Dataset profile
# ---------------------------------------------------------------------------

def profile(df: pd.DataFrame) -> DatasetProfile:
    """Compute a :class:`DatasetProfile` for the cleaned DataFrame *df*.

    This must run *after* cleaning so column dtypes are correct.
    """
    _log.info("Profiling %d rows × %d cols", len(df), df.shape[1])

    columns: list[ColumnProfile] = []
    n_rows = len(df)

    for col in df.columns:
        s = df[col]
        col_profile = _profile_column(s, n_rows)
        columns.append(col_profile)

    # Primary date column: the DATETIME column with the most unique values
    date_cols = [(c.name, c.n_unique) for c in columns if c.kind == ColumnKind.DATETIME]
    if date_cols:
        primary_date_col = max(date_cols, key=lambda x: x[1])[0]
    else:
        primary_date_col = None

    memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)

    _log.info("Profile complete. Primary date col: %s", primary_date_col)

    return DatasetProfile(
        n_rows=n_rows,
        n_cols=len(columns),
        columns=columns,
        primary_date_col=primary_date_col,
        memory_mb=round(memory_mb, 4),
    )


def _profile_column(s: pd.Series, n_rows: int) -> ColumnProfile:
    """Build a :class:`ColumnProfile` for a single Series."""
    kind = classify_column(s)
    non_null = s.dropna()
    n_missing = int(s.isna().sum())
    pct_missing = n_missing / n_rows if n_rows > 0 else 0.0
    n_unique = int(non_null.nunique())
    unique_ratio = n_unique / len(non_null) if len(non_null) > 0 else 0.0

    # Sample values: up to 3 non-null unique values
    sample_values = [str(v) for v in non_null.unique()[:3]]

    # Numeric stats
    numeric_stats: dict[str, float] | None = None
    if kind == ColumnKind.NUMERIC and len(non_null) > 0:
        numeric_stats = {
            "min": float(non_null.min()),
            "max": float(non_null.max()),
            "mean": float(non_null.mean()),
            "median": float(non_null.median()),
            "std": float(non_null.std()),
            "skew": float(non_null.skew()),
        }

    # Top values (categorical / boolean)
    top_values: list[tuple[str, int]] | None = None
    if kind in (ColumnKind.CATEGORICAL, ColumnKind.BOOLEAN):
        vc = s.value_counts().head(5)
        top_values = [(str(k), int(v)) for k, v in vc.items()]

    # Date range
    date_range: tuple[str, str] | None = None
    if kind == ColumnKind.DATETIME and len(non_null) > 0:
        date_range = (
            str(non_null.min().isoformat()),
            str(non_null.max().isoformat()),
        )

    return ColumnProfile(
        name=s.name,
        dtype=str(s.dtype),
        kind=kind,
        n_missing=n_missing,
        pct_missing=round(pct_missing, 4),
        n_unique=n_unique,
        unique_ratio=round(unique_ratio, 4),
        sample_values=sample_values,
        numeric_stats=numeric_stats,
        top_values=top_values,
        date_range=date_range,
    )

