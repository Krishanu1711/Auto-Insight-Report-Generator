"""
src/database.py — SQLAlchemy 2.0 engine, ORM tables, and CRUD operations.

Public API
----------
get_engine(db_path)                                     -> Engine
init_db(engine)                                         -> None
save_bundle(bundle, name, engine)                       -> int   (dataset id)
list_datasets(engine)                                   -> list[DatasetRecord]
load_clean_table(dataset_id, limit, engine)             -> pd.DataFrame
delete_dataset(dataset_id, engine)                      -> None
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from src.config import DB_PATH
from src.exceptions import StorageError
from src.models import AnalysisBundle, DatasetRecord
from src.utils import get_logger

_log = get_logger(__name__)

_CLEAN_TABLE_RE = re.compile(r"^clean_\d+$")


# ---------------------------------------------------------------------------
# ORM base and tables
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class DatasetRow(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)
    source_format = Column(Text, nullable=False)
    file_sha256 = Column(Text, nullable=False, index=True)
    n_rows_raw = Column(Integer, nullable=False)
    n_cols_raw = Column(Integer, nullable=False)
    n_rows_clean = Column(Integer, nullable=False)
    n_cols_clean = Column(Integer, nullable=False)
    clean_table = Column(Text, nullable=False, unique=True)
    quality_before = Column(Text, nullable=False)    # JSON
    quality_after = Column(Text, nullable=False)     # JSON
    primary_date_col = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class CleaningLogRow(Base):
    __tablename__ = "cleaning_log"
    __table_args__ = (UniqueConstraint("dataset_id", "step_order"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    step = Column(Text, nullable=False)
    column_name = Column(Text, nullable=True)
    description = Column(Text, nullable=False)
    rows_affected = Column(Integer, nullable=False, default=0)


class ColumnProfileRow(Base):
    __tablename__ = "column_profiles"
    __table_args__ = (UniqueConstraint("dataset_id", "column_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    ordinal = Column(Integer, nullable=False)
    column_name = Column(Text, nullable=False)
    dtype = Column(Text, nullable=False)
    kind = Column(Text, nullable=False)
    n_missing = Column(Integer, nullable=False)
    n_unique = Column(Integer, nullable=False)
    stats = Column(Text, nullable=True)     # JSON


class ForecastRunRow(Base):
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    date_column = Column(Text, nullable=False)
    target_column = Column(Text, nullable=False)
    agg = Column(Text, nullable=False)
    freq = Column(Text, nullable=False)
    horizon = Column(Integer, nullable=False)
    arima_p = Column(Integer, nullable=False)
    arima_d = Column(Integer, nullable=False)
    arima_q = Column(Integer, nullable=False)
    aic = Column(Float, nullable=False)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)
    forecast = Column(Text, nullable=False)     # JSON list of {date, forecast, lower, upper}
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------

def get_engine(db_path: str | None = None) -> Engine:
    """Create (or reuse) a SQLAlchemy engine for the SQLite database at *db_path*.

    Foreign keys are enabled on every new connection via an event listener.
    """
    path = db_path or DB_PATH
    engine = create_engine(f"sqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create all ORM tables if they do not already exist."""
    import os
    db_url = str(engine.url)
    # Extract path from sqlite:///path
    if "///" in db_url:
        db_file = db_url.split("///", 1)[1]
        os.makedirs(os.path.dirname(db_file) if os.path.dirname(db_file) else ".", exist_ok=True)
    Base.metadata.create_all(engine)
    _log.info("Database initialised.")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def save_bundle(
    bundle: AnalysisBundle,
    name: str | None = None,
    engine: Engine | None = None,
) -> int:
    """Persist the bundle to the database and return the new dataset id.

    Runs entirely in one transaction; raises :class:`StorageError` on failure.
    """
    eng = engine or get_engine()
    init_db(eng)

    display_name = name or bundle.source.filename

    def _qs(obj) -> dict:
        """QualityStats to dict, handling dataclass or plain object."""
        try:
            return asdict(obj)
        except Exception:
            return {k: getattr(obj, k) for k in vars(obj)}

    try:
        with eng.begin() as conn:
            # 1. Insert placeholder row
            placeholder = f"pending_{uuid.uuid4().hex}"
            result = conn.execute(
                text(
                    "INSERT INTO datasets "
                    "(name, original_filename, source_format, file_sha256, "
                    "n_rows_raw, n_cols_raw, n_rows_clean, n_cols_clean, "
                    "clean_table, quality_before, quality_after, primary_date_col, created_at) "
                    "VALUES (:name, :orig, :fmt, :sha, :rraw, :craw, :rclean, :cclean, "
                    ":ctable, :qbefore, :qafter, :pdate, :created)"
                ),
                {
                    "name": display_name,
                    "orig": bundle.source.filename,
                    "fmt": bundle.source.source_format.value,
                    "sha": bundle.source.file_sha256,
                    "rraw": bundle.source.n_rows_raw,
                    "craw": bundle.source.n_cols_raw,
                    "rclean": bundle.clean.df.shape[0],
                    "cclean": bundle.clean.df.shape[1],
                    "ctable": placeholder,
                    "qbefore": json.dumps(_qs(bundle.clean.quality_before)),
                    "qafter": json.dumps(_qs(bundle.clean.quality_after)),
                    "pdate": bundle.profile.primary_date_col,
                    "created": datetime.now(timezone.utc).isoformat(),
                },
            )
            dataset_id: int = result.lastrowid  # type: ignore[assignment]

            # 2. Update clean_table to the real name
            clean_table = f"clean_{dataset_id}"
            conn.execute(
                text("UPDATE datasets SET clean_table = :ct WHERE id = :id"),
                {"ct": clean_table, "id": dataset_id},
            )

            # 3. Write cleaned data via pandas
            bundle.clean.df.to_sql(
                clean_table,
                conn,
                if_exists="fail",
                index=False,
            )

            # 4. Cleaning log
            for order, action in enumerate(bundle.clean.actions, start=1):
                conn.execute(
                    text(
                        "INSERT INTO cleaning_log "
                        "(dataset_id, step_order, step, column_name, description, rows_affected) "
                        "VALUES (:did, :ord, :step, :col, :desc, :rows)"
                    ),
                    {
                        "did": dataset_id,
                        "ord": order,
                        "step": action.step.value,
                        "col": action.column,
                        "desc": action.description,
                        "rows": action.rows_affected,
                    },
                )

            # 5. Column profiles
            for ordinal, cp in enumerate(bundle.profile.columns):
                stats_json: str | None = None
                if cp.numeric_stats:
                    stats_json = json.dumps(cp.numeric_stats)
                elif cp.top_values:
                    stats_json = json.dumps(cp.top_values)
                elif cp.date_range:
                    stats_json = json.dumps(list(cp.date_range))

                conn.execute(
                    text(
                        "INSERT INTO column_profiles "
                        "(dataset_id, ordinal, column_name, dtype, kind, n_missing, n_unique, stats) "
                        "VALUES (:did, :ord, :col, :dtype, :kind, :nm, :nu, :stats)"
                    ),
                    {
                        "did": dataset_id,
                        "ord": ordinal,
                        "col": cp.name,
                        "dtype": cp.dtype,
                        "kind": cp.kind.value,
                        "nm": cp.n_missing,
                        "nu": cp.n_unique,
                        "stats": stats_json,
                    },
                )

            # 6. Forecast run
            if bundle.forecast is not None:
                fc = bundle.forecast
                fc_list = [
                    {
                        "date": str(idx.isoformat()),
                        "forecast": float(row["forecast"]),
                        "lower": float(row["lower"]),
                        "upper": float(row["upper"]),
                    }
                    for idx, row in fc.forecast.iterrows()
                ]
                bt = fc.backtest
                conn.execute(
                    text(
                        "INSERT INTO forecast_runs "
                        "(dataset_id, date_column, target_column, agg, freq, horizon, "
                        "arima_p, arima_d, arima_q, aic, mae, rmse, mape, forecast, created_at) "
                        "VALUES (:did, :dc, :tc, :agg, :freq, :hor, :p, :d, :q, :aic, "
                        ":mae, :rmse, :mape, :fc, :created)"
                    ),
                    {
                        "did": dataset_id,
                        "dc": fc.params.date_col,
                        "tc": fc.params.target_col,
                        "agg": fc.params.agg,
                        "freq": fc.freq,
                        "hor": fc.params.horizon,
                        "p": fc.order[0],
                        "d": fc.order[1],
                        "q": fc.order[2],
                        "aic": fc.aic,
                        "mae": bt.mae if bt else None,
                        "rmse": bt.rmse if bt else None,
                        "mape": bt.mape if bt else None,
                        "fc": json.dumps(fc_list),
                        "created": datetime.now(timezone.utc).isoformat(),
                    },
                )

        _log.info("Saved dataset id=%d ('%s').", dataset_id, display_name)
        return dataset_id

    except Exception as exc:
        raise StorageError(
            f"Failed to save dataset: {exc}",
            detail=str(exc),
        ) from exc


