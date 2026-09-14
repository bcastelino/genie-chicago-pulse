"""Neighborhood + Data Health API contract tests (mock provider)."""


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True


def test_list_neighborhoods(client):
    body = client.get("/api/neighborhoods").json()
    assert len(body) >= 10
    assert {"community_area", "community_area_name"} <= set(body[0].keys())


def test_pulse_returns_metrics_and_trend(client):
    body = client.get("/api/neighborhoods/25/pulse").json()
    assert body["community_area"] == 25
    assert body["reporting_period_label"]
    keys = {m["key"] for m in body["metrics"]}
    assert "total_311_requests" in keys
    assert len(body["trend_311"]) == 12
    assert len(body["top_service_types"]) >= 1


def test_pulse_marks_unavailable_data_as_na():
    # O'Hare fixture has business/permit data unavailable -> available False, value None.
    from fastapi.testclient import TestClient

    from server.deps import reset_caches
    from server.main import app

    reset_caches()
    c = TestClient(app)
    body = c.get("/api/neighborhoods/76/pulse").json()
    biz = next(m for m in body["metrics"] if m["key"] == "business_license_issues")
    assert biz["available"] is False
    assert biz["value"] is None


def test_invalid_neighborhood_rejected(client):
    assert client.get("/api/neighborhoods/999/pulse").status_code == 422


def test_compare_valid(client):
    body = client.get("/api/neighborhoods/compare?areas=25,6,76").json()
    assert len(body["neighborhoods"]) == 3
    assert body["metric_keys"]


def test_compare_invalid_area_rejected(client):
    assert client.get("/api/neighborhoods/compare?areas=25,999").status_code == 422


def test_compare_too_many_rejected(client):
    assert client.get("/api/neighborhoods/compare?areas=1,2,3,4,6").status_code == 422


def test_geo_feature_collection(client):
    body = client.get("/api/neighborhoods/geo").json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) >= 10
    assert body["features"][0]["geometry"]["type"] == "Polygon"


def test_map_metric(client):
    body = client.get("/api/neighborhoods/map").json()
    assert body["metric_label"] == "311 Requests"
    assert len(body["values"]) >= 10


def test_data_health(client):
    body = client.get("/api/data-health").json()
    assert body["pipeline_status"] == "operational"
    assert body["last_refresh_at"] == "2024-07-01T06:20:00.000Z"
    assert len(body["datasets"]) == 8
    ds = {d["dataset"]: d for d in body["datasets"]}
    assert ds["311 Service Requests"]["socrata_id"] == "v6vf-nfxy"
    assert ds["311 Service Requests"]["usage_status"] == "in_use"
    assert ds["311 Service Requests"]["source_url"].endswith("/d/v6vf-nfxy")
    assert ds["311 Service Requests"]["last_ingested_at"] == "2024-07-01T06:12:00.000Z"
    assert ds["Food Inspections"]["usage_status"] == "future_scope"
    assert ds["Food Inspections"]["socrata_id"] == "4ijn-s7e5"
    assert ds["Food Inspections"]["row_count"] is None
    assert ds["Crimes - 2001 to Present"]["usage_status"] == "future_scope"
    assert body["metric_explanation"]
    assert body["source_notice"]


def test_pipeline_run_can_be_triggered_and_polled(client):
    started = client.post("/api/data-health/pipeline-runs")
    assert started.status_code == 200
    body = started.json()
    assert body["run_id"] == 424242
    assert body["life_cycle_state"] == "PENDING"
    assert body["started_new"] is True

    states = []
    completed = None
    for _ in range(4):
        completed = client.get(f"/api/data-health/pipeline-runs/{body['run_id']}")
        assert completed.status_code == 200
        states.append(completed.json()["life_cycle_state"])
    assert states[:3] == ["RUNNING", "RUNNING", "RUNNING"]
    assert completed is not None
    assert completed.status_code == 200
    assert completed.json()["life_cycle_state"] == "TERMINATED"
    assert completed.json()["result_state"] == "SUCCESS"
    assert [task["task_key"] for task in completed.json()["tasks"]] == [
        "incremental_ingestion",
        "transform_refresh",
        "validation",
    ]


def test_unknown_pipeline_run_is_not_exposed(client):
    response = client.get("/api/data-health/pipeline-runs/999")
    assert response.status_code == 404


def test_invalid_pipeline_run_id_is_rejected(client):
    response = client.get("/api/data-health/pipeline-runs/0")
    assert response.status_code == 422
