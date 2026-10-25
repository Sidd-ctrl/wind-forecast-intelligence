from __future__ import annotations

import json
from datetime import date, datetime, timezone

import httpx
import pytest

from app.config.settings import Settings
from app.services.elexon_client import (
    ElexonClient,
    ElexonUnavailableError,
    ElexonValidationError,
)


def build_settings(**overrides) -> Settings:
    base = {
        "elexon_base_url": "https://data.elexon.co.uk/bmrs/api/v1",
        "elexon_timeout_seconds": 5.0,
        "elexon_max_retries": 3,
        "elexon_retry_backoff_seconds": 0.0,
        "elexon_max_chunk_days": 7,
        "data_mode": "live",
    }
    base.update(overrides)
    return Settings(**base)


def test_actual_retrieval_is_chunked_under_the_seven_day_limit():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(dict(request.url.params))
        return httpx.Response(200, json={"data": [{"startTime": "2026-01-01T00:00:00Z", "generation": 1, "fuelType": "WIND"}]})

    client = ElexonClient(build_settings(), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 31))

    assert len(captured) == 5
    assert result.failures == []
    for params in captured:
        start = date.fromisoformat(params["settlementDateFrom"])
        end = date.fromisoformat(params["settlementDateTo"])
        assert (end - start).days <= 6
        assert params["fuelType"] == "WIND"


def test_forecast_retrieval_uses_publish_window_parameters():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(dict(request.url.params))
        return httpx.Response(200, json={"data": []})

    client = ElexonClient(build_settings(), transport=httpx.MockTransport(handler))
    client.fetch_forecast_wind(
        datetime(2025, 12, 25, tzinfo=timezone.utc),
        datetime(2026, 2, 2, tzinfo=timezone.utc),
    )

    assert len(captured) == 6
    assert all("publishDateTimeFrom" in params and "publishDateTimeTo" in params for params in captured)
    assert all("from" != key for params in captured for key in params)


def test_transient_server_errors_are_retried():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"data": [{"startTime": "2026-01-01T00:00:00Z", "generation": 1}]})

    client = ElexonClient(build_settings(), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert attempts["count"] == 3
    assert len(result.records) == 1


def test_persistent_server_errors_are_reported_as_partial_retrieval():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = ElexonClient(build_settings(elexon_max_retries=2), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 3))
    assert result.partial is True
    assert result.records == []
    assert all("error" in failure for failure in result.failures)


def test_client_error_is_recorded_as_a_partial_retrieval_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"title": "bad request"})

    client = ElexonClient(build_settings(), transport=httpx.MockTransport(handler))
    result = client.fetch_forecast_wind(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
    assert result.partial is True
    assert result.records == []
    assert any("rejected" in failure["error"] for failure in result.failures)


def test_non_json_response_is_recorded_as_a_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    client = ElexonClient(build_settings(elexon_max_retries=1), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert result.partial is True
    assert any("non-JSON" in failure["error"] for failure in result.failures)


def test_unexpected_envelope_is_recorded_as_a_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"rows": []})

    client = ElexonClient(build_settings(elexon_max_retries=1), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert result.partial is True
    assert any("envelope" in failure["error"] for failure in result.failures)


def test_validation_error_type_is_used_for_client_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"title": "bad request"})

    client = ElexonClient(build_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(ElexonValidationError):
        with client._client() as http_client:
            client._request(http_client, "/datasets/FUELHH", {"settlementDateFrom": "2026-01-01"})


def test_bare_list_payload_is_accepted():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps([{"startTime": "2026-01-01T00:00:00Z", "generation": 5}]))

    client = ElexonClient(build_settings(), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert len(result.records) == 1


def test_exhausted_retries_surface_an_unavailable_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    client = ElexonClient(build_settings(elexon_max_retries=2), transport=httpx.MockTransport(handler))
    result = client.fetch_actual_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert result.partial is True
    assert any("did not respond" in failure["error"] for failure in result.failures)


def test_unavailable_error_type_is_raised_after_exhausted_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    client = ElexonClient(build_settings(elexon_max_retries=2), transport=httpx.MockTransport(handler))
    with pytest.raises(ElexonUnavailableError):
        with client._client() as http_client:
            client._request(http_client, "/datasets/FUELHH", {"settlementDateFrom": "2026-01-01"})
