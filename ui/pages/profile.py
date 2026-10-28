"""
ui/pages/profile.py — Data profile, cleaning log, and transformed data viewer.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ui import components

st.set_page_config(page_title="Profile — Auto-Insight", page_icon="📋", layout="wide")
st.title("📋 Data Profile")

bundle = components.require_bundle()

tab_overview, tab_cleaning, tab_transform = st.tabs(
    ["📊 Overview", "🧹 Cleaning", "🔄 Transformed Data"]
)

# ---------------------------------------------------------------------------
# Tab 1: Overview
# ---------------------------------------------------------------------------
with tab_overview:
    st.subheader("Dataset Overview")

    from src.models import ColumnKind
    numeric_count = len(bundle.profile.cols_of(ColumnKind.NUMERIC))
    cat_count = len(bundle.profile.cols_of(ColumnKind.CATEGORICAL))
    date_count = len(bundle.profile.cols_of(ColumnKind.DATETIME))

    components.metric_row([
        ("Rows", f"{bundle.profile.n_rows:,}"),
        ("Columns", bundle.profile.n_cols),
        ("Numeric", numeric_count),
        ("Categorical", cat_count),
        ("Date columns", date_count),
        ("Memory", f"{bundle.profile.memory_mb:.2f} MB"),
    ])

    st.subheader("Column Profiles")
    profile_rows = [
        {
            "Column": cp.name,
            "Kind": cp.kind.value,
            "Dtype": cp.dtype,
            "Missing": cp.n_missing,
            "Missing %": f"{cp.pct_missing:.1%}",
            "Unique": cp.n_unique,
            "Sample Values": ", ".join(cp.sample_values[:3]),
        }
        for cp in bundle.profile.columns
    ]
    st.dataframe(pd.DataFrame(profile_rows), use_container_width=True)

    st.subheader("Insights")
    if bundle.insights:
        for ins in bundle.insights:
            if ins.level == "warning":
                st.warning(f"**[{ins.category}]** {ins.text}", icon="⚠️")
            else:
                st.info(f"**[{ins.category}]** {ins.text}", icon="ℹ️")
    else:
        st.write("No insights generated.")

    if bundle.analysis.descriptive is not None:
        st.subheader("Descriptive Statistics")
        st.dataframe(bundle.analysis.descriptive.round(4), use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 2: Cleaning
# ---------------------------------------------------------------------------
with tab_cleaning:
    st.subheader("Quality: Before vs After")
    qb = bundle.clean.quality_before
    qa = bundle.clean.quality_after
    quality_df = pd.DataFrame(
        {
            "Before": [qb.n_rows, qb.n_cols, qb.missing_cells, qb.duplicate_rows, qb.outlier_cells],
            "After": [qa.n_rows, qa.n_cols, qa.missing_cells, qa.duplicate_rows, qa.outlier_cells],
        },
        index=["Rows", "Columns", "Missing Cells", "Duplicate Rows", "Outlier Cells"],
    )
    st.dataframe(quality_df, use_container_width=True)

    st.subheader("Cleaning Log")
    log_rows = [
        {
            "Step": a.step.value,
            "Column": a.column or "—",
            "Description": a.description,
            "Rows Affected": a.rows_affected,
        }
        for a in bundle.clean.actions
    ]
    if log_rows:
        st.dataframe(pd.DataFrame(log_rows), use_container_width=True)
    else:
        st.write("No cleaning actions were performed.")

    if bundle.clean.rename_map:
        st.subheader("Column Renames")
        rename_df = pd.DataFrame(
            [
                {"Original": k, "Renamed To": v}
                for k, v in bundle.clean.rename_map.items()
                if k != v
            ]
        )
        if not rename_df.empty:
            st.dataframe(rename_df, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 3: Transformed Data
# ---------------------------------------------------------------------------
with tab_transform:
    if bundle.transform is None:
        st.info("Transformation is not available for unstructured text input.")
    else:
        t = bundle.transform
        options = {
            "Min-Max Scaled": t.scaled_minmax,
            "Standard Scaled": t.scaled_standard,
            "Label Encoded": t.label_encoded,
            "One-Hot Encoded": t.one_hot,
            "Binned": t.binned,
            "ML-Ready (Standard + One-Hot)": t.ml_ready,
        }
        for key, agg_df in t.aggregations.items():
            options[f"Aggregation: {key}"] = agg_df

        choice = st.selectbox("Select a view", list(options.keys()))
        chosen_df = options[choice]

        if chosen_df.empty:
            st.warning("This view is empty (no columns of the required type).")
        else:
            components.show_warnings(t.warnings)
            components.dataframe_view(chosen_df, max_rows=50)

