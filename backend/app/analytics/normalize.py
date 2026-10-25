from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.config.constants import WIND_FUEL_TYPE
from app.utils.timezones import parse_instant

ACTUAL_COLUMNS = ["start_time_utc", "actual_mw", "publish_time_utc", "settlement_date", "settlement_period"]
FORECAST_COLUMNS = ["start_time_utc", "publish_time_utc", "forecast_mw"]


@dataclass
class NormalizationReport:
    parsed: int = 0
    dropped_invalid_timestamp: int = 0
    dropped_invalid_generation: int = 0
    dropped_wrong_fuel_type: int = 0
    duplicates_removed: int = 0
    negative_values: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class NormalizationResult:
    frame: pd.DataFrame
    report: NormalizationReport


def _empty_actuals() -> pd.DataFrame:
    frame = pd.DataFrame({column: pd.Series(dtype="datetime64[ns, UTC]" if "time" in column else "float64") for column in ACTUAL_COLUMNS[:3]})
    frame["settlement_date"] = pd.Series(dtype="object")
    frame["settlement_period"] = pd.Series(dtype="float64")
    return frame


def _empty_forecasts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "start_time_utc": pd.Series(dtype="datetime64[ns, UTC]"),
            "publish_time_utc": pd.Series(dtype="datetime64[ns, UTC]"),
            "forecast_mw": pd.Series(dtype="float64"),
        }
    )


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def normalize_actuals(records: list[dict[str, Any]]) -> NormalizationResult:
    report = NormalizationReport()
    if not records:
        report.warnings.append("Elexon returned no FUELHH records for the requested window.")
        return NormalizationResult(frame=_empty_actuals(), report=report)

    frame = pd.DataFrame(records)
    report.parsed = len(frame)

    if "fuelType" in frame.columns:
        fuel = frame["fuelType"].astype(str).str.upper()
        mask = fuel == WIND_FUEL_TYPE
        report.dropped_wrong_fuel_type = int((~mask).sum())
        frame = frame[mask]

    required = {"startTime", "generation"}
    missing = required - set(frame.columns)
    if missing:
        report.errors.append(f"FUELHH payload missing required fields: {', '.join(sorted(missing))}")
        return NormalizationResult(frame=_empty_actuals(), report=report)

    frame = frame.copy()
    frame["start_time_utc"] = frame["startTime"].map(_safe_instant)
    frame["publish_time_utc"] = frame.get("publishTime", pd.Series([None] * len(frame))).map(_safe_instant)
    frame["actual_mw"] = _coerce_numeric(frame["generation"])
    frame["settlement_date"] = frame.get("settlementDate", pd.Series([None] * len(frame)))
    frame["settlement_period"] = _coerce_numeric(frame.get("settlementPeriod", pd.Series([None] * len(frame))))

    invalid_time = frame["start_time_utc"].isna()
    report.dropped_invalid_timestamp = int(invalid_time.sum())
    frame = frame[~invalid_time]

    invalid_generation = frame["actual_mw"].isna()
    report.dropped_invalid_generation = int(invalid_generation.sum())
    frame = frame[~invalid_generation]

    frame = frame.drop_duplicates(
        subset=["start_time_utc"],
        keep="last",
    )
    report.duplicates_removed = max(0, report.parsed - report.dropped_wrong_fuel_type - report.dropped_invalid_timestamp - report.dropped_invalid_generation - len(frame))

    negative = frame["actual_mw"] < 0
    report.negative_values = int(negative.sum())
    if report.negative_values:
        report.warnings.append(
            f"{report.negative_values} FUELHH WIND records report negative generation; values are retained as published."
        )

    frame = frame[ACTUAL_COLUMNS].sort_values("start_time_utc").reset_index(drop=True)
    return NormalizationResult(frame=frame, report=report)


def normalize_forecasts(records: list[dict[str, Any]]) -> NormalizationResult:
    report = NormalizationReport()
    if not records:
        report.warnings.append("Elexon returned no WINDFOR records for the requested publication window.")
        return NormalizationResult(frame=_empty_forecasts(), report=report)

    frame = pd.DataFrame(records)
    report.parsed = len(frame)

    required = {"startTime", "publishTime", "generation"}
    missing = required - set(frame.columns)
    if missing:
        report.errors.append(f"WINDFOR payload missing required fields: {', '.join(sorted(missing))}")
        return NormalizationResult(frame=_empty_forecasts(), report=report)

    frame = frame.copy()
    frame["start_time_utc"] = frame["startTime"].map(_safe_instant)
    frame["publish_time_utc"] = frame["publishTime"].map(_safe_instant)
    frame["forecast_mw"] = _coerce_numeric(frame["generation"])

    invalid_time = frame["start_time_utc"].isna() | frame["publish_time_utc"].isna()
    report.dropped_invalid_timestamp = int(invalid_time.sum())
    frame = frame[~invalid_time]

    invalid_generation = frame["forecast_mw"].isna()
    report.dropped_invalid_generation = int(invalid_generation.sum())
    frame = frame[~invalid_generation]

    before = len(frame)
    frame = frame.sort_values("publish_time_utc").drop_duplicates(subset=["start_time_utc", "publish_time_utc"], keep="last")
    report.duplicates_removed = before - len(frame)

    negative = frame["forecast_mw"] < 0
    report.negative_values = int(negative.sum())
    if report.negative_values:
        report.warnings.append(
            f"{report.negative_values} WINDFOR records report negative forecast generation; values are retained as published."
        )

    frame = frame[FORECAST_COLUMNS].sort_values(["publish_time_utc", "start_time_utc"]).reset_index(drop=True)
    return NormalizationResult(frame=frame, report=report)


def _safe_instant(value: Any) -> pd.Timestamp | pd.NaT:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return pd.NaT
    try:
        parsed = parse_instant(str(value))
    except (ValueError, TypeError):
        return pd.NaT
    return pd.Timestamp(parsed)


def frame_timestamp(frame: pd.DataFrame, column: str) -> datetime | None:
    if frame.empty or column not in frame.columns:
        return None
    value = frame[column].max()
    if pd.isna(value):
        return None
    return value.to_pydatetime()
