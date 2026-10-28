"""tests/test_ingest.py"""
from __future__ import annotations

import json
import pytest

from src.ingest import load
from src.exceptions import EmptyDatasetError, IngestError, UnsupportedFormatError
from src.models import SourceFormat


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def test_csv_basic():
    content = b"name,age,city\nAlice,30,London\nBob,25,Paris\n"
    result = load("data.csv", content)
    assert result.source_format == SourceFormat.CSV
    assert result.df.shape == (2, 3)
    assert not result.is_unstructured


def test_csv_with_dollar_sign():
    content = b"item,price\nApple,$1.50\nBanana,$0.75\n"
    result = load("prices.csv", content)
    assert result.df.shape == (2, 2)


def test_csv_latin1():
    content = "name,value\ncafé,1\n".encode("latin-1")
    result = load("data.csv", content)
    assert len(result.warnings) > 0   # latin-1 warning


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def test_json_list_of_objects():
    data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    content = json.dumps(data).encode()
    result = load("data.json", content)
    assert result.df.shape == (2, 2)


def test_json_dict_of_lists():
    data = {"x": [1, 2, 3], "y": [4, 5, 6]}
    content = json.dumps(data).encode()
    result = load("data.json", content)
    assert result.df.shape == (3, 2)


def test_json_dict_with_one_list():
    data = {"records": [{"a": 1}, {"a": 2}]}
    content = json.dumps(data).encode()
    result = load("data.json", content)
    assert result.df.shape == (2, 1)


def test_json_non_tabular():
    content = json.dumps({"nested": {"key": "value"}}).encode()
    with pytest.raises(IngestError):
        load("data.json", content)


# ---------------------------------------------------------------------------
# XML
# ---------------------------------------------------------------------------

def test_xml_basic():
    xml = b"""<root><item><name>A</name><val>1</val></item><item><name>B</name><val>2</val></item></root>"""
    result = load("data.xml", xml)
    assert result.df.shape[0] == 2
    assert "name" in result.df.columns


def test_xml_malicious_entity():
    """defusedxml should reject entity expansion attacks."""
    evil = b"""<?xml version="1.0"?>
<!DOCTYPE evil [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root><item>&xxe;</item></root>"""
    with pytest.raises(Exception):
        load("data.xml", evil)


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------

def test_txt_tabular():
    content = b"col1\tcol2\tcol3\n1\t2\t3\n4\t5\t6\n"
    result = load("data.txt", content)
    assert not result.is_unstructured
    assert result.df.shape == (2, 3)


def test_txt_unstructured():
    content = b"Hello world this is a test.\nAnother line of text here.\n"
    result = load("feedback.txt", content)
    assert result.is_unstructured
    assert "text" in result.df.columns


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

def test_unsupported_extension():
    with pytest.raises(UnsupportedFormatError):
        load("data.xlsx", b"content")


def test_empty_csv():
    with pytest.raises(EmptyDatasetError):
        load("empty.csv", b"col1,col2\n")


def test_file_too_large():
    from src.config import MAX_UPLOAD_MB
    big = b"a,b\n" + b"1,2\n" * 1000
    # Patch the config temporarily
    import src.config as cfg
    old = cfg.MAX_UPLOAD_MB
    cfg.MAX_UPLOAD_MB = 0
    try:
        with pytest.raises(IngestError):
            load("data.csv", big)
    finally:
        cfg.MAX_UPLOAD_MB = old


# ---------------------------------------------------------------------------
# Phase 10: URL Ingestion
# ---------------------------------------------------------------------------

def test_load_from_url_invalid_scheme():
    from src.ingest import load_from_url
    with pytest.raises(IngestError, match="Only HTTP and HTTPS"):
        load_from_url("ftp://example.com/data.json")


def test_load_from_url_mocked(monkeypatch):
    from src.ingest import load_from_url

    class DummyResponse:
        headers = {"Content-Length": "100"}
        def raise_for_status(self): pass
        def iter_content(self, chunk_size=8192):
            yield json.dumps([{"id": 1, "val": 10}, {"id": 2, "val": 20}]).encode()

    import requests
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: DummyResponse())

    res = load_from_url("https://api.example.com/items")
    assert res.df.shape == (2, 2)


