"""
ui/components.py — Reusable Streamlit widgets shared across pages.
"""
from __future__ import annotations

import streamlit as st

from src.exceptions import InsightError
from src.models import AnalysisBundle, ChartSpec
from src.utils import get_logger
from ui import state

_log = get_logger(__name__)


def require_bundle() -> AnalysisBundle:
    """Guard: return the bundle or show a message and stop the page."""
    bundle = state.get_bundle()
    if bundle is None:
        st.info(
            "No analysis loaded yet. Please go to the **Upload** page, "
            "upload a file and click **Run analysis**.",
            icon="ℹ️",
        )
        st.page_link("ui/pages/upload.py", label="Go to Upload →", icon="📤")
        st.stop()
    return bundle  # type: ignore[return-value]


def render_chart(spec: ChartSpec) -> None:
    """Render a :class:`ChartSpec` figure with Streamlit."""
    st.plotly_chart(spec.figure, use_container_width=True, key=spec.id)


def show_warnings(warnings: list[str]) -> None:
    """Display a warning banner for each warning message."""
    for w in warnings:
        st.warning(w, icon="⚠️")


def metric_row(items: list[tuple[str, str | int | float]]) -> None:
    """Render a horizontal row of st.metric boxes."""
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.metric(label=label, value=value)


def dataframe_view(df, max_rows: int = 100) -> None:
    """Show up to *max_rows* rows of a DataFrame with an info note if truncated."""
    if len(df) > max_rows:
        st.caption(f"Showing first {max_rows} of {len(df):,} rows.")
        st.dataframe(df.head(max_rows), use_container_width=True)
    else:
        st.dataframe(df, use_container_width=True)


def show_error(exc: Exception) -> None:
    """Display a user-friendly error message.

    For :class:`InsightError` subclasses the ``user_message`` is shown.
    For any other exception a generic message is shown and the full error
    is logged (without data contents).
    """
    if isinstance(exc, InsightError):
        st.error(f"**Error:** {exc.user_message}", icon="🚨")
        if exc.detail:
            with st.expander("Technical detail"):
                st.code(exc.detail)
    else:
        _log.exception("Unexpected error in page: %s", type(exc).__name__)
        st.error(
            "**Something went wrong.** Please try another file or check the logs.",
            icon="🚨",
        )
        with st.expander("Technical detail"):
            st.code(str(exc))

