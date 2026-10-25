from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.metrics import (
    common_observation_frame,
    compute_metrics,
    direction_split,
    error_histogram,
    largest_absolute_error,
    safe_wape,
)


def test_mae_matches_manual_calculation(metrics_frame):
    metrics = compute_metrics(metrics_frame)
    assert metrics.mae_mw == pytest.approx(10.0)
    assert metrics.n_observations == 4


def test_rmse_matches_manual_calculation(metrics_frame):
    metrics = compute_metrics(metrics_frame)
    assert metrics.rmse_mw == pytest.approx(12.24744871391589)


def test_bias_keeps_the_sign_of_the_net_error(metrics_frame):
    metrics = compute_metrics(metrics_frame)
    assert metrics.bias_mw == pytest.approx(5.0)


def test_bias_is_positive_when_forecast_runs_high():
    frame = pd.DataFrame(
        {
            "status": ["matched", "matched"],
            "forecast_mw": [120.0, 130.0],
            "actual_mw": [100.0, 100.0],
            "error_mw": [20.0, 30.0],
            "abs_error_mw": [20.0, 30.0],
        }
    )
    metrics = compute_metrics(frame)
    assert metrics.bias_mw == pytest.approx(25.0)
    assert metrics.overforecast_count == 2
    assert metrics.underforecast_count == 0


def test_wape_uses_absolute_error_over_actual_generation(metrics_frame):
    metrics = compute_metrics(metrics_frame)
    assert metrics.wape_pct == pytest.approx(40.0 / 400.0 * 100.0)


def test_wape_returns_none_when_actual_sum_is_zero():
    assert safe_wape(100.0, 0.0) is None
    frame = pd.DataFrame(
        {
            "status": ["matched", "matched"],
            "forecast_mw": [50.0, 50.0],
            "actual_mw": [0.0, 0.0],
            "error_mw": [50.0, 50.0],
            "abs_error_mw": [50.0, 50.0],
        }
    )
    metrics = compute_metrics(frame)
    assert metrics.wape_pct is None
    assert metrics.mae_mw == pytest.approx(50.0)
    assert any("WAPE is undefined" in note for note in metrics.notes)


def test_metrics_ignore_rows_without_matched_error():
    frame = pd.DataFrame(
        {
            "status": ["matched", "missing_actual", "missing_forecast"],
            "forecast_mw": [110.0, 200.0, None],
            "actual_mw": [100.0, None, 120.0],
            "error_mw": [10.0, None, None],
            "abs_error_mw": [10.0, None, None],
        }
    )
    metrics = compute_metrics(frame)
    assert metrics.n_observations == 1
    assert metrics.mae_mw == pytest.approx(10.0)
    assert metrics.missing_actual == 1
    assert metrics.missing_forecast == 1
    assert metrics.periods_total == 3


def test_missing_actuals_are_not_treated_as_zero():
    frame = pd.DataFrame(
        {
            "status": ["matched", "missing_actual"],
            "forecast_mw": [100.0, 9000.0],
            "actual_mw": [100.0, None],
            "error_mw": [0.0, None],
            "abs_error_mw": [0.0, None],
        }
    )
    metrics = compute_metrics(frame)
    assert metrics.mean_actual_mw == pytest.approx(100.0)
    assert metrics.bias_mw == pytest.approx(0.0)


def test_empty_frame_returns_null_metrics():
    metrics = compute_metrics(pd.DataFrame())
    assert metrics.n_observations == 0
    assert metrics.mae_mw is None
    assert metrics.rmse_mw is None
    assert metrics.bias_mw is None
    assert metrics.wape_pct is None
    assert metrics.notes


def test_overforecast_percentage_is_computed_from_matched_rows(metrics_frame):
    metrics = compute_metrics(metrics_frame)
    assert metrics.overforecast_pct == pytest.approx(50.0)
    assert metrics.underforecast_count == 1
    assert metrics.exact_count == 1


def test_direction_split_counts_all_three_cases(metrics_frame):
    split = direction_split(metrics_frame)
    assert split == {"overforecast": 2, "underforecast": 1, "exact": 1}


def test_histogram_bins_cover_every_absolute_error(metrics_frame):
    bins = error_histogram(metrics_frame, bins=4)
    assert sum(item["count"] for item in bins) == 4


def test_histogram_is_empty_without_data():
    assert error_histogram(pd.DataFrame()) == []


def test_largest_absolute_error_reports_signed_and_unsigned_values():
    frame = pd.DataFrame(
        {
            "status": ["matched", "matched"],
            "delivery_local": ["2026-01-01 00:00", "2026-01-01 00:30"],
            "delivery_utc": ["2026-01-01T00:00:00Z", "2026-01-01T00:30:00Z"],
            "period_index": [1, 2],
            "forecast_mw": [120.0, 60.0],
            "actual_mw": [100.0, 100.0],
            "error_mw": [20.0, -40.0],
            "abs_error_mw": [20.0, 40.0],
            "direction": ["overforecast", "underforecast"],
            "forecast_publish_local": ["2025-12-31T12:00:00+00:00", "2025-12-31T12:00:00+00:00"],
            "lead_hours": [12.0, 12.5],
        }
    )
    largest = largest_absolute_error(frame)
    assert largest["abs_error_mw"] == pytest.approx(40.0)
    assert largest["error_mw"] == pytest.approx(-40.0)
    assert largest["direction"] == "underforecast"


def test_common_observation_frame_uses_intersection():
    def frame(mapping):
        rows = []
        for index, (period, error) in enumerate(mapping.items()):
            rows.append(
                {
                    "period_start_utc": pd.Timestamp(period),
                    "status": "matched",
                    "error_mw": error,
                    "abs_error_mw": abs(error),
                    "forecast_mw": 100.0,
                    "actual_mw": 100.0 - error,
                }
            )
        return pd.DataFrame(rows)

    left = frame({"2026-01-01T00:00Z": 5.0, "2026-01-01T00:30Z": 7.0, "2026-01-01T01:00Z": 9.0})
    right = frame({"2026-01-01T00:30Z": 1.0, "2026-01-01T01:00Z": 2.0, "2026-01-01T01:30Z": 3.0})
    left_common, right_common = common_observation_frame(left, right)
    assert len(left_common) == 2
    assert len(right_common) == 2
    assert set(left_common["period_start_utc"]) == set(right_common["period_start_utc"])


def test_common_observation_frame_handles_empty_input():
    left, right = common_observation_frame(pd.DataFrame(), pd.DataFrame())
    assert left.empty and right.empty
