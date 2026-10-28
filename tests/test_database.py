"""tests/test_database.py"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.database import delete_dataset, get_engine, init_db, list_datasets, load_clean_table, save_bundle
from src.exceptions import StorageError


@pytest.fixture
def tmp_engine():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    engine = get_engine(db_path)
    init_db(engine)
    yield engine
    engine.dispose()
    Path(db_path).unlink(missing_ok=True)


def test_save_and_list(tmp_engine, sample_bundle):
    dataset_id = save_bundle(sample_bundle, name="Test Dataset", engine=tmp_engine)
    assert isinstance(dataset_id, int)
    assert dataset_id > 0

    records = list_datasets(engine=tmp_engine)
    assert len(records) == 1
    assert records[0].name == "Test Dataset"
    assert records[0].id == dataset_id


def test_load_clean_table(tmp_engine, sample_bundle):
    dataset_id = save_bundle(sample_bundle, engine=tmp_engine)
    df = load_clean_table(dataset_id, limit=10, engine=tmp_engine)
    assert isinstance(df, pd.DataFrame)
    assert len(df) <= 10


def test_delete_dataset(tmp_engine, sample_bundle):
    dataset_id = save_bundle(sample_bundle, engine=tmp_engine)
    delete_dataset(dataset_id, engine=tmp_engine)
    records = list_datasets(engine=tmp_engine)
    assert len(records) == 0


def test_delete_cascade(tmp_engine, sample_bundle):
    """Deleting a dataset should cascade to child rows and the clean table."""
    dataset_id = save_bundle(sample_bundle, engine=tmp_engine)
    delete_dataset(dataset_id, engine=tmp_engine)
    # clean table should not exist
    with pytest.raises(Exception):
        load_clean_table(dataset_id, engine=tmp_engine)


def test_save_multiple(tmp_engine, sample_bundle):
    id1 = save_bundle(sample_bundle, name="First", engine=tmp_engine)
    id2 = save_bundle(sample_bundle, name="Second", engine=tmp_engine)
    assert id1 != id2
    records = list_datasets(engine=tmp_engine)
    assert len(records) == 2


def test_invalid_table_name(tmp_engine):
    with pytest.raises(StorageError):
        # Passing an invalid or SQL-injection string as dataset_id should raise StorageError
        load_clean_table("1; DROP TABLE datasets; --", engine=tmp_engine)

