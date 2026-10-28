"""
src/utils.py — Logging, string helpers, safe type parsers, and sha256.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata

import pandas as pd

from src.config import LOG_LEVEL

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_logging_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a standard-library logger configured with LOG_LEVEL.

    The root handler is added only once; subsequent calls re-use it.
    """
    global _logging_configured
    if not _logging_configured:
        logging.basicConfig(
            level=LOG_LEVEL,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        _logging_configured = True
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

_SNAKE_RE = re.compile(r"[^a-z0-9]+")


def to_snake_case(name: str) -> str:
    """Convert a column name to lowercase snake_case.

    Strips accents, replaces any run of non-alphanumeric characters with
    an underscore, and strips leading/trailing underscores.
    """
    # Normalise unicode (strip accents)
    norm = unicodedata.normalize("NFKD", str(name))
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")
    lower = ascii_name.lower()
    snake = _SNAKE_RE.sub("_", lower).strip("_")
    return snake or "col"


def unique_names(names: list[str]) -> list[str]:
    """Deduplicate a list of names by appending _2, _3, … suffixes.

    The first occurrence is kept as-is; duplicates get incrementing suffixes.
    """
    seen: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            candidate = f"{name}_{seen[name]}"
            # Edge case: the candidate itself might already exist
            while candidate in seen:
                seen[name] += 1
                candidate = f"{name}_{seen[name]}"
            seen[candidate] = 1
            result.append(candidate)
    return result


# ---------------------------------------------------------------------------
# Safe type parsers
# ---------------------------------------------------------------------------

_CURRENCY_STRIP = re.compile(r"[$€£¥₹,\s%]+")


def try_parse_numeric(series: pd.Series) -> pd.Series:
    """Attempt to convert a Series to numeric.

    Strips currency symbols, commas, percent signs and whitespace before
    calling ``pd.to_numeric(errors='coerce')``.

    Returns the converted Series (NaN where conversion failed).
    """
    cleaned = series.astype(str).str.strip()
    cleaned = cleaned.str.replace(_CURRENCY_STRIP, "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def try_parse_datetime(series: pd.Series) -> pd.Series:
    """Attempt to convert a Series to datetime.

    Returns the converted Series (NaT where conversion failed).
    """
    return pd.to_datetime(series, errors="coerce")


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()

