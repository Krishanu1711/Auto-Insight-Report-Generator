"""tests/test_pipeline_e2e.py — End-to-end pipeline tests using sample data."""
from __future__ import annotations

import json

import pytest

from src.models import PipelineConfig
from src.pipeline import run_pipeline, rerun_forecast


# ---------------------------------------------------------------------------
# CSV path
# ---------------------------------------------------------------------------

def _make_csv() -> bytes:
    return (
        b"order_id,order_date,region,sales,quantity,profit\n"
        b"1,2021-01-01,East,$100.00,2,20.0\n"
        b"2,2021-01-15,West,200,3,50.0\n"
        b"3,2021-02-01,East,150,1,30.0\n"
        b"4,2021-02-15,North,N/A,2,10.0\n"
        b"5,2021-03-01,South,300,4,80.0\n"
        b"6,2021-03-15,East,250,3,60.0\n"
        b"7,2021-04-01,West,180,2,40.0\n"
        b"8,2021-04-15,North,220,3,55.0\n"
        b"9,2021-05-01,East,175,1,35.0\n"
        b"10,2021-05-15,South,310,5,90.0\n"
    )


def test_pipeline_csv_basic():
    content = _make_csv()
    bundle = run_pipeline("orders.csv", content, PipelineConfig(auto_forecast=False))
    assert bundle.source.filename == "orders.csv"
    assert bundle.clean.df.shape[0] > 0
    assert bundle.profile is not None
    assert len(bundle.charts) > 0


def test_pipeline_produces_insights():
    content = _make_csv()
    bundle = run_pipeline("orders.csv", content, PipelineConfig(auto_forecast=False))
    # Insights list should exist (may be empty for clean data)
    assert isinstance(bundle.insights, list)


def test_pipeline_unstructured_txt():
    content = b"Hello world this is feedback.\nAnother review about the product.\nFurther comments here.\n"
    bundle = run_pipeline("feedback.txt", content, PipelineConfig())
    assert bundle.source.is_unstructured
    assert bundle.transform is None
    assert bundle.forecast is None
    assert len(bundle.charts) > 0  # text chart


def test_pipeline_json():
    data = [
        {"name": "Alice", "score": 95, "date": "2021-01-01"},
        {"name": "Bob", "score": 87, "date": "2021-02-01"},
        {"name": "Carol", "score": 92, "date": "2021-03-01"},
    ]
    content = json.dumps(data).encode()
    bundle = run_pipeline("scores.json", content, PipelineConfig(auto_forecast=False))
    assert bundle.clean.df.shape[0] == 3


def test_pipeline_xml():
    xml = b"""<orders>
    <order><id>1</id><sales>100</sales><date>2021-01-01</date></order>
    <order><id>2</id><sales>200</sales><date>2021-02-01</date></order>
    </orders>"""
    bundle = run_pipeline("data.xml", xml, PipelineConfig(auto_forecast=False))
    assert bundle.clean.df.shape[0] == 2


def test_pipeline_error_unsupported_format():
    from src.exceptions import UnsupportedFormatError
    with pytest.raises(UnsupportedFormatError):
        run_pipeline("data.xlsx", b"content", PipelineConfig())


def test_pipeline_progress_callback():
    content = _make_csv()
    progress_calls = []

    def track(label: str, frac: float):
        progress_calls.append((label, frac))

    run_pipeline("orders.csv", content, PipelineConfig(auto_forecast=False), progress=track)
    assert len(progress_calls) > 0
    # Last call should be "Done" at 1.0
    assert progress_calls[-1][1] == 1.0

