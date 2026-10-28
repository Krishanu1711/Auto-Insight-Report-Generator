"""
src/ingest.py — Read CSV, JSON, XML and TXT files into a DataFrame.

Public API
----------
load(filename, content) -> IngestResult
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import defusedxml.ElementTree as ET
import pandas as pd

from src import config
from src.config import NA_TOKENS, RAW_PREVIEW_ROWS, SUPPORTED_EXTENSIONS
from src.exceptions import EmptyDatasetError, IngestError, UnsupportedFormatError
from src.models import IngestResult, SourceFormat
from src.utils import get_logger, sha256_bytes

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load(filename: str, content: bytes) -> IngestResult:
    """Parse *content* (raw file bytes) into an :class:`IngestResult`.

    The format is inferred from the lowercase extension of *filename*.
    Raises :class:`UnsupportedFormatError`, :class:`IngestError`, or
    :class:`EmptyDatasetError` on failure.
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"File type '{ext}' is not supported. "
            f"Please upload one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        )

    size_mb = len(content) / (1024 * 1024)
    if size_mb > config.MAX_UPLOAD_MB:
        raise IngestError(
            f"File is {size_mb:.1f} MB, which exceeds the {config.MAX_UPLOAD_MB} MB limit."
        )

    digest = sha256_bytes(content)
    warnings: list[str] = []

    _log.info("Ingesting '%s' (%s, %.2f MB)", filename, ext, size_mb)

    if ext == ".csv":
        df = _load_csv(content, warnings)
        fmt = SourceFormat.CSV
        is_unstructured = False

    elif ext == ".json":
        df = _load_json(content, warnings)
        fmt = SourceFormat.JSON
        is_unstructured = False

    elif ext == ".xml":
        df = _load_xml(content, warnings)
        fmt = SourceFormat.XML
        is_unstructured = False

    else:  # .txt
        df, is_unstructured = _load_txt(content, warnings)
        fmt = SourceFormat.TXT

    if df.empty or df.shape[0] == 0 or df.shape[1] == 0:
        raise EmptyDatasetError(
            "The file produced an empty table (0 rows or 0 columns). "
            "Please check the file contents."
        )

    _log.info(
        "Ingest complete: %d rows × %d cols, unstructured=%s",
        len(df), df.shape[1], is_unstructured,
    )

    return IngestResult(
        df=df,
        source_format=fmt,
        is_unstructured=is_unstructured,
        file_sha256=digest,
        warnings=warnings,
    )


def load_from_url(url: str) -> IngestResult:
    """Fetch a JSON resource from *url* and parse it.

    Enforces http/https schemes, API_TIMEOUT_S timeout, and MAX_API_RESPONSE_MB cap.
    """
    import urllib.parse
    import requests
    from src.config import API_TIMEOUT_S, MAX_API_RESPONSE_MB

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise IngestError("Only HTTP and HTTPS URLs are supported.")

    try:
        response = requests.get(url, timeout=API_TIMEOUT_S, stream=True)
        response.raise_for_status()
    except Exception as exc:
        raise IngestError(f"Failed to fetch data from URL: {exc}") from exc

    content = bytearray()
    max_bytes = MAX_API_RESPONSE_MB * 1024 * 1024
    for chunk in response.iter_content(chunk_size=8192):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise IngestError(f"Response stream exceeded {MAX_API_RESPONSE_MB} MB limit.")

    raw_bytes = bytes(content)
    return load("api_data.json", raw_bytes)


# ---------------------------------------------------------------------------
# Format-specific parsers
# ---------------------------------------------------------------------------

def _load_csv(content: bytes, warnings: list[str]) -> pd.DataFrame:
    """Decode and parse CSV bytes."""
    text: str | None = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = content.decode(encoding)
            if encoding == "latin-1":
                warnings.append(
                    "File encoding detected as latin-1 (not UTF-8). "
                    "Some special characters may not display correctly."
                )
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise IngestError("Could not decode the file. Please save it as UTF-8.")

    try:
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str)
    except Exception as exc:
        raise IngestError(f"Failed to parse CSV: {exc}") from exc

    return df


