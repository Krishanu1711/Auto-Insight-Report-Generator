"""
src/models.py — All shared enums and dataclasses.
Types only; no application logic here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import pandas as pd
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SourceFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
    XML = "xml"
    TXT = "txt"


class ColumnKind(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TEXT = "text"
    HIGH_CARDINALITY = "high_cardinality"
    ID_LIKE = "id_like"
    CONSTANT = "constant"


class OutlierTreatment(str, Enum):
    FLAG = "flag"
    CAP = "cap"
    REMOVE = "remove"


class CleaningStep(str, Enum):
    RENAME_COLUMNS = "rename_columns"
    TRIM_TEXT = "trim_text"
    NA_TOKENS = "na_tokens"
    COERCE_NUMERIC = "coerce_numeric"
    COERCE_DATETIME = "coerce_datetime"
    DROP_EMPTY_ROWS = "drop_empty_rows"
    DROP_DUPLICATES = "drop_duplicates"
    DROP_COLUMN = "drop_column"
    IMPUTE = "impute"
    HARMONIZE_CATEGORY = "harmonize_category"
    OUTLIERS = "outliers"


class ChartKind(str, Enum):
    HISTOGRAM = "histogram"
    BOX = "box"
    BAR = "bar"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    LINE = "line"
    DECOMPOSITION = "decomposition"
    FORECAST = "forecast"


class ChartGroup(str, Enum):
    DISTRIBUTION = "distribution"
    CATEGORY = "category"
    RELATIONSHIP = "relationship"
    TEXT = "text"
    TIME_SERIES = "time_series"


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CleaningConfig:
    """Parameters controlling the cleaning stage."""
    outlier_treatment: OutlierTreatment = OutlierTreatment.FLAG
    drop_column_missing_pct: float = 0.60   # drop columns missing more than this share
    iqr_k: float = 1.5


@dataclass
class PipelineConfig:
    """Top-level pipeline configuration."""
    cleaning: CleaningConfig = field(default_factory=CleaningConfig)
    auto_forecast: bool = True


@dataclass
class ForecastParams:
    """Parameters for a forecast run."""
    date_col: str
    target_col: str
    agg: str = "sum"                            # "sum" or "mean"
    horizon: int = 3                            # 1 .. MAX_HORIZON
    decomposition_model: str = "additive"       # "additive" or "multiplicative"


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    df: pd.DataFrame
    source_format: SourceFormat
    is_unstructured: bool                       # True only for free-text .txt
    file_sha256: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class SourceInfo:
    """What the AnalysisBundle remembers about the uploaded file."""
    filename: str
    source_format: SourceFormat
    file_sha256: str
    n_rows_raw: int
    n_cols_raw: int
    is_unstructured: bool
    raw_preview: pd.DataFrame                   # first RAW_PREVIEW_ROWS rows of the raw data
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

@dataclass
class CleaningAction:
    step: CleaningStep
    column: str | None
    description: str
    rows_affected: int


@dataclass
class QualityStats:
    n_rows: int
    n_cols: int
    missing_cells: int
    duplicate_rows: int
    outlier_cells: int                          # IQR rule, numeric columns only


@dataclass
class CleanResult:
    df: pd.DataFrame
    actions: list[CleaningAction]
    quality_before: QualityStats
    quality_after: QualityStats
    rename_map: dict[str, str]                  # original name -> cleaned name
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@dataclass
class ColumnProfile:
    name: str
    dtype: str
    kind: ColumnKind
    n_missing: int
    pct_missing: float
    n_unique: int
    unique_ratio: float
    sample_values: list[str]                    # up to 3
    numeric_stats: dict[str, float] | None      # min, max, mean, median, std, skew
    top_values: list[tuple[str, int]] | None    # up to 5; categorical/boolean only
    date_range: tuple[str, str] | None          # ISO strings; datetime only


@dataclass
class DatasetProfile:
    n_rows: int
    n_cols: int
    columns: list[ColumnProfile]
    primary_date_col: str | None
    memory_mb: float

    def cols_of(self, kind: ColumnKind) -> list[str]:
        """Return column names that match the given ColumnKind."""
        return [c.name for c in self.columns if c.kind == kind]


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

@dataclass
class TransformResult:
    scaled_minmax: pd.DataFrame                 # NUMERIC columns, range 0..1
    scaled_standard: pd.DataFrame               # NUMERIC columns, mean 0, std 1
    label_encoded: pd.DataFrame                 # CATEGORICAL + BOOLEAN, integer codes
    one_hot: pd.DataFrame                       # CATEGORICAL + BOOLEAN, 0/1 columns
    binned: pd.DataFrame                        # one "<col>_bin" column per NUMERIC column
    aggregations: dict[str, pd.DataFrame]       # key "by_<categorical>", max 2 entries
    ml_ready: pd.DataFrame                      # scaled_standard + one_hot, side by side
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

@dataclass
class CorrPair:
    x: str
    y: str
    r: float


@dataclass
class RegressionResult:
    x: str
    y: str
    coef: float
    intercept: float
    r2: float
    mae: float
    rmse: float
    n_train: int
    n_test: int
    y_test: list[float]
    y_pred: list[float]


@dataclass
class TextSummary:
    n_lines: int
    n_words: int
    avg_words_per_line: float
    top_words: list[tuple[str, int]]            # top TOP_WORDS_N, stop words removed


@dataclass
class AnalysisResult:
    descriptive: pd.DataFrame | None            # one row per NUMERIC column
    correlation: pd.DataFrame | None            # Pearson matrix or None if < 2 numeric cols
    top_pairs: list[CorrPair]                   # sorted by abs(r), desc
    regression: RegressionResult | None
    text_summary: TextSummary | None            # only for unstructured input
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

@dataclass
class ChartSpec:
    id: str                                     # unique, e.g. "hist__sales"
    title: str
    kind: ChartKind
    group: ChartGroup
    columns: list[str]
    figure: go.Figure
    description: str                            # one plain-language line


# ---------------------------------------------------------------------------
# Forecast
# ---------------------------------------------------------------------------

@dataclass
class DecompositionResult:
    model: str
    observed: pd.Series
    trend: pd.Series
    seasonal: pd.Series
    resid: pd.Series
    period: int


@dataclass
class BacktestResult:
    actual: pd.Series
    predicted: pd.Series
    mae: float
    rmse: float
    mape: float | None                          # None if actual contains zeros only


@dataclass
class ForecastResult:
    params: ForecastParams
    freq: str                                   # "D", "W" or "MS"
    seasonal_period: int
    series: pd.Series                           # resampled target series (DatetimeIndex)
    sma: pd.Series
    ema: pd.Series
    sma_window: int
    ema_span: int
    decomposition: DecompositionResult | None
    adf_pvalue: float
    order: tuple[int, int, int]                 # (p, d, q)
    aic: float
    backtest: BacktestResult | None
    forecast: pd.DataFrame                      # index = future dates; cols: forecast, lower, upper
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

@dataclass
class Insight:
    level: str                                  # "info" or "warning"
    category: str                               # "quality","distribution","relationship","regression","timeseries"
    text: str


# ---------------------------------------------------------------------------
# Bundle — the single object the UI holds in session state
# ---------------------------------------------------------------------------

@dataclass
class AnalysisBundle:
    source: SourceInfo
    clean: CleanResult
    profile: DatasetProfile
    transform: TransformResult | None           # None for unstructured input
    analysis: AnalysisResult
    charts: list[ChartSpec]
    forecast: ForecastResult | None
    forecast_charts: list[ChartSpec]
    forecast_error: str | None                  # user-readable reason if forecast failed/skipped
    insights: list[Insight]
    config: PipelineConfig
    created_at: datetime


# ---------------------------------------------------------------------------
# Persistence listing
# ---------------------------------------------------------------------------

@dataclass
class DatasetRecord:
    id: int
    name: str
    original_filename: str
    source_format: str
    n_rows_clean: int
    n_cols_clean: int
    created_at: datetime

