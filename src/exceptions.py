"""
src/exceptions.py — InsightError hierarchy.
Every public exception carries a user_message that is safe to display in the UI.
"""
from __future__ import annotations


class InsightError(Exception):
    """Base class. ``user_message`` is safe to show in the UI."""

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.user_message} ({self.detail})"
        return self.user_message


class UnsupportedFormatError(InsightError):
    """Raised when the uploaded file extension is not in SUPPORTED_EXTENSIONS."""


class IngestError(InsightError):
    """Raised when the file cannot be parsed into a tabular structure."""


class EmptyDatasetError(InsightError):
    """Raised when the resulting DataFrame has 0 rows or 0 columns."""


class CleaningError(InsightError):
    """Raised when a cleaning step encounters an unrecoverable problem."""


class ForecastError(InsightError):
    """Raised when time-series forecasting cannot proceed."""


class ReportError(InsightError):
    """Raised when Jinja2 rendering fails."""


class StorageError(InsightError):
    """Raised when a database operation fails; the transaction is rolled back."""

