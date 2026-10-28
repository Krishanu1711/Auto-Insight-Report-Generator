import json
import time

import pytest
from fastapi.testclient import TestClient

import server
from src.database import get_engine, init_db


def _make_forecastable_csv() -> bytes:
    rows = [
        "order_id,order_date,region,sales,quantity,profit",
        "1,2023-01-01,East,100,2,20",
        "2,2023-02-01,West,120,3,25",
        "3,2023-03-01,East,130,2,27",
        "4,2023-04-01,North,140,2,28",
        "5,2023-05-01,South,150,4,30",
        "6,2023-06-01,East,160,3,35",
        "7,2023-07-01,West,170,2,38",
        "8,2023-08-01,North,180,3,40",
        "9,2023-09-01,East,190,1,42",
        "10,2023-10-01,South,200,5,45",
        "11,2023-11-01,East,210,3,48",
        "12,2023-12-01,West,220,2,50",
        "13,2024-01-01,North,230,3,52",
        "14,2024-02-01,South,240,4,55",
        "15,2024-03-01,East,250,3,58",
    ]
    return "\n".join(rows).encode("utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = get_engine(str(tmp_path / "api_test.db"))
    init_db(engine)
    monkeypatch.setattr(server, "_engine", engine)
    with server._lock:
        server._sessions.clear()
        server._jobs.clear()
    with TestClient(server.app) as test_client:
        yield test_client
    with server._lock:
        server._sessions.clear()
        server._jobs.clear()


def test_session_starts_empty(client: TestClient):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.json() == {"bundle": None}
    assert server.SESSION_COOKIE_NAME in response.cookies


def test_api_errors_use_frontend_friendly_shape(client: TestClient):
    report_response = client.post("/api/report", json={})
    assert report_response.status_code == 409
    assert report_response.json()["error"] == "No active dataset available to generate report."

    validation_response = client.post("/api/forecast", json={})
    assert validation_response.status_code == 422
    assert "error" in validation_response.json()


def test_api_analysis_forecast_and_persistence_flow(client: TestClient):
    analyze_response = client.post(
        "/api/analyze",
        files={"file": ("orders.csv", _make_forecastable_csv(), "text/csv")},
        data={
            "options": json.dumps(
                {
                    "outlierTreatment": "flag",
                    "missingThreshold": 0.6,
                    "autoForecast": False,
                }
            )
        },
    )
    assert analyze_response.status_code == 202
    job_id = analyze_response.json()["jobId"]

    final_job = None
    for _ in range(200):
        job_response = client.get(f"/api/jobs/{job_id}")
        assert job_response.status_code == 200
        final_job = job_response.json()
        if final_job["status"] in {"complete", "error"}:
            break
        time.sleep(0.05)

    assert final_job is not None
    assert final_job["status"] == "complete", final_job

    session_response = client.get("/api/session")
    bundle = session_response.json()["bundle"]
    assert bundle is not None
    assert bundle["source"]["filename"] == "orders.csv"
    assert bundle["analysis"]["descriptive"] is not None
    assert len(bundle["charts"]) > 0

    forecast_response = client.post(
        "/api/forecast",
        json={
            "dateColumn": "order_date",
            "targetColumn": "sales",
            "aggregation": "sum",
            "horizon": 3,
            "decompositionModel": "additive",
        },
    )
    assert forecast_response.status_code == 200
    forecast_bundle = forecast_response.json()["bundle"]
    assert forecast_bundle["forecast"] is not None
    assert len(forecast_bundle["forecastCharts"]) > 0

    report_response = client.post("/api/report", json={})
    assert report_response.status_code == 200
    assert "text/html" in report_response.headers["content-type"]
    assert "attachment; filename=\"insight_report.html\"" == report_response.headers["content-disposition"]

    clean_csv_response = client.get("/api/download/clean.csv")
    assert clean_csv_response.status_code == 200
    assert "text/csv" in clean_csv_response.headers["content-type"]

    ml_ready_response = client.get("/api/download/ml-ready.csv")
    assert ml_ready_response.status_code == 200
    assert "text/csv" in ml_ready_response.headers["content-type"]

    save_response = client.post("/api/save", json={"name": "API Smoke Test"})
    assert save_response.status_code == 201
    dataset_id = save_response.json()["datasetId"]

    saved_response = client.get("/api/saved")
    assert saved_response.status_code == 200
    datasets = saved_response.json()["datasets"]
    assert any(dataset["id"] == dataset_id for dataset in datasets)

    preview_response = client.get(f"/api/saved/{dataset_id}?limit=5")
    assert preview_response.status_code == 200
    assert preview_response.json()["data"]["totalRows"] >= 5

    saved_csv_response = client.get(f"/api/saved/{dataset_id}/csv")
    assert saved_csv_response.status_code == 200
    assert "text/csv" in saved_csv_response.headers["content-type"]

    delete_response = client.delete(f"/api/saved/{dataset_id}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"ok": True}
