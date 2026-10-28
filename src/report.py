"""
src/report.py — Build a self-contained HTML report using Jinja2.

Public API
----------
build_report(bundle) -> bytes    (UTF-8 encoded HTML)
"""
from __future__ import annotations

from pathlib import Path

import plotly.offline
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from src.config import REPORT_TABLE_MAX_ROWS
from src.exceptions import ReportError
from src.models import AnalysisBundle, ChartGroup
from src.utils import get_logger

_log = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def build_report(bundle: AnalysisBundle) -> bytes:
    """Render *bundle* to a single self-contained UTF-8 HTML file.

    The Plotly JS library is inlined once in ``<head>``.
    All other content is autoescaped by Jinja2.
    Raises :class:`ReportError` on template or rendering failure.
    """
    _log.info("Building HTML report.")
    try:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            # We manually mark Plotly HTML safe below, so keep autoescape=True
        )
        # Deliberately NOT using select_autoescape on .j2 extension alone —
        # autoescape is explicitly True for all templates (architecture rule).
        env.autoescape = True

        template = env.get_template("report.html.j2")

        plotly_js = plotly.offline.get_plotlyjs()

        # Build chart HTML (marked Markup so Jinja2 does not re-escape it)
        def chart_html(spec) -> Markup:
            return Markup(spec.figure.to_html(full_html=False, include_plotlyjs=False))

        # Group charts by ChartGroup
        grouped_charts: dict[str, list] = {}
        for spec in bundle.charts:
            key = spec.group.value
            grouped_charts.setdefault(key, []).append(spec)

        # Descriptive stats HTML
        desc_html: str | None = None
        if bundle.analysis.descriptive is not None:
            desc_html = bundle.analysis.descriptive.to_html(
                escape=True, max_rows=REPORT_TABLE_MAX_ROWS
            )

        # Correlation HTML
        corr_html: str | None = None
        if bundle.analysis.correlation is not None:
            corr_html = bundle.analysis.correlation.round(3).to_html(
                escape=True, max_rows=REPORT_TABLE_MAX_ROWS
            )

        # Cleaning log HTML
        import pandas as pd
        log_rows = [
            {
                "Step": a.step.value,
                "Column": a.column or "—",
                "Description": a.description,
                "Rows Affected": a.rows_affected,
            }
            for a in bundle.clean.actions
        ]
        cleaning_log_html = pd.DataFrame(log_rows).to_html(
            escape=True, index=False, max_rows=REPORT_TABLE_MAX_ROWS
        )

        # Column profile HTML
        profile_rows = [
            {
                "Column": cp.name,
                "Kind": cp.kind.value,
                "Dtype": cp.dtype,
                "Missing": f"{cp.n_missing} ({cp.pct_missing:.1%})",
                "Unique": cp.n_unique,
                "Sample": ", ".join(cp.sample_values[:3]),
            }
            for cp in bundle.profile.columns
        ]
        profile_html = pd.DataFrame(profile_rows).to_html(
            escape=True, index=False, max_rows=REPORT_TABLE_MAX_ROWS
        )

        # Forecast table HTML
        forecast_html: str | None = None
        if bundle.forecast is not None:
            forecast_html = bundle.forecast.forecast.round(4).to_html(escape=True)

        html_str = template.render(
            bundle=bundle,
            plotly_js=Markup(plotly_js),
            chart_html=chart_html,
            grouped_charts=grouped_charts,
            desc_html=Markup(desc_html) if desc_html else None,
            corr_html=Markup(corr_html) if corr_html else None,
            cleaning_log_html=Markup(cleaning_log_html),
            profile_html=Markup(profile_html),
            forecast_html=Markup(forecast_html) if forecast_html else None,
            ChartGroup=ChartGroup,
            REPORT_TABLE_MAX_ROWS=REPORT_TABLE_MAX_ROWS,
        )

        _log.info("Report built successfully (%.1f kB).", len(html_str) / 1024)
        return html_str.encode("utf-8")

    except Exception as exc:
        raise ReportError(f"Failed to build report: {exc}", detail=str(exc)) from exc

