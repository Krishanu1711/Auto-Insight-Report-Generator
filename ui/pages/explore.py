"""
ui/pages/explore.py — Auto-generated charts grouped by ChartGroup.
"""
from __future__ import annotations

import streamlit as st

from src.models import ChartGroup
from ui import components

st.set_page_config(page_title="Explore — Auto-Insight", page_icon="📈", layout="wide")
st.title("📈 Explore Charts")

bundle = components.require_bundle()

# Group charts by their ChartGroup
grouped: dict[str, list] = {}
for spec in bundle.charts + bundle.forecast_charts:
    grouped.setdefault(spec.group.value, []).append(spec)

GROUP_LABELS = {
    ChartGroup.DISTRIBUTION.value: "📊 Distributions",
    ChartGroup.CATEGORY.value: "🗂️ Categories",
    ChartGroup.RELATIONSHIP.value: "🔗 Relationships",
    ChartGroup.TEXT.value: "📝 Text Analysis",
    ChartGroup.TIME_SERIES.value: "📅 Time Series",
}

if not grouped:
    st.info("No charts were generated for this dataset.")
else:
    tab_names = [GROUP_LABELS.get(k, k.title()) for k in grouped]
    tabs = st.tabs(tab_names)

    for tab, (group_key, specs) in zip(tabs, grouped.items()):
        with tab:
            # 2-column grid
            col_pairs = [specs[i:i+2] for i in range(0, len(specs), 2)]
            for pair in col_pairs:
                cols = st.columns(len(pair))
                for col, spec in zip(cols, pair):
                    with col:
                        components.render_chart(spec)
                        st.caption(spec.description)

# Regression summary card
if bundle.analysis.regression is not None:
    st.divider()
    st.subheader("🔢 Linear Regression Summary")
    reg = bundle.analysis.regression
    components.metric_row([
        ("X", reg.x),
        ("Y", reg.y),
        ("Coefficient", f"{reg.coef:.4f}"),
        ("Intercept", f"{reg.intercept:.4f}"),
        ("R²", f"{reg.r2:.4f}"),
        ("MAE", f"{reg.mae:.4f}"),
        ("RMSE", f"{reg.rmse:.4f}"),
        ("Train rows", reg.n_train),
        ("Test rows", reg.n_test),
    ])