def _load_json(content: bytes, warnings: list[str]) -> pd.DataFrame:
    """Parse JSON bytes into a DataFrame."""
    try:
        text = content.decode("utf-8", errors="replace")
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"Invalid JSON: {exc}") from exc

    if isinstance(data, list):
        if not data or not isinstance(data[0], dict):
            raise IngestError("JSON is a list but does not contain objects.")
        return pd.json_normalize(data, sep="_")

    if isinstance(data, dict):
        # Case 1: dict with one key whose value is a list of objects
        list_values = {k: v for k, v in data.items() if isinstance(v, list)}
        if len(list_values) == 1:
            inner = next(iter(list_values.values()))
            if inner and isinstance(inner[0], dict):
                return pd.json_normalize(inner, sep="_")

        # Case 2: dict of equal-length lists (column-oriented)
        if all(isinstance(v, list) for v in data.values()):
            lengths = {len(v) for v in data.values()}
            if len(lengths) == 1:
                return pd.DataFrame(data)

        raise IngestError(
            "JSON structure not tabular. "
            "Expected a list of objects, a dict with one list of objects, "
            "or a dict of equal-length lists."
        )

    raise IngestError("JSON structure not tabular.")


def _load_xml(content: bytes, warnings: list[str]) -> pd.DataFrame:
    """Parse XML bytes using defusedxml (safe against XXE attacks)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise IngestError(f"Invalid XML: {exc}") from exc

    # Find the record element: most frequent child tag under the root,
    # descending one level if the root has a single child wrapper.
    children = list(root)
    if not children:
        raise IngestError("XML root element has no children; cannot extract records.")

    # Descend one level if the root has a single distinct child tag
    child_tags = [c.tag for c in children]
    distinct_tags = set(child_tags)
    if len(distinct_tags) == 1 and len(children) == 1:
        # Single wrapper child — descend into it
        root = children[0]
        children = list(root)
        child_tags = [c.tag for c in children]
        distinct_tags = set(child_tags)

    # Pick the most frequent tag as the record element name
    tag_counts: dict[str, int] = {}
    for tag in child_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if not tag_counts:
        raise IngestError("XML contains no repeating child elements.")

    record_tag = max(tag_counts, key=lambda t: tag_counts[t])
    records_els = [c for c in children if c.tag == record_tag]

    if len(records_els) < 1:
        raise IngestError(f"No <{record_tag}> elements found.")

    rows: list[dict] = []
    for el in records_els:
        row: dict = dict(el.attrib)  # attributes
        for child in el:
            if len(list(child)) == 0:
                row[child.tag] = child.text
            else:
                # Flatten one level: parent_child
                for grandchild in child:
                    row[f"{child.tag}_{grandchild.tag}"] = grandchild.text
        rows.append(row)

    if not rows:
        raise IngestError("XML records contain no data.")

    return pd.DataFrame(rows)


def _load_txt(content: bytes, warnings: list[str]) -> tuple[pd.DataFrame, bool]:
    """Parse a .txt file as delimited text or as free-text (unstructured)."""
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        text = content.decode("latin-1", errors="replace")

    lines = [ln for ln in text.splitlines() if ln.strip()]

    # Try CSV sniffer on first 20 non-empty lines with common delimiters
    sample = "\n".join(lines[:20])
    delimiter: str | None = None
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = None

    if delimiter and delimiter not in (".", "!", "?", "'", '"'):
        # Check that at least 2 columns appear consistently across ALL sample lines
        try:
            reader = csv.reader(lines[:20], delimiter=delimiter)
            col_counts = [len(row) for row in reader]
            # Every row must have >= 2 columns to be considered tabular
            if col_counts and min(col_counts) >= 2 and max(col_counts) == min(col_counts):
                df = pd.read_csv(
                    io.StringIO(text), sep=re.escape(delimiter), dtype=str, engine="python"
                )
                if df.shape[1] >= 2:
                    return df, False
        except Exception:
            pass

    # Unstructured: return line_no + text DataFrame
    df = pd.DataFrame(
        {"line_no": list(range(1, len(lines) + 1)), "text": lines}
    )
    return df, True

