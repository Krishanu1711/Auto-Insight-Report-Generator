"""
src/config.py — All constants, thresholds and default paths.
No magic numbers allowed in module code; import from here instead.
"""
from __future__ import annotations

import os
import plotly.colors

# ---------------------------------------------------------------------------
# File ingestion
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS: set[str] = {".csv", ".json", ".xml", ".txt"}
MAX_UPLOAD_MB: int = 50
MAX_API_RESPONSE_MB: int = 10
API_TIMEOUT_S: int = 15
RAW_PREVIEW_ROWS: int = 200

# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
NA_TOKENS: set[str] = {"", "na", "n/a", "nan", "null", "none", "-", "--", "?", "#n/a"}
NUMERIC_PARSE_MIN_RATIO: float = 0.95
DATETIME_PARSE_MIN_RATIO: float = 0.90
DROP_COLUMN_MISSING_PCT: float = 0.60
IQR_K: float = 1.5

# ---------------------------------------------------------------------------
# Profiling
# ---------------------------------------------------------------------------
CATEGORICAL_MAX_UNIQUE: int = 20
ID_UNIQUE_RATIO: float = 0.95
TEXT_MIN_AVG_LEN: float = 30.0

# ---------------------------------------------------------------------------
# Charting
# ---------------------------------------------------------------------------
MAX_NUMERIC_CHART_COLS: int = 8
MAX_CATEGORICAL_CHART_COLS: int = 6
MAX_SCATTER_PAIRS: int = 3
TOP_PAIRS_N: int = 5
SCATTER_MIN_ABS_R: float = 0.3
HEATMAP_MAX_COLS: int = 15
CHART_MAX_POINTS: int = 10_000
TOP_N_BAR: int = 15
TOP_WORDS_N: int = 20
ENCODED_MAX_COLUMNS: int = 200

# ---------------------------------------------------------------------------
# Analysis / regression
# ---------------------------------------------------------------------------
REGRESSION_TEST_SIZE: float = 0.2
REGRESSION_MIN_ROWS: int = 30

# ---------------------------------------------------------------------------
# Randomness
# ---------------------------------------------------------------------------
RANDOM_STATE: int = 42

# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------
FORECAST_MIN_POINTS: int = 12
DEFAULT_HORIZON: int = 3
MAX_HORIZON: int = 24
ARIMA_MAX_P: int = 2
ARIMA_MAX_D: int = 2
ARIMA_MAX_Q: int = 2
ADF_ALPHA: float = 0.05
FORECAST_CONF_LEVEL: float = 0.95

# Per-frequency settings: period, SMA window, EMA span
FREQ_SETTINGS: dict[str, dict[str, int]] = {
    "D":  {"period": 7,  "sma_window": 7,  "ema_span": 30},
    "W":  {"period": 52, "sma_window": 4,  "ema_span": 12},
    "MS": {"period": 12, "sma_window": 3,  "ema_span": 6},
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
REPORT_TABLE_MAX_ROWS: int = 50

# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------
PLOTLY_TEMPLATE: str = "plotly_white"
COLOR_SEQUENCE: list[str] = plotly.colors.qualitative.Set2

# ---------------------------------------------------------------------------
# Database / persistence
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("INSIGHT_DB_PATH", "data/insight.db")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.environ.get("INSIGHT_LOG_LEVEL", "INFO")