def list_datasets(engine: Engine | None = None) -> list[DatasetRecord]:
    """Return summary records for all saved datasets, newest first."""
    eng = engine or get_engine()
    init_db(eng)

    try:
        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, name, original_filename, source_format, "
                    "n_rows_clean, n_cols_clean, created_at "
                    "FROM datasets ORDER BY created_at DESC"
                )
            ).fetchall()
    except Exception as exc:
        raise StorageError(f"Failed to list datasets: {exc}") from exc

    records: list[DatasetRecord] = []
    for row in rows:
        try:
            created = datetime.fromisoformat(str(row[6]))
        except Exception:
            created = datetime.now(timezone.utc)
        records.append(DatasetRecord(
            id=row[0],
            name=row[1],
            original_filename=row[2],
            source_format=row[3],
            n_rows_clean=row[4],
            n_cols_clean=row[5],
            created_at=created,
        ))
    return records


def load_clean_table(
    dataset_id: int,
    limit: int | None = None,
    engine: Engine | None = None,
) -> pd.DataFrame:
    """Load the cleaned data for *dataset_id* from SQLite.

    Raises :class:`StorageError` if the table does not exist.
    """
    eng = engine or get_engine()
    init_db(eng)

    clean_table = f"clean_{dataset_id}"
    if not _CLEAN_TABLE_RE.match(clean_table):
        raise StorageError(f"Invalid table name: {clean_table!r}")

    try:
        with eng.connect() as conn:
            sql = f"SELECT * FROM {clean_table}"  # noqa: S608 — name validated above
            if limit is not None:
                sql += f" LIMIT {int(limit)}"
            df = pd.read_sql(text(sql), conn)
    except Exception as exc:
        raise StorageError(f"Failed to load dataset {dataset_id}: {exc}") from exc

    return df


def delete_dataset(dataset_id: int, engine: Engine | None = None) -> None:
    """Delete the dataset and all related rows.  Drops the clean data table first.

    Raises :class:`StorageError` on any failure; transaction is rolled back.
    """
    eng = engine or get_engine()

    clean_table = f"clean_{dataset_id}"
    if not _CLEAN_TABLE_RE.match(clean_table):
        raise StorageError(f"Invalid table name: {clean_table!r}")

    try:
        with eng.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {clean_table}"))  # noqa: S608
            conn.execute(
                text("DELETE FROM datasets WHERE id = :id"),
                {"id": dataset_id},
            )
        _log.info("Deleted dataset id=%d.", dataset_id)
    except Exception as exc:
        raise StorageError(f"Failed to delete dataset {dataset_id}: {exc}") from exc

