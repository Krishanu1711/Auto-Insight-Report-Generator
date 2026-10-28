"""
src/clean.py — Ordered cleaning pipeline with a full change log.

Public API
----------
clean(df, config, is_unstructured) -> CleanResult
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.config import (
    CATEGORICAL_MAX_UNIQUE,
    NA_TOKENS,
    NUMERIC_PARSE_MIN_RATIO,
    DATETIME_PARSE_MIN_RATIO,
)
from src.exceptions import EmptyDatasetError
from src.models import (
    CleaningAction,
    CleaningConfig,
    CleaningStep,
    CleanResult,
    OutlierTreatment,
    QualityStats,
)
from src.utils import get_logger, to_snake_case, try_parse_datetime, try_parse_numeric, unique_names

_log = get_logger(__name__)

_CURRENCY_STRIP = re.compile(r"[$€£¥₹,%\s]+")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def clean(
    df: pd.DataFrame,
    config: CleaningConfig,
    is_unstructured: bool = False,
) -> CleanResult:
    """Apply the ordered cleaning pipeline to *df* and return a :class:`CleanResult`.

    The input DataFrame is never mutated; all work is done on a copy.

    For unstructured text (``is_unstructured=True``) only steps 1, 2 and
    drop-empty-rows are applied.
    """
    _log.info("Starting cleaning (%d rows × %d cols, unstructured=%s)",
              len(df), df.shape[1], is_unstructured)

    df = df.copy()
    actions: list[CleaningAction] = []
    rename_map: dict[str, str] = {}

    # --- Step 1: Rename columns to snake_case ---
    df, rename_map = _step_rename(df, actions)

    # --- Step 2: Trim text and replace NA tokens ---
    df = _step_trim_and_na(df, actions)

    if is_unstructured:
        # Reduced path: only drop empty rows
        before_rows = len(df)
        df = df.dropna(how="all").reset_index(drop=True)
        dropped = before_rows - len(df)
        if dropped:
            actions.append(CleaningAction(
                step=CleaningStep.DROP_EMPTY_ROWS,
                column=None,
                description=f"Dropped {dropped} fully-empty row(s).",
                rows_affected=dropped,
            ))
        quality_before = _quality_stats(df)
        quality_after = _quality_stats(df)
        _check_not_empty(df)
        return CleanResult(
            df=df,
            actions=actions,
            quality_before=quality_before,
            quality_after=quality_after,
            rename_map=rename_map,
        )

    # --- Step 3: Coerce numeric and datetime types ---
    df = _step_coerce(df, actions)

    # --- Snapshot quality_before (after type coercion) ---
    quality_before = _quality_stats(df)

    # --- Step 4: Drop empty rows and exact duplicates ---
    df = _step_drop_empty_rows(df, actions)
    df = _step_drop_duplicates(df, actions)

    # --- Step 5: Drop columns over the missing threshold ---
    df = _step_drop_columns(df, config, actions)

    # --- Step 6: Impute missing values ---
    df = _step_impute(df, actions)

    # --- Step 7: Harmonize category spelling ---
    df = _step_harmonize(df, actions)

    # --- Step 8: Outlier treatment ---
    df = _step_outliers(df, config, actions)

    # --- Snapshot quality_after ---
    quality_after = _quality_stats(df)

    _check_not_empty(df)

    _log.info(
        "Cleaning complete: %d rows × %d cols, %d actions",
        len(df), df.shape[1], len(actions),
    )

    return CleanResult(
        df=df,
        actions=actions,
        quality_before=quality_before,
        quality_after=quality_after,
        rename_map=rename_map,
    )


# ---------------------------------------------------------------------------
# Individual steps
# ---------------------------------------------------------------------------

def _step_rename(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Step 1: Rename all columns to snake_case, deduplicating conflicts."""
    original_names = list(df.columns)
    snake_names = [to_snake_case(n) for n in original_names]
    unique_snake = unique_names(snake_names)

    rename_map = {
        orig: new
        for orig, new in zip(original_names, unique_snake)
        if orig != new
    }
    if rename_map:
        df = df.rename(columns=dict(zip(original_names, unique_snake)))
        actions.append(CleaningAction(
            step=CleaningStep.RENAME_COLUMNS,
            column=None,
            description=f"Renamed {len(rename_map)} column(s) to snake_case.",
            rows_affected=0,
        ))
    full_map = dict(zip(original_names, unique_snake))
    return df, full_map


