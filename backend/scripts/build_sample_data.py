from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import get_settings
from app.services.elexon_client import ElexonClient

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "sample"
ACTUAL_COLUMNS = [
    "dataset",
    "publishTime",
    "startTime",
    "settlementDate",
    "settlementPeriod",
    "fuelType",
    "generation",
]
FORECAST_COLUMNS = ["dataset", "publishTime", "startTime", "generation"]


def main() -> None:
    settings = get_settings()
    client = ElexonClient(settings)
    start_day = pd.Timestamp(settings.analysis_start_date).date()
    end_day = pd.Timestamp(settings.analysis_end_date).date()

    actual = client.fetch_actual_wind(start_day, end_day)
    forecast = client.fetch_forecast_wind(
        pd.Timestamp(settings.analysis_start_date).tz_localize("UTC").to_pydatetime()
        - pd.Timedelta(days=settings.forecast_publish_lookback_days),
        pd.Timestamp(settings.analysis_end_date).tz_localize("UTC").to_pydatetime()
        + pd.Timedelta(days=settings.forecast_publish_lookahead_days),
    )

    if actual.failures or forecast.failures:
        raise SystemExit(f"Retrieval failed: {actual.failures + forecast.failures}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actual_frame = pd.DataFrame(actual.records)[ACTUAL_COLUMNS].sort_values("startTime")
    forecast_frame = pd.DataFrame(forecast.records)[FORECAST_COLUMNS].sort_values(["startTime", "publishTime"])

    actual_path = OUTPUT_DIR / "fuelhh_wind_2026_01.csv.gz"
    forecast_path = OUTPUT_DIR / "windfor_2026_01.csv.gz"
    actual_frame.to_csv(actual_path, index=False, compression="gzip")
    forecast_frame.to_csv(forecast_path, index=False, compression="gzip")

    print(f"actuals: {len(actual_frame)} rows -> {actual_path} ({actual_path.stat().st_size / 1024:.0f} KB)")
    print(f"forecasts: {len(forecast_frame)} rows -> {forecast_path} ({forecast_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
