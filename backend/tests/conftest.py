from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

os.environ.setdefault("DATA_MODE", "sample")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("CACHE_DIR", "/tmp/aeron-test-cache")

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


@pytest.fixture
def forecast_frame() -> pd.DataFrame:
    records = []
    for hour in range(0, 6):
        published = []
        for publish_hour in range(0, 8):
            published.append(
                {
                    "start_time_utc": pd.Timestamp(utc(2026, 1, 1, hour)),
                    "publish_time_utc": pd.Timestamp(utc(2025, 12, 31, publish_hour)),
                    "forecast_mw": 1000.0 + hour * 10 + publish_hour,
                }
            )
        records.extend(published)
    return pd.DataFrame(records)


@pytest.fixture
def actual_frame() -> pd.DataFrame:
    rows = []
    for hour in range(0, 6):
        for half in (0, 30):
            start = utc(2026, 1, 1, hour, half)
            rows.append(
                {
                    "start_time_utc": pd.Timestamp(start),
                    "actual_mw": 900.0 + hour,
                    "publish_time_utc": pd.NaT,
                    "settlement_date": "2026-01-01",
                    "settlement_period": hour * 2 + (1 if half == 0 else 2),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def metrics_frame() -> pd.DataFrame:
    def build(rows):
        frame = pd.DataFrame(rows)
        frame["abs_error_mw"] = (frame["forecast_mw"] - frame["actual_mw"]).abs()
        frame["error_mw"] = frame["forecast_mw"] - frame["actual_mw"]
        return frame

    return build(
        [
            {"status": "matched", "forecast_mw": 110.0, "actual_mw": 100.0},
            {"status": "matched", "forecast_mw": 90.0, "actual_mw": 100.0},
            {"status": "matched", "forecast_mw": 120.0, "actual_mw": 100.0},
            {"status": "matched", "forecast_mw": 100.0, "actual_mw": 100.0},
        ]
    )


@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_repository
    from app.config.settings import get_settings
    from app.main import app

    get_settings.cache_clear()
    get_repository.cache_clear()
    with TestClient(app) as client:
        yield client
    get_repository.cache_clear()


@pytest.fixture
def sample_raw_actuals() -> list[dict]:
    return [
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T00:30:00Z",
            "startTime": "2026-01-01T00:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 1,
            "fuelType": "WIND",
            "generation": 12000,
        },
        {
            "dataset": "FUELHH",
            "publishTime": "2026-01-01T00:30:00Z",
            "startTime": "2026-01-01T00:00:00Z",
            "settlementDate": "2026-01-01",
            "settlementPeriod": 1,
            "fuelType": "CCGT",
            "generation": 5000,
        },
    ]


@pytest.fixture
def sample_raw_forecasts() -> list[dict]:
    return [
        {"dataset": "WINDFOR", "publishTime": "2025-12-31T12:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 11500},
        {"dataset": "WINDFOR", "publishTime": "2025-12-31T18:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 11800},
        {"dataset": "WINDFOR", "publishTime": "2026-01-01T02:30:00Z", "startTime": "2026-01-01T00:00:00Z", "generation": 12100},
    ]