def _step_trim_and_na(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 2: Strip whitespace and replace NA token strings with NaN."""
    obj_cols = df.select_dtypes(include="object").columns.tolist()
    if not obj_cols:
        return df

    # Trim whitespace and collapse internal runs
    df[obj_cols] = df[obj_cols].apply(
        lambda s: s.str.strip().str.replace(r"\s+", " ", regex=True)
        if s.dtype == object else s
    )

    # Replace NA token strings
    na_replaced = 0
    for col in obj_cols:
        mask = df[col].str.lower().isin(NA_TOKENS)
        count = int(mask.sum())
        if count:
            df.loc[mask, col] = np.nan
            na_replaced += count

    if na_replaced:
        actions.append(CleaningAction(
            step=CleaningStep.NA_TOKENS,
            column=None,
            description=f"Replaced {na_replaced} NA-token value(s) with NaN.",
            rows_affected=na_replaced,
        ))
    else:
        actions.append(CleaningAction(
            step=CleaningStep.TRIM_TEXT,
            column=None,
            description="Trimmed whitespace in text columns.",
            rows_affected=0,
        ))
    return df


def _step_coerce(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 3: Try to coerce object columns to numeric or datetime."""
    obj_cols = df.select_dtypes(include="object").columns.tolist()

    for col in obj_cols:
        series = df[col]
        non_null = series.dropna()
        if len(non_null) == 0:
            continue

        # Try numeric first
        numeric_parsed = try_parse_numeric(non_null)
        numeric_ratio = numeric_parsed.notna().sum() / len(non_null)
        if numeric_ratio >= NUMERIC_PARSE_MIN_RATIO:
            df[col] = try_parse_numeric(series)
            actions.append(CleaningAction(
                step=CleaningStep.COERCE_NUMERIC,
                column=col,
                description=(
                    f"Converted '{col}' to numeric "
                    f"({numeric_ratio:.0%} of values parsed successfully)."
                ),
                rows_affected=0,
            ))
            continue

        # Skip datetime coercion if already numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            continue

        # Try datetime
        dt_parsed = try_parse_datetime(non_null)
        dt_ratio = dt_parsed.notna().sum() / len(non_null)
        if dt_ratio >= DATETIME_PARSE_MIN_RATIO:
            df[col] = try_parse_datetime(series)
            actions.append(CleaningAction(
                step=CleaningStep.COERCE_DATETIME,
                column=col,
                description=(
                    f"Converted '{col}' to datetime "
                    f"({dt_ratio:.0%} of values parsed successfully)."
                ),
                rows_affected=0,
            ))

    return df


def _step_drop_empty_rows(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 4a: Drop rows where every cell is null."""
    before = len(df)
    df = df.dropna(how="all")
    dropped = before - len(df)
    if dropped:
        df = df.reset_index(drop=True)
        actions.append(CleaningAction(
            step=CleaningStep.DROP_EMPTY_ROWS,
            column=None,
            description=f"Dropped {dropped} fully-empty row(s).",
            rows_affected=dropped,
        ))
    return df


def _step_drop_duplicates(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 4b: Drop exact duplicate rows (keep first)."""
    before = len(df)
    df = df.drop_duplicates(keep="first")
    dropped = before - len(df)
    if dropped:
        df = df.reset_index(drop=True)
        actions.append(CleaningAction(
            step=CleaningStep.DROP_DUPLICATES,
            column=None,
            description=f"Removed {dropped} exact duplicate row(s).",
            rows_affected=dropped,
        ))
    return df


def _step_drop_columns(
    df: pd.DataFrame,
    config: CleaningConfig,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 5: Drop columns whose missing share exceeds the threshold."""
    threshold = config.drop_column_missing_pct
    n_rows = len(df)
    if n_rows == 0:
        return df

    to_drop: list[str] = []
    for col in df.columns:
        missing_ratio = df[col].isna().sum() / n_rows
        if missing_ratio > threshold:
            to_drop.append(col)

    if to_drop:
        df = df.drop(columns=to_drop)
        actions.append(CleaningAction(
            step=CleaningStep.DROP_COLUMN,
            column=None,
            description=(
                f"Dropped {len(to_drop)} column(s) with >{threshold:.0%} missing values: "
                f"{', '.join(to_drop)}."
            ),
            rows_affected=0,
        ))
    return df


def _step_impute(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 6: Impute missing values (median for numeric, 'Unknown' for object/bool)."""
    for col in df.columns:
        n_missing = int(df[col].isna().sum())
        if n_missing == 0:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            actions.append(CleaningAction(
                step=CleaningStep.IMPUTE,
                column=col,
                description=f"Filled {n_missing} missing value(s) in '{col}' with median ({median_val:.4g}).",
                rows_affected=n_missing,
            ))
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            # Datetime: leave as NaT
            pass
        else:
            df[col] = df[col].fillna("Unknown")
            actions.append(CleaningAction(
                step=CleaningStep.IMPUTE,
                column=col,
                description=f"Filled {n_missing} missing value(s) in '{col}' with 'Unknown'.",
                rows_affected=n_missing,
            ))
    return df


def _step_harmonize(
    df: pd.DataFrame,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 7: Harmonize category spelling (case/whitespace variants)."""
    obj_cols = df.select_dtypes(include="object").columns.tolist()

    for col in obj_cols:
        n_unique = df[col].nunique(dropna=True)
        if n_unique > CATEGORICAL_MAX_UNIQUE:
            continue

        # Group values by their normalised form (lowercase, stripped)
        normalised: dict[str, list[str]] = {}
        for val in df[col].dropna().unique():
            key = str(val).lower().strip()
            normalised.setdefault(key, []).append(str(val))

        replace_map: dict[str, str] = {}
        for variants in normalised.values():
            if len(variants) <= 1:
                continue
            # Pick the most frequent spelling
            freq = df[col].value_counts()
            canonical = max(variants, key=lambda v: freq.get(v, 0))
            for v in variants:
                if v != canonical:
                    replace_map[v] = canonical

        if replace_map:
            df[col] = df[col].replace(replace_map)
            actions.append(CleaningAction(
                step=CleaningStep.HARMONIZE_CATEGORY,
                column=col,
                description=(
                    f"Harmonized {len(replace_map)} spelling variant(s) in '{col}'."
                ),
                rows_affected=0,
            ))
    return df


def _step_outliers(
    df: pd.DataFrame,
    config: CleaningConfig,
    actions: list[CleaningAction],
) -> pd.DataFrame:
    """Step 8: IQR-based outlier treatment (flag / cap / remove)."""
    k = config.iqr_k
    treatment = config.outlier_treatment
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    for col in numeric_cols:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - k * iqr
        upper = q3 + k * iqr

        outlier_mask = (df[col] < lower) | (df[col] > upper)
        n_outliers = int(outlier_mask.sum())
        if n_outliers == 0:
            continue

        if treatment == OutlierTreatment.FLAG:
            actions.append(CleaningAction(
                step=CleaningStep.OUTLIERS,
                column=col,
                description=f"Flagged {n_outliers} outlier(s) in '{col}' (IQR × {k}, data unchanged).",
                rows_affected=n_outliers,
            ))

        elif treatment == OutlierTreatment.CAP:
            df[col] = df[col].clip(lower=lower, upper=upper)
            actions.append(CleaningAction(
                step=CleaningStep.OUTLIERS,
                column=col,
                description=f"Capped {n_outliers} outlier(s) in '{col}' to [{lower:.4g}, {upper:.4g}].",
                rows_affected=n_outliers,
            ))

        elif treatment == OutlierTreatment.REMOVE:
            before = len(df)
            df = df[~outlier_mask].reset_index(drop=True)
            removed = before - len(df)
            actions.append(CleaningAction(
                step=CleaningStep.OUTLIERS,
                column=col,
                description=f"Removed {removed} row(s) with outliers in '{col}'.",
                rows_affected=removed,
            ))

    return df


# ---------------------------------------------------------------------------
# Helper: quality snapshot
# ---------------------------------------------------------------------------

def _quality_stats(df: pd.DataFrame) -> QualityStats:
    """Compute a :class:`QualityStats` snapshot of *df*."""
    n_rows = len(df)
    n_cols = df.shape[1]
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    # IQR outlier count across all numeric columns
    outlier_cells = 0
    for col in df.select_dtypes(include="number").columns:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_cells += int(((df[col] < lower) | (df[col] > upper)).sum())

    return QualityStats(
        n_rows=n_rows,
        n_cols=n_cols,
        missing_cells=missing_cells,
        duplicate_rows=duplicate_rows,
        outlier_cells=outlier_cells,
    )


def _check_not_empty(df: pd.DataFrame) -> None:
    if df.empty or df.shape[0] == 0 or df.shape[1] == 0:
        raise EmptyDatasetError(
            "After cleaning, no rows or columns remain. "
            "The dataset may be entirely empty or duplicated."
        )

