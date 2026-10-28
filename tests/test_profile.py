"""tests/test_profile.py"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import ColumnKind
from src.profile import classify_column, profile


def test_classify_numeric():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert classify_column(s) == ColumnKind.NUMERIC


def test_classify_categorical():
    s = pd.Series(["East", "West", "North", "South"] * 5)
    assert classify_column(s) == ColumnKind.CATEGORICAL


def test_classify_datetime():
    s = pd.to_datetime(pd.Series(["2021-01-01", "2021-01-02", "2021-01-03"]))
    assert classify_column(s) == ColumnKind.DATETIME


def test_classify_boolean():
    s = pd.Series([True, False, True, True, False])
    assert classify_column(s) == ColumnKind.BOOLEAN


def test_classify_constant():
    s = pd.Series([42, 42, 42, 42])
    assert classify_column(s) == ColumnKind.CONSTANT


def test_classify_id_like():
    # Integer with high unique ratio
    s = pd.Series(range(100))
    assert classify_column(s) == ColumnKind.ID_LIKE


def test_classify_text():
    # Average string length > TEXT_MIN_AVG_LEN (30)
    long_text = "This is a very long piece of text that exceeds the threshold for classification."
    s = pd.Series([long_text] * 5 + [long_text + " extra"] * 5)
    assert classify_column(s) == ColumnKind.TEXT


def test_primary_date_col_selected():
    df = pd.DataFrame({
        "date1": pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-03"]),
        "date2": pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-01"]),  # less unique
        "value": [1.0, 2.0, 3.0],
    })
    p = profile(df)
    # date1 has more unique values
    assert p.primary_date_col == "date1"


def test_profile_all_column_kinds():
    df = pd.DataFrame({
        "num": [1.0, 2.0, 3.0, 4.0, 5.0],
        "cat": ["A", "B", "A", "B", "A"],
        "dt": pd.to_datetime(["2021-01-01", "2021-01-02", "2021-01-03",
                               "2021-01-04", "2021-01-05"]),
        "const": [1, 1, 1, 1, 1],
    })
    p = profile(df)
    kinds = {col.name: col.kind for col in p.columns}
    assert kinds["num"] == ColumnKind.NUMERIC
    assert kinds["cat"] == ColumnKind.CATEGORICAL
    assert kinds["dt"] == ColumnKind.DATETIME
    assert kinds["const"] == ColumnKind.CONSTANT

