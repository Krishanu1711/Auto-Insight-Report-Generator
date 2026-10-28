# Auto-Insight Report Generator

> Upload any dataset and get a cleaned dataset, the right charts, a forecast (when dates exist) and a downloadable report, automatically.

Final project for **Data Analytics & Visualization (DAV) Lab**, Department of Artificial Intelligence and Machine Learning, Ramdeobaba University (RBU), Nagpur.

**Status:** Core features complete & verified (P0–P9, 100% test pass rate)

---

## Overview

Most data analysis projects are built around one fixed dataset. **Auto-Insight Report Generator** is an automated tool designed to work on *any* tabular or text dataset. A user uploads a CSV, JSON, XML or TXT file, and the system:

1. **Reads & understands the file** (format detection, encoding detection, column types, dates, categories)
2. **Cleans & preprocesses** (rename snake_case, trim & NA tokens, type coercion, drop duplicates/empty rows, missing-threshold column drop, median/Unknown imputation, case harmonization, IQR outlier handling)
3. **Profiles columns** (classification into 8 ColumnKinds, date identification, summary statistics)
4. **Transforms & analyzes** (Min-Max/standard scaling, label/one-hot encoding, binning, group aggregations, descriptive stats, Pearson correlation, OLS linear regression)
5. **Smart visualizations** (Distribution histograms & box plots, categorical pies/donuts/bars, relationship scatter plots with trendlines, correlation heatmap)
6. **Time-series forecasting** (resampling, moving averages, additive/multiplicative decomposition, ADF test, ARIMA grid search, backtesting with MAE/RMSE/MAPE)
7. **Report export** (self-contained, standalone single-file HTML report with embedded Plotly JS)
8. **Persistence** (optional SQLite storage via SQLAlchemy 2.0 with metadata tables and dynamic clean data tables)

---

## How It Works

```
Upload file
    |
    v
Read & detect format (CSV / JSON / XML / TXT)
    |
    v
Clean data (ordered 8-step pipeline with audit log and quality stats)
    |
    v
Profile columns (classify into 8 ColumnKinds, pick primary date)
    |
    v
Transform & Analyze (scaling, encoding, binning, aggregation, correlation, regression)
    |
    v
Auto-select visualizations (Plotly figures for distributions, categories, relationships)
    |
    v
Date column found? --yes--> Decompose + moving averages (SMA/EMA) + ARIMA forecast
    |
    v
Generate insight report (HTML with inlined Plotly) + (optional) save to SQLite
```

---

## Tech Stack

| Area | Tools | Notes |
|---|---|---|
| Language | Python 3.11+ | Python 3.13 tested & supported |
| Core Data | Pandas, NumPy | Data manipulation and numeric operations |
| Preprocessing & ML | Scikit-learn | Scalers, encoders, linear regression, stop words |
| Time Series | Statsmodels | Seasonal decomposition, ADF stationarity, ARIMA |
| Visualizations | Plotly | Interactive charts in both Streamlit app and HTML report |
| Safe XML | defusedxml | Hardened XML parsing preventing XXE attacks |
| Storage | SQLite, SQLAlchemy 2.0 | Metadata tables + dynamic `clean_<id>` tables |
| Report Engine | Jinja2 | Self-contained HTML report with Plotly JS |
| Front End | Streamlit | Multipage app with 6 dedicated pages |
| Testing | pytest | 74 unit and end-to-end integration tests |

---

## How the Project Covers the DAV Labs

| Lab | Topic | Used in this project for |
|---|---|---|
| 1 | Reading structured and unstructured data | Multi-format file ingestion (CSV, JSON, XML, TXT) |
| 2 | Data cleaning and preprocessing | Duplicates, missing values, outliers, standardisation |
| 3 | Transformation and analysis | Scaling, encoding, binning, aggregation, correlation, regression |
| 4 | Data extraction using APIs | Optional data fetch from a public API (Phase 10 extension) |
| 5 | Python and databases | Saving cleaned data to SQLite with `to_sql()` |
| 6 | Time-series analytics | Decomposition, moving averages, ARIMA forecasting |
| 7 | Line and scatter plots | Trend lines, annotated charts, correlation analysis |
| 8 | Histograms, box plots, bar/pie/donut charts | Automatic chart selection and dashboard |

---

## Project Structure

