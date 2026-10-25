from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from app.analytics.selection import (
    SelectionRequest,
    build_period_grid,
    describe_selection,
    select_forecasts,
)
from app.config.constants import CUTOFF_MODE_ABSOLUTE


def hour_forecast(start: datetime, publish: datetime, value: float) -> dict:
    return {
        "start_time_utc": pd.Timestamp(start),
        "publish_time_utc": pd.Timestamp(publish),
        "forecast_mw": value,
    }


def half_hourly_actuals(start: datetime, count: int, value: float) -> list[dict]:
    rows = []
    for index in range(count):
        rows.append(
            {
                "start_time_utc": pd.Timestamp(start + timedelta(minutes=30 * index)),
                "actual_mw": value + index,
                "publish_time_utc": pd.NaT,
                "settlement_date": "2026-01-01",
                "settlement_period": index + 1,
            }
        )
    return rows


def build_forecast_frame(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def build_actual_frame(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def test_latest_publication_at_or_before_cutoff_is_selected():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    forecasts = build_forecast_frame(
        [
            hour_forecast(start, datetime(2025, 12, 31, 6, 0, tzinfo=timezone.utc), 100.0),
            hour_forecast(start, datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 200.0),
            hour_forecast(start, datetime(2025, 12, 31, 18, 0, tzinfo=timezone.utc), 300.0),
        ]
    )
    actuals = build_actual_frame(half_hourly_actuals(start, 2, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(forecasts, actuals, request)
    first = result.frame.iloc[0]
    assert first["forecast_mw"] == pytest.approx(200.0)
    assert first["lead_hours"] == pytest.approx(12.0)


def test_forecasts_published_after_the_cutoff_are_excluded():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    forecasts = build_forecast_frame(
        [
            hour_forecast(start, datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 200.0),
            hour_forecast(start, datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc), 999.0),
        ]
    )
    actuals = build_actual_frame(half_hourly_actuals(start, 2, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(forecasts, actuals, request)
    assert result.frame.iloc[0]["forecast_mw"] == pytest.approx(200.0)
    assert not (result.frame["forecast_mw"] == 999.0).any()


def test_publication_exactly_at_the_cutoff_is_eligible():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    cutoff_publication = start - timedelta(hours=12)
    forecasts = build_forecast_frame([hour_forecast(start, cutoff_publication, 250.0)])
    actuals = build_actual_frame(half_hourly_actuals(start, 2, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(forecasts, actuals, request)
    assert result.frame.iloc[0]["forecast_mw"] == pytest.approx(250.0)
    assert result.frame.iloc[0]["status"] == "matched"


def test_periods_with_only_late_publications_are_flagged():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    forecasts = build_forecast_frame([hour_forecast(start, datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc), 900.0)])
    actuals = build_actual_frame(half_hourly_actuals(start, 2, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(forecasts, actuals, request)
    assert result.frame.iloc[0]["status"] == "missing_forecast"
    assert result.frame.iloc[0]["forecast_missing_reason"] == "published_after_cutoff"


def test_missing_forecast_is_reported_not_dropped():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    actuals = build_actual_frame(half_hourly_actuals(start, 4, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(build_forecast_frame([]), actuals, request)
    assert len(result.frame) == 48
    assert (result.frame["status"].iloc[:4] == "missing_forecast").all()
    assert (result.frame["status"].iloc[4:] == "missing_both").all()
    assert result.frame.iloc[0]["forecast_missing_reason"] == "no_publication_in_window"
    assert result.warnings


def test_missing_actual_is_reported_and_excluded_from_error():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    forecasts = build_forecast_frame([hour_forecast(start, datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 500.0)])
    actuals = build_actual_frame(half_hourly_actuals(start + timedelta(minutes=30), 2, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(forecasts, actuals, request)
    statuses = dict(zip(result.frame["time_label"], result.frame["status"]))
    assert statuses["00:00"] == "missing_actual"
    assert statuses["00:30"] == "matched"
    assert pd.isna(result.frame.iloc[0]["error_mw"])


def test_half_hourly_periods_match_the_containing_hourly_forecast():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    forecasts = build_forecast_frame(
        [
            hour_forecast(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 1000.0),
            hour_forecast(datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 2000.0),
        ]
    )
    actuals = build_actual_frame(half_hourly_actuals(start, 4, 150.0))
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)

    result = select_forecasts(forecasts, actuals, request)
    values = list(result.frame["forecast_mw"])
    assert values[0] == pytest.approx(1000.0)
    assert values[1] == pytest.approx(1000.0)
    assert values[2] == pytest.approx(2000.0)
    assert values[3] == pytest.approx(2000.0)


def test_fixed_cutoff_applies_one_instant_to_every_period():
    forecasts = build_forecast_frame(
        [
            hour_forecast(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 100.0),
            hour_forecast(datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc), datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 200.0),
            hour_forecast(datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc), datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc), 300.0),
        ]
    )
    actuals = build_actual_frame(half_hourly_actuals(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), 6, 150.0))
    cutoff = datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc)
    request = SelectionRequest(
        start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), mode=CUTOFF_MODE_ABSOLUTE, cutoff=cutoff
    )

    result = select_forecasts(forecasts, actuals, request)
    assert result.matched_count == 6
    assert set(result.frame["cutoff_local"].dropna()) == {cutoff.astimezone(timezone.utc).isoformat()}


def test_period_grid_has_48_periods_on_a_standard_local_day():
    grid = build_period_grid(date(2026, 1, 15), date(2026, 1, 15))
    assert len(grid) == 48
    assert grid.iloc[0]["time_label"] == "00:00"
    assert grid.iloc[-1]["time_label"] == "23:30"


def test_period_grid_respects_daylight_saving_transitions():
    spring_forward = build_period_grid(date(2026, 3, 29), date(2026, 3, 29))
    autumn_back = build_period_grid(date(2026, 10, 25), date(2026, 10, 25))
    assert len(spring_forward) == 46
    assert len(autumn_back) == 50


def test_period_grid_spans_multiple_days():
    grid = build_period_grid(date(2026, 1, 1), date(2026, 1, 3))
    assert len(grid) == 144
    assert set(grid["delivery_date_local"]) == {"2026-01-01", "2026-01-02", "2026-01-03"}


def test_empty_actual_and_forecast_frames_produce_full_missing_report():
    request = SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12)
    result = select_forecasts(pd.DataFrame(), pd.DataFrame(), request)
    assert len(result.frame) == 48
    assert result.matched_count == 0
    assert (result.frame["status"] == "missing_both").all()


def test_invalid_selection_requests_are_rejected():
    with pytest.raises(ValueError):
        SelectionRequest(start_day=date(2026, 1, 2), end_day=date(2026, 1, 1), lead_hours=12).validate()
    with pytest.raises(ValueError):
        SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=0).validate()
    with pytest.raises(ValueError):
        SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), mode=CUTOFF_MODE_ABSOLUTE).validate()


def test_selection_description_discloses_cutoff_semantics():
    rolling = describe_selection(SelectionRequest(start_day=date(2026, 1, 1), end_day=date(2026, 1, 1), lead_hours=12))
    assert "not an official market deadline" in rolling["description"]

    fixed = describe_selection(
        SelectionRequest(
            start_day=date(2026, 1, 1),
            end_day=date(2026, 1, 1),
            mode=CUTOFF_MODE_ABSOLUTE,
            cutoff=datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc),
        )
    )
    assert fixed["mode"] == CUTOFF_MODE_ABSOLUTE
    assert fixed["cutoff_local"] is not None
