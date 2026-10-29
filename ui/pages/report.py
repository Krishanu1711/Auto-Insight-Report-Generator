"""
ui/pages/report.py — Report download, CSV exports and save to SQLite.
"""
from __future__ import annotations

import streamlit as st

from src import database, report as rpt
from src.exceptions import InsightError
from ui import components, state

st.title("📄 Report & Export")

bundle = components.require_bundle()

# ---------------------------------------------------------------------------
# HTML Report
# ---------------------------------------------------------------------------
st.subheader("📥 HTML Report")
if st.button("🔨 Build report", type="primary"):
    try:
        with st.spinner("Building report …"):
            report_bytes = rpt.build_report(bundle)
        state.set_report_bytes(report_bytes)
        st.success("Report built!")
    except InsightError as exc:
        components.show_error(exc)

report_bytes = state.get_report_bytes()
if report_bytes:
    st.download_button(
        label="⬇️ Download HTML report",
        data=report_bytes,
        file_name="insight_report.html",
        mime="text/html",
    )

st.divider()

# ---------------------------------------------------------------------------
# CSV Downloads
# ---------------------------------------------------------------------------
st.subheader("📂 Download Data")

col1, col2 = st.columns(2)
with col1:
    clean_csv = bundle.clean.df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Cleaned data (CSV)",
        data=clean_csv,
        file_name="cleaned_data.csv",
        mime="text/csv",
    )

with col2:
    if bundle.transform is not None and not bundle.transform.ml_ready.empty:
        ml_csv = bundle.transform.ml_ready.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ ML-ready data (CSV)",
            data=ml_csv,
            file_name="ml_ready_data.csv",
            mime="text/csv",
        )
    else:
        st.info("ML-ready data not available for unstructured input.")

st.divider()

# ---------------------------------------------------------------------------
# Save to SQLite
# ---------------------------------------------------------------------------
st.subheader("💾 Save to SQLite")

default_name = bundle.source.filename
save_name = st.text_input("Dataset name", value=default_name)

if st.button("💾 Save to SQLite", type="secondary"):
    try:
        with st.spinner("Saving …"):
            engine = database.get_engine()
            dataset_id = database.save_bundle(bundle, name=save_name, engine=engine)
        state.set_saved_dataset_id(dataset_id)
        st.success(f"Saved! Dataset ID: **{dataset_id}**")
    except InsightError as exc:
        components.show_error(exc)

saved_id = state.get_saved_dataset_id()
if saved_id is not None:
    st.info(f"Last saved as dataset **#{saved_id}**. View it on the Saved page.")
    st.page_link("ui/pages/saved.py", label="Go to Saved datasets →", icon="🗄️")