```
auto-insight-report-generator/
├── app.py                         # Streamlit entry point: page config + st.navigation
├── requirements.txt
├── pytest.ini
├── README.md
├── ARCHITECTURE.md
├── .gitignore
├── .streamlit/
│   └── config.toml                # upload size limit, theme, telemetry off
├── data/
│   ├── samples/                   # committed small sample inputs
│   └── insight.db                 # created at runtime (git-ignored)
├── notebooks/                     # lab prototypes (Labs 1 to 8); not imported by src/
├── scripts/
│   └── generate_samples.py        # deterministic generator for data/samples/*
├── src/
│   ├── __init__.py
│   ├── config.py                  # constants, thresholds, default paths
│   ├── exceptions.py              # InsightError hierarchy
│   ├── models.py                  # enums + dataclasses (all shared types)
│   ├── utils.py                   # logging, snake_case, safe parsers, sha256
│   ├── ingest.py                  # CSV/JSON/XML/TXT -> DataFrame
│   ├── clean.py                   # cleaning steps + cleaning log + quality stats
│   ├── profile.py                 # column type classification + column profiles
│   ├── transform.py               # scaling, encoding, binning, aggregation
│   ├── analyze.py                 # descriptive stats, correlation, regression, text summary
│   ├── forecast.py                # SMA/EMA, decomposition, ARIMA, backtest
│   ├── visualize.py               # automatic chart selection -> Plotly figures
│   ├── insights.py                # rule-based plain-language insights
│   ├── report.py                  # HTML report builder (Jinja2)
│   ├── database.py                # SQLAlchemy engine, ORM tables, save/list/load/delete
│   ├── pipeline.py                # orchestrator: run_pipeline, rerun_forecast
│   └── templates/
│       └── report.html.j2         # HTML report template
├── ui/
│   ├── __init__.py
│   ├── state.py                   # typed session_state accessors
│   ├── components.py              # reusable Streamlit widgets
│   └── pages/
│       ├── upload.py              # Upload and run analysis
│       ├── profile.py             # Data profile, cleaning log, transformed data
│       ├── explore.py             # Auto-generated charts
│       ├── forecast.py            # Time-series analysis
│       ├── report.py              # Report download, CSV downloads, save to DB
│       └── saved.py               # Saved datasets browser
└── tests/
    ├── conftest.py                # synthetic dataset fixtures
    ├── test_ingest.py
    ├── test_clean.py
    ├── test_profile.py
    ├── test_transform_analyze.py
    ├── test_visualize.py
    ├── test_forecast.py
    ├── test_report.py
    ├── test_database.py
    └── test_pipeline_e2e.py
```

---

## Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/auto-insight-report-generator.git
cd auto-insight-report-generator

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Generate deterministic sample data
python scripts/generate_samples.py

# 5. Run tests
pytest tests/ -v

# 6. Run the app
streamlit run app.py
```

---

## Roadmap

- [x] **P0: Scaffolding and contracts** (frozen models, config, exceptions, utils, app skeleton)
- [x] **P1: Ingest module** (CSV, JSON, XML via defusedxml, delimited TXT, unstructured TXT)
- [x] **P2: Clean module** (8 ordered steps, change log, quality stats before/after)
- [x] **P3: Profile module** (ColumnKind classification, primary date column selection)
- [x] **P4: Transform & Analyze** (Min-max, standard, label & one-hot encoding, binning, descriptive stats, correlation, OLS regression)
- [x] **P5: Visualize module** (Automatic Plotly chart generator for distributions, categories, relationships, and time-series)
- [x] **P6: Pipeline & Core Pages** (End-to-end orchestrator, Upload, Profile, and Explore pages)
- [x] **P7: Forecast module & page** (Resampling, moving averages, seasonal decomposition, ADF stationarity, ARIMA grid search, backtesting, forecast page)
- [x] **P8: Insights & Report engine** (Deterministic rule-based plain-language insights, standalone Jinja2 HTML report generator)
- [x] **P9: Database & Saved page** (SQLAlchemy 2.0 ORM, dynamic `clean_<id>` tables, transaction rollback, cascade delete)
- [ ] **P10: Optional API ingestion** (`load_from_url` for live public JSON REST endpoints)

---

## Team

| Name | Role |
|---|---|
| *Member 1* | *TBD* |
| *Member 2* | *TBD* |
| *Member 3* | *TBD* |

**Course:** Data Analytics & Visualization Lab, V Semester  
**Institution:** Ramdeobaba University (RBU), Nagpur  
**Session:** 2026-27  

## License

This project is for academic purposes.
