"""
ui/pages/upload.py — Upload page: file uploader, cleaning options and pipeline runner.
"""
from __future__ import annotations

import streamlit as st

from src import pipeline as pipe
from src.exceptions import InsightError
from src.models import CleaningConfig, OutlierTreatment, PipelineConfig
from src.utils import sha256_bytes
from ui import components, state

st.title("📤 Upload & Analyse")
st.caption("Upload a CSV, JSON, XML or TXT file to get started.")

# ---------------------------------------------------------------------------
# Upload or API URL
# ---------------------------------------------------------------------------
tab_file, tab_url = st.tabs(["📁 Upload File", "🌐 From API URL"])

with tab_file:
    uploaded = st.file_uploader(
        "Choose a file",
        type=["csv", "json", "xml", "txt"],
        help="Max 50 MB. Supported formats: CSV, JSON, XML, TXT.",
    )

with tab_url:
    api_url = st.text_input(
        "Public JSON API URL",
        placeholder="https://jsonplaceholder.typicode.com/posts",
        help="Enter a public URL returning a JSON array or object.",
    )

# ---------------------------------------------------------------------------
# Cleaning options
# ---------------------------------------------------------------------------
with st.expander("⚙️ Cleaning options", expanded=False):
    outlier_choice = st.selectbox(
        "Outlier treatment",
        options=["flag", "cap", "remove"],
        index=0,
        help="flag = log only, cap = clip to IQR fences, remove = drop rows",
    )
    missing_threshold = st.slider(
        "Drop column if missing > X%",
        min_value=0.30,
        max_value=0.90,
        value=0.60,
        step=0.05,
        format="%.0f%%",
        help="Columns with more than this fraction of missing values are dropped.",
    )
    auto_forecast = st.checkbox("Auto-forecast when date column detected", value=True)

# ---------------------------------------------------------------------------
# Run button
# ---------------------------------------------------------------------------
has_input = (uploaded is not None) or bool(api_url.strip())
run_btn = st.button("🚀 Run analysis", type="primary", disabled=not has_input)

if run_btn:
    from src import ingest
    try:
        if uploaded is not None:
            filename = uploaded.name
            content = uploaded.getvalue()
        elif api_url.strip():
            with st.spinner("Fetching data from API URL..."):
                ingest_res = ingest.load_from_url(api_url.strip())
                filename = api_url.strip().split("/")[-1] or "api_data.json"
                if not filename.endswith(".json"):
                    filename += ".json"
                content = ingest_res.df.to_json(orient="records").encode("utf-8")
        else:
            st.stop()

        sha = sha256_bytes(content)

        # If a different file is uploaded, reset state
        if sha != state.get_upload_sha():
            state.reset_all()

        cleaning_cfg = CleaningConfig(
            outlier_treatment=OutlierTreatment(outlier_choice),
            drop_column_missing_pct=missing_threshold,
        )
        pipeline_cfg = PipelineConfig(cleaning=cleaning_cfg, auto_forecast=auto_forecast)

        with st.status("Running analysis …", expanded=True) as status_box:
            progress_bar = st.progress(0.0)

            def _progress(label: str, frac: float) -> None:
                st.write(f"**{label}**")
                progress_bar.progress(frac)

            bundle = pipe.run_pipeline(
                filename=filename,
                content=content,
                config=pipeline_cfg,
                progress=_progress,
            )
            status_box.update(label="✅ Analysis complete!", state="complete")

        state.set_bundle(bundle, upload_sha=sha)

    except InsightError as exc:
        components.show_error(exc)
        st.stop()
    except Exception as exc:
        components.show_error(exc)
        st.stop()

# ---------------------------------------------------------------------------
# Results summary (if a bundle exists)
# ---------------------------------------------------------------------------
bundle = state.get_bundle()
if bundle is not None:
    st.divider()
    st.subheader("📊 Summary")

    components.metric_row([
        ("Raw rows", f"{bundle.source.n_rows_raw:,}"),
        ("Clean rows", f"{bundle.clean.df.shape[0]:,}"),
        ("Columns", f"{bundle.clean.df.shape[1]}"),
        ("Cleaning actions", len(bundle.clean.actions)),
        ("Charts", len(bundle.charts)),
        ("Forecast", "✅" if bundle.forecast else ("⚠️" if bundle.forecast_error else "—")),
    ])

    if bundle.forecast_error:
        st.info(f"ℹ️ {bundle.forecast_error}")

    components.show_warnings(bundle.source.warnings)
    components.show_warnings(bundle.clean.warnings)

    st.subheader("👀 Raw data preview")
    components.dataframe_view(bundle.source.raw_preview)

    st.divider()
    st.subheader("🔗 Next steps")
    col1, col2, col3, col4 = st.columns(4)
    col1.page_link("ui/pages/profile.py", label="📋 Profile", icon="📋")
    col2.page_link("ui/pages/explore.py", label="📈 Explore charts", icon="📈")
    col3.page_link("ui/pages/forecast.py", label="🔮 Forecast", icon="🔮")
    col4.page_link("ui/pages/report.py", label="📄 Report", icon="📄")

