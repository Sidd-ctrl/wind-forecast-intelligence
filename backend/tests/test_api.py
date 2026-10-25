from __future__ import annotations

import csv
import io

import pytest


def test_health_reports_mode_and_window(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_mode"] == "sample"
    assert payload["analysis_start_date"] == "2026-01-01"


def test_metadata_lists_analysis_dates_and_definitions(api_client):
    response = api_client.get("/api/metadata")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["analysis_dates"]) == 31
    assert payload["analysis_dates"][0] == "2026-01-01"
    assert payload["analysis_dates"][-1] == "2026-01-31"
    assert "wape" in payload["metric_definitions"]
    assert payload["meta"]["unit"] == "MW"
    assert payload["meta"]["data_mode"] == "sample"


def test_overview_returns_validated_metrics_matching_the_series(api_client):
    response = api_client.get("/api/overview", params={"delivery_date": "2026-01-15", "lead_hours": 12})
    assert response.status_code == 200
    payload = response.json()

    assert len(payload["series"]) == 48
    assert payload["quality"]["periods_total"] == 48
    assert payload["metrics"]["n_observations"] == payload["quality"]["matched"]

    matched = [point for point in payload["series"] if point["status"] == "matched"]
    errors = [abs(point["error_mw"]) for point in matched]
    expected_mae = sum(errors) / len(errors)
    assert payload["metrics"]["mae_mw"] == pytest.approx(expected_mae, rel=1e-6)
    assert payload["metrics"]["bias_mw"] == pytest.approx(
        sum(point["error_mw"] for point in matched) / len(matched), rel=1e-6
    )
    assert payload["largest_error"]["abs_error_mw"] == pytest.approx(max(errors))


def test_overview_flags_sample_mode(api_client):
    payload = api_client.get("/api/overview", params={"delivery_date": "2026-01-15"}).json()
    assert payload["meta"]["data_mode"] == "sample"
    assert any("SAMPLE DATA MODE" in warning for warning in payload["quality"]["warnings"])


def test_fixed_cutoff_mode_returns_selection_metadata(api_client):
    response = api_client.get(
        "/api/overview",
        params={"delivery_date": "2026-01-15", "mode": "absolute_cutoff", "cutoff": "2026-01-14T09:00:00Z"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["selection"]["mode"] == "absolute_cutoff"
    assert payload["selection"]["cutoff_local"].startswith("2026-01-14T09:00:00")
    for point in payload["series"]:
        if point["forecast_publish_local"]:
            assert point["forecast_publish_local"] <= payload["selection"]["cutoff_local"].replace("+00:00", "+00:00")


def test_forecast_endpoint_filters_by_status(api_client):
    response = api_client.get("/api/forecast", params={"delivery_date": "2026-01-15", "lead_hours": 96})
    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == len(payload["rows"])
    assert payload["quality"]["missing_forecast"] > 0

    filtered = api_client.get(
        "/api/forecast", params={"delivery_date": "2026-01-15", "lead_hours": 96, "status": "missing_forecast"}
    ).json()
    assert all(row["status"] == "missing_forecast" for row in filtered["rows"])
    assert filtered["row_count"] == payload["quality"]["missing_forecast"]


def test_forecast_endpoint_filters_by_direction(api_client):
    payload = api_client.get(
        "/api/forecast", params={"delivery_date": "2026-01-15", "direction": "underforecast"}
    ).json()
    assert all(row["direction"] == "underforecast" for row in payload["rows"])


def test_accuracy_histogram_and_direction_agree_with_counts(api_client):
    payload = api_client.get("/api/accuracy", params={"delivery_date": "2026-01-15"}).json()
    assert sum(bin_["count"] for bin_ in payload["histogram"]) == payload["metrics"]["n_observations"]
    assert payload["direction"]["overforecast"] == payload["metrics"]["overforecast_count"]
    assert payload["direction"]["underforecast"] == payload["metrics"]["underforecast_count"]


def test_compare_uses_common_observations(api_client):
    response = api_client.get(
        "/api/accuracy/compare", params={"delivery_date": "2026-01-15", "lead_hours": [12, 24]}
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["entries"]) == 2
    assert payload["common_period_count"] > 0
    for entry in payload["entries"]:
        assert entry["n_common"] == payload["common_period_count"]
    for metric in payload["common_metrics"]:
        assert metric["n_observations"] == payload["common_period_count"]


def test_provenance_reports_consistent_counts(api_client):
    payload = api_client.get("/api/provenance", params={"delivery_date": "2026-01-15"}).json()
    counts = payload["counts"]
    assert counts["actual_records_used"] == 1488
    assert counts["forecast_records_used"] > 0
    assert counts["matched_observations"] == 48
    assert payload["sources"][0]["dataset"] == "FUELHH"
    assert payload["sources"][1]["dataset"] == "WINDFOR"
    assert payload["cache"]["status"] == "disabled"
    assert payload["coverage"]["latest_forecast_publication"] is not None


def test_csv_export_contains_all_rows_and_headers(api_client):
    response = api_client.get("/api/data/records/export.csv", params={"delivery_date": "2026-01-15"})
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 48
    assert rows[0]["delivery_local"].startswith("2026-01-15")
    assert rows[0]["status"] in {"matched", "missing_forecast", "missing_actual", "missing_both"}
    assert set(rows[0].keys()) >= {"forecast_mw", "actual_mw", "error_mw", "lead_hours"}


def test_records_endpoint_matches_csv_row_count(api_client):
    records = api_client.get("/api/data/records", params={"delivery_date": "2026-01-15"}).json()
    csv_response = api_client.get("/api/data/records/export.csv", params={"delivery_date": "2026-01-15"})
    assert records["row_count"] == len(list(csv.DictReader(io.StringIO(csv_response.text))))


def test_invalid_delivery_date_returns_structured_error(api_client):
    response = api_client.get("/api/overview", params={"delivery_date": "2026-13-01"})
    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "analysis_error"
    assert "yyyy-MM-dd" in payload["error"]["message"]


def test_dates_outside_the_analysis_window_are_rejected(api_client):
    response = api_client.get("/api/overview", params={"delivery_date": "2026-02-05"})
    assert response.status_code == 400
    assert "outside the January 2026" in response.json()["error"]["message"]


def test_negative_lead_hours_are_rejected(api_client):
    response = api_client.get("/api/overview", params={"delivery_date": "2026-01-15", "lead_hours": -3})
    assert response.status_code == 400
    assert "lead_hours" in response.json()["error"]["message"]


def test_absolute_cutoff_mode_requires_a_cutoff(api_client):
    response = api_client.get("/api/overview", params={"delivery_date": "2026-01-15", "mode": "absolute_cutoff"})
    assert response.status_code == 400
    assert "cutoff is required" in response.json()["error"]["message"]


def test_unknown_mode_is_rejected(api_client):
    response = api_client.get("/api/overview", params={"delivery_date": "2026-01-15", "mode": "nonsense"})
    assert response.status_code == 400


def test_refresh_returns_new_snapshot_summary(api_client):
    response = api_client.post("/api/data/refresh", params={"delivery_date": "2026-01-15"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refreshed"
    assert payload["counts"]["actual_records_used"] == 1488


def test_month_range_is_supported(api_client):
    payload = api_client.get("/api/overview", params={"start_date": "2026-01-01", "end_date": "2026-01-31"}).json()
    assert payload["quality"]["periods_total"] == 1488
    assert payload["metrics"]["n_observations"] > 1400
