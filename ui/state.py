"""
ui/state.py — Typed accessors for st.session_state.

All session keys are defined here.  No other module may read or write these
keys directly; use these functions instead.
"""
from __future__ import annotations

import streamlit as st

from src.models import AnalysisBundle

# ---------------------------------------------------------------------------
# Key constants
# ---------------------------------------------------------------------------
_KEY_BUNDLE = "bundle"
_KEY_UPLOAD_SHA = "upload_sha"
_KEY_REPORT_BYTES = "report_bytes"
_KEY_SAVED_DATASET_ID = "saved_dataset_id"


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

def get_bundle() -> AnalysisBundle | None:
    """Return the current :class:`AnalysisBundle` or None."""
    return st.session_state.get(_KEY_BUNDLE)


def set_bundle(bundle: AnalysisBundle, upload_sha: str | None = None) -> None:
    """Store a new bundle and clear the cached report bytes."""
    st.session_state[_KEY_BUNDLE] = bundle
    if upload_sha is not None:
        st.session_state[_KEY_UPLOAD_SHA] = upload_sha
    # Invalidate any previously built report
    st.session_state[_KEY_REPORT_BYTES] = None
    st.session_state[_KEY_SAVED_DATASET_ID] = None


# ---------------------------------------------------------------------------
# Upload SHA (used to detect a different file)
# ---------------------------------------------------------------------------

def get_upload_sha() -> str | None:
    return st.session_state.get(_KEY_UPLOAD_SHA)


# ---------------------------------------------------------------------------
# Report bytes
# ---------------------------------------------------------------------------

def get_report_bytes() -> bytes | None:
    return st.session_state.get(_KEY_REPORT_BYTES)


def set_report_bytes(data: bytes) -> None:
    st.session_state[_KEY_REPORT_BYTES] = data


# ---------------------------------------------------------------------------
# Saved dataset id
# ---------------------------------------------------------------------------

def get_saved_dataset_id() -> int | None:
    return st.session_state.get(_KEY_SAVED_DATASET_ID)


def set_saved_dataset_id(dataset_id: int) -> None:
    st.session_state[_KEY_SAVED_DATASET_ID] = dataset_id


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def reset_all() -> None:
    """Clear all session state keys managed by this module."""
    for key in (_KEY_BUNDLE, _KEY_UPLOAD_SHA, _KEY_REPORT_BYTES, _KEY_SAVED_DATASET_ID):
        st.session_state.pop(key, None)

