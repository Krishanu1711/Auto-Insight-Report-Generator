"""
ui/pages/saved.py — Browse, preview, download, and delete saved datasets.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import database
from src.exceptions import InsightError
from ui import components

st.title("🗄️ Saved Datasets")

# ---------------------------------------------------------------------------
# List datasets
# ---------------------------------------------------------------------------
try:
    engine = database.get_engine()
    records = database.list_datasets(engine=engine)
except InsightError as exc:
    components.show_error(exc)
    st.stop()

if not records:
    st.info("No datasets saved yet. Use the **Report** page to save your analysis.")
    st.stop()

records_df = pd.DataFrame([
    {
        "ID": r.id,
        "Name": r.name,
        "File": r.original_filename,
        "Format": r.source_format,
        "Rows": r.n_rows_clean,
        "Columns": r.n_cols_clean,
        "Saved At": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—",
    }
    for r in records
])

st.subheader(f"Saved datasets ({len(records)})")
st.dataframe(records_df, use_container_width=True)

# ---------------------------------------------------------------------------
# Select a dataset
# ---------------------------------------------------------------------------
st.divider()
ids = [r.id for r in records]
names = [f"#{r.id} — {r.name}" for r in records]
selected_label = st.selectbox("Select a dataset to view", names)
selected_id = ids[names.index(selected_label)]

if selected_id:
    col_preview, col_actions = st.columns([3, 1])

    with col_preview:
        st.subheader("Preview (first 100 rows)")
        try:
            preview_df = database.load_clean_table(selected_id, limit=100, engine=engine)
            components.dataframe_view(preview_df, max_rows=100)
        except InsightError as exc:
            components.show_error(exc)

    with col_actions:
        st.subheader("Actions")

        # Download full table
        try:
            full_df = database.load_clean_table(selected_id, engine=engine)
            csv_bytes = full_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_bytes,
                file_name=f"dataset_{selected_id}.csv",
                mime="text/csv",
            )
        except InsightError as exc:
            components.show_error(exc)

        st.divider()

        # Delete with confirmation
        confirm_delete = st.checkbox(f"I want to delete dataset #{selected_id}")
        if st.button("🗑️ Delete", type="secondary", disabled=not confirm_delete):
            try:
                database.delete_dataset(selected_id, engine=engine)
                st.success(f"Dataset #{selected_id} deleted.")
                st.rerun()
            except InsightError as exc:
                components.show_error(exc)

