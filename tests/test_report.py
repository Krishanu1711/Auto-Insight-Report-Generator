"""tests/test_report.py"""
from __future__ import annotations

import pytest

from src.report import build_report


def test_report_returns_bytes(sample_bundle):
    html_bytes = build_report(sample_bundle)
    assert isinstance(html_bytes, bytes)
    assert len(html_bytes) > 1000


def test_report_contains_html_structure(sample_bundle):
    html = build_report(sample_bundle).decode("utf-8")
    assert "<!DOCTYPE html>" in html
    assert "<title>" in html
    assert "</html>" in html


def test_report_contains_plotlyjs(sample_bundle):
    html = build_report(sample_bundle).decode("utf-8")
    # Plotly JS should be inlined
    assert "plotly" in html.lower()


def test_report_escapes_html_in_column_names(sample_bundle):
    """Column names containing HTML must be escaped."""
    import pandas as pd
    from src.models import ColumnKind, ColumnProfile
    # Inject a malicious column name
    evil_profile = ColumnProfile(
        name="<script>alert('xss')</script>",
        dtype="float64", kind=ColumnKind.NUMERIC,
        n_missing=0, pct_missing=0.0, n_unique=5, unique_ratio=1.0,
        sample_values=["1"], numeric_stats=None, top_values=None, date_range=None,
    )
    import dataclasses
    new_profile = dataclasses.replace(
        sample_bundle.profile,
        columns=[evil_profile],
    )
    new_bundle = dataclasses.replace(sample_bundle, profile=new_profile)
    html = build_report(new_bundle).decode("utf-8")
    # The raw script tag must NOT appear unescaped in the HTML
    assert "<script>alert('xss')</script>" not in html


def test_report_works_without_forecast(sample_bundle):
    """Report must build even when bundle.forecast is None."""
    html_bytes = build_report(sample_bundle)
    assert len(html_bytes) > 0


def test_report_works_with_transform_none(sample_bundle):
    import dataclasses
    no_transform_bundle = dataclasses.replace(sample_bundle, transform=None)
    html_bytes = build_report(no_transform_bundle)
    assert len(html_bytes) > 0

