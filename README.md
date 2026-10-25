# Auto-Insight Report Generator

> Upload any dataset and get a cleaned dataset, the right charts, a forecast (when dates exist) and a downloadable report, automatically.

Final project for **Data Analytics & Visualization (DAV) Lab**, Department of Artificial Intelligence and Machine Learning, Ramdeobaba University (RBU), Nagpur.

**Status:** Under development (initial commit)

---

## Overview

Most data analysis projects are built around one fixed dataset. **Auto-Insight Report Generator** is a tool that works on *any* dataset. A user uploads a CSV, JSON, XML or TXT file, and the system:

1. Reads and understands the file (column types, missing values, dates, categories)
2. Cleans and preprocesses the data
3. Chooses suitable visualizations for each column
4. Forecasts future values if the data contains a time component
5. Exports a short, readable insight report

The aim is that a dataset the tool has never seen can be analysed live, with no manual changes to the code.

## Key Features (Planned)

- **Multi-format ingestion:** reads `.csv`, `.json`, `.xml` and `.txt` into one standard DataFrame.
- **Automatic profiling:** detects numeric, categorical and date columns, missing values, duplicates and outliers.
- **Automatic cleaning:** removes duplicates, fills missing values, standardises text, fixes data types and flags outliers (IQR / Z-score), with a log of every change made.
- **Transformations:** Min-Max normalization, standard scaling, label/one-hot encoding, binning and group aggregation.
- **Smart chart selection:**

  | Column type | Chart used |
  |---|---|
  | Numeric | Histogram + box plot |
  | Categorical | Bar chart / pie / donut chart |
  | Two numeric columns | Scatter plot with trend line |
  | Multiple numeric columns | Correlation heatmap |
  | Date column present | Line chart with moving averages |

- **Time-series forecasting:** trend/seasonality decomposition, moving averages, exponential smoothing and ARIMA forecasts when a date column is found.
- **Report export:** summary of data quality, key statistics, charts and forecast.
- **Optional database storage:** cleaned data saved to SQLite via SQLAlchemy.

## How It Works

```
Upload file
    |
    v
Read & detect format (CSV / JSON / XML / TXT)
    |
    v
Profile columns (types, missing values, dates, outliers)
    |
    v
Clean & transform (duplicates, missing values, scaling, encoding, binning)
    |
    v
Auto-select visualizations
    |
    v
Date column found? --yes--> Decompose + moving averages + ARIMA forecast
    |
    v
Generate insight report + (optional) save to SQLite
```

## Tech Stack

| Area | Tools |
|---|---|
| Language | Python 3 |
| Data handling | Pandas, NumPy |
| Preprocessing and regression | Scikit-learn |
| Time series | Statsmodels |
| Visualization | Matplotlib, Seaborn, Plotly |
| Storage | SQLite, SQLAlchemy |
| Front end | Streamlit *(planned)* |
| Development | Jupyter Notebook / Google Colab |

## How the Project Covers the DAV Labs

| Lab | Topic | Used in this project for |
|---|---|---|
| 1 | Reading structured and unstructured data | Multi-format file ingestion |
| 2 | Data cleaning and preprocessing | Duplicates, missing values, outliers, standardisation |
| 3 | Transformation and analysis | Scaling, encoding, binning, aggregation, correlation, regression |
| 4 | Data extraction using APIs | Optional data fetch from a public API (planned extension) |
| 5 | Python and databases | Saving cleaned data to SQLite with `to_sql()` |
| 6 | Time-series analytics | Decomposition, moving averages, ARIMA forecasting |
| 7 | Line and scatter plots | Trend lines, annotated charts, correlation analysis |
| 8 | Histograms, box plots, bar/pie/donut charts | Automatic chart selection and dashboard |

## Project Structure (Proposed)

```
auto-insight-report-generator/
├── data/                # Sample input datasets
├── src/
│   ├── ingest.py        # File reading and format detection
│   ├── profile.py       # Column type detection and data profiling
│   ├── clean.py         # Cleaning and preprocessing
│   ├── transform.py     # Scaling, encoding, binning, aggregation
│   ├── visualize.py     # Automatic chart selection
│   ├── forecast.py      # Time-series analysis and ARIMA
│   ├── report.py        # Report generation
│   └── database.py      # SQLite / SQLAlchemy storage
├── notebooks/           # Experiments and lab-based prototypes
├── app.py               # Streamlit front end (planned)
├── requirements.txt
└── README.md
```

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

# 4. Run the app (once implemented)
streamlit run app.py
```

## Roadmap

- [ ] Multi-format file reader
- [ ] Column profiling and type detection
- [ ] Automated cleaning with change log
- [ ] Data transformation module
- [ ] Automatic chart selection
- [ ] Time-series forecasting module
- [ ] Report export
- [ ] SQLite storage
- [ ] Streamlit interface
- [ ] Testing on multiple unseen datasets

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

This project is for academic purposes. Add a license (for example MIT) here if you plan to open-source it.
