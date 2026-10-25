from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.normalize import normalize_actuals, normalize_forecasts


def test_actuals_are_filtered_to_wind(sample_raw_actuals):
    result = normalize_actuals(sample_raw_actuals)
    assert len(result.frame) == 1
    assert result.report.dropped_wrong_fuel_type == 1
    assert result.frame.iloc[0]["actual_mw"] == pytest.approx(12000.0)


def test_actual_timestamps_are_normalised_to_utc(sample_raw_actuals):
    result = normalize_actuals(sample_raw_actuals)
    assert str(result.frame.iloc[0]["start_time_utc"]) == "2026-01-01 00:00:00+00:00"
    assert result.frame["start_time_utc"].dt.tz is not None


def test_actuals_with_offset_timestamps_are_converted_to_utc():
    records = [
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T01:00:00+01:00",
            "startTime": "2026-01-01T00:00:00+01:00",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 1,
            "fuelType": "WIND",
            "generation": 5000,
        }
    ]
    result = normalize_actuals(records)
    assert str(result.frame.iloc[0]["start_time_utc"]) == "2025-12-31 23:00:00+00:00"


def test_actuals_drop_duplicate_start_times():
    records = [
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z", "fuelType": "WIND", "generation": 100},
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z", "fuelType": "WIND", "generation": 100},
        {"startTime": "2026-01-01T00:30:00Z", "publishTime": "2026-01-01T01:00:00Z", "fuelType": "WIND", "generation": 200},
    ]
    result = normalize_actuals(records)
    assert len(result.frame) == 2
    assert result.report.duplicates_removed == 1


def test_actuals_drop_invalid_generation_without_using_zero():
    records = [
        {"startTime": "2026-01-01T00:00:00Z", "publishTime": "2026-01-01T00:30:00Z", "fuelType": "WIND", "generation": None},
        {"startTime": "2026-01-01T00:30:00Z", "publishTime": "2026-01-01T01:00:00Z", "fuelType": "WIND", "generation": "not-a-number"},
        {"startTime": "2026-01-01T01:00:00Z", "publishTime": "2026-01-01T01:30:00Z", "fuelType": "WIND", "generation": 4500},
    ]
    result = normalize_actuals(records)
    assert len(result.frame) == 1
    assert result.report.dropped_invalid_generation == 2
    assert result.frame.iloc[0]["actual_mw"] == pytest.approx(4500.0)


def test_actuals_without_records_return_empty_frame():
    result = normalize_actuals([])
    assert result.frame.empty
    assert result.report.warnings


def test_forecasts_keep_every_publication_for_the_same_delivery_period(sample_raw_forecasts):
    result = normalize_forecasts(sample_raw_forecasts)
    first_hour = result.frame[result.frame["start_time_utc"] == pd.Timestamp("2026-01-01T00:00:00Z")]
    assert len(first_hour) == 3


def test_forecast_duplicates_are_removed():
    records = [
        {"publishTime": "2025-12-31T12:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 100},
        {"publishTime": "2025-12-31T12:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 100},
    ]
    result = normalize_forecasts(records)
    assert len(result.frame) == 1
    assert result.report.duplicates_removed == 1


def test_forecasts_missing_publish_time_are_rejected():
    records = [{"startTime": "2026-01-01T00:00:00Z", "generation": 100}]
    result = normalize_forecasts(records)
    assert result.frame.empty
    assert result.report.errors


def test_forecasts_with_invalid_timestamps_are_dropped():
    records = [
        {"publishTime": "not-a-time", "startTime": "2026-01-01T00:00:00Z", "generation": 100},
        {"publishTime": "2025-12-31T12:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 200},
    ]
    result = normalize_forecasts(records)
    assert len(result.frame) == 1
    assert result.report.dropped_invalid_timestamp == 1


def test_negative_generation_is_retained_and_flagged():
    records = [{"publishTime": "2025-12-31T12:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": -120}]
    result = normalize_forecasts(records)
    assert len(result.frame) == 1
    assert result.report.negative_values == 1
    assert result.report.warnings
