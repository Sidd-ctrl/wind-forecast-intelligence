from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from app.config.constants import (
    CUTOFF_MODE_ABSOLUTE,
    CUTOFF_MODE_ROLLING,
    PERIOD_MINUTES,
    STATUS_MATCHED,
    STATUS_MISSING_ACTUAL,
    STATUS_MISSING_BOTH,
    STATUS_MISSING_FORECAST,
)
from app.utils.timezones import delivery_day_bounds_utc, format_london, format_utc, to_london, to_utc

REASON_NO_PUBLICATION = "no_publication_in_window"
REASON_PUBLISHED_AFTER_CUTOFF = "published_after_cutoff"
REASON_NO_ACTUAL = "no_actual_record"


@dataclass
class SelectionRequest:
    start_day: date
    end_day: date
    mode: str = CUTOFF_MODE_ROLLING
    lead_hours: float = 12.0
    cutoff: datetime | None = None

    def validate(self) -> None:
        if self.end_day < self.start_day:
            raise ValueError("end date must not be before start date")
        if self.mode == CUTOFF_MODE_ABSOLUTE and self.cutoff is None:
            raise ValueError("an absolute cutoff instant is required for absolute_cutoff mode")
        if self.mode == CUTOFF_MODE_ROLLING and self.lead_hours <= 0:
            raise ValueError("lead hours must be positive")


@dataclass
class SelectionResult:
    frame: pd.DataFrame
    request: SelectionRequest
    warnings: list[str] = field(default_factory=list)

    @property
    def periods_total(self) -> int:
        return int(len(self.frame))

    @property
    def matched_count(self) -> int:
        return int((self.frame["status"] == STATUS_MATCHED).sum())

    def matched(self) -> pd.DataFrame:
        return self.frame[self.frame["status"] == STATUS_MATCHED].copy()


def build_period_grid(start_day: date, end_day: date) -> pd.DataFrame:
    rows: list[dict] = []
    cursor = start_day
    while cursor <= end_day:
        day_start, day_end = delivery_day_bounds_utc(cursor)
        period_start = day_start
        index = 0
        while period_start < day_end:
            local = to_london(period_start)
            rows.append(
                {
                    "period_start_utc": period_start,
                    "delivery_local": local.strftime("%Y-%m-%d %H:%M"),
                    "delivery_date_local": local.strftime("%Y-%m-%d"),
                    "period_index": index + 1,
                    "time_label": local.strftime("%H:%M"),
                }
            )
            index += 1
            period_start = period_start + timedelta(minutes=PERIOD_MINUTES)
        cursor = cursor + timedelta(days=1)

    frame = pd.DataFrame(rows)
    frame["period_start_utc"] = pd.to_datetime(frame["period_start_utc"], utc=True)
    frame["aligned_hour"] = frame["period_start_utc"].dt.floor("h")
    return frame


def _cutoff_series(periods: pd.DataFrame, request: SelectionRequest) -> pd.Series:
    if request.mode == CUTOFF_MODE_ABSOLUTE:
        cutoff = pd.Timestamp(to_utc(request.cutoff))
        return pd.Series([cutoff] * len(periods), index=periods.index, dtype="datetime64[ns, UTC]")
    delta = pd.to_timedelta(request.lead_hours, unit="h")
    return periods["period_start_utc"] - delta


def _empty_forecast_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "aligned_hour": pd.Series(dtype="datetime64[ns, UTC]"),
            "publish_time_utc": pd.Series(dtype="datetime64[ns, UTC]"),
            "forecast_mw": pd.Series(dtype="float64"),
        }
    )


def select_forecasts(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    request: SelectionRequest,
) -> SelectionResult:
    request.validate()
    periods = build_period_grid(request.start_day, request.end_day)

    if periods.empty:
        return SelectionResult(frame=_empty_selection_frame(), request=request, warnings=["No delivery periods in the selected range."])

    warnings: list[str] = []
    periods["cutoff_utc"] = _cutoff_series(periods, request)

    if forecasts.empty:
        warnings.append("No WINDFOR forecast records are available for the requested publication window.")
        working_forecasts = _empty_forecast_frame()
    else:
        working_forecasts = forecasts.rename(columns={"start_time_utc": "aligned_hour"})[
            ["aligned_hour", "publish_time_utc", "forecast_mw"]
        ].copy()
        working_forecasts["aligned_hour"] = working_forecasts["aligned_hour"].dt.floor("h")

    candidates = periods.merge(working_forecasts, on="aligned_hour", how="left", sort=False)

    had_publication = (
        candidates.groupby("period_start_utc")["publish_time_utc"].apply(lambda series: series.notna().any()).rename("had_publication")
    )

    eligible = candidates[candidates["publish_time_utc"].notna() & (candidates["publish_time_utc"] <= candidates["cutoff_utc"])]
    selected = (
        eligible.sort_values(["period_start_utc", "publish_time_utc"])
        .drop_duplicates(subset=["period_start_utc"], keep="last")
        .set_index("period_start_utc")
    )

    result = periods.set_index("period_start_utc").copy()
    result["forecast_mw"] = selected["forecast_mw"].reindex(result.index)
    result["publish_time_utc"] = selected["publish_time_utc"].reindex(result.index)

    if actuals.empty:
        warnings.append("No FUELHH actual wind generation records are available for the requested delivery dates.")
        result["actual_mw"] = np.nan
        result["settlement_period"] = np.nan
    else:
        actual_indexed = actuals.set_index("start_time_utc")
        result["actual_mw"] = actual_indexed["actual_mw"].reindex(result.index)
        if "settlement_period" in actual_indexed.columns:
            result["settlement_period"] = actual_indexed["settlement_period"].reindex(result.index)
        else:
            result["settlement_period"] = np.nan

    result = result.reset_index()

    publication_flag = result["period_start_utc"].map(had_publication).fillna(False).astype(bool)
    has_forecast = result["forecast_mw"].notna()
    has_actual = result["actual_mw"].notna()

    result["status"] = np.select(
        [
            has_forecast & has_actual,
            has_forecast & ~has_actual,
            ~has_forecast & has_actual,
        ],
        [STATUS_MATCHED, STATUS_MISSING_ACTUAL, STATUS_MISSING_FORECAST],
        default=STATUS_MISSING_BOTH,
    )

    result["forecast_missing_reason"] = np.select(
        [
            ~has_forecast & publication_flag,
            ~has_forecast & ~publication_flag,
        ],
        [REASON_PUBLISHED_AFTER_CUTOFF, REASON_NO_PUBLICATION],
        default=None,
    )
    result.loc[has_forecast, "forecast_missing_reason"] = None

    result["error_mw"] = result["forecast_mw"] - result["actual_mw"]
    result["abs_error_mw"] = result["error_mw"].abs()
    result["lead_hours"] = (result["period_start_utc"] - result["publish_time_utc"]).dt.total_seconds() / 3600.0

    result["direction"] = np.select(
        [result["error_mw"] > 0, result["error_mw"] < 0],
        ["overforecast", "underforecast"],
        default="exact",
    )

    result = result.sort_values("period_start_utc").reset_index(drop=True)
    result["forecast_publish_local"] = result["publish_time_utc"].map(_local_or_none)
    result["delivery_utc"] = result["period_start_utc"].map(format_utc)
    result["cutoff_local"] = result["cutoff_utc"].map(_local_or_none)

    if not forecasts.empty and request.mode == CUTOFF_MODE_ROLLING:
        median_lead = result["lead_hours"].dropna().median()
        if pd.notna(median_lead) and median_lead < request.lead_hours - 1:
            warnings.append(
                "WINDFOR publishes on an irregular cycle, so the realised lead time is shorter than the requested "
                f"cutoff for some delivery periods (median realised lead {median_lead:.1f} h against a requested {request.lead_hours:.0f} h)."
            )

    return SelectionResult(frame=result, request=request, warnings=warnings)


def _local_or_none(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return format_london(value.to_pydatetime() if hasattr(value, "to_pydatetime") else value)


def _empty_selection_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "period_start_utc",
            "delivery_local",
            "delivery_date_local",
            "period_index",
            "time_label",
            "aligned_hour",
            "cutoff_utc",
            "forecast_mw",
            "publish_time_utc",
            "actual_mw",
            "settlement_period",
            "status",
            "forecast_missing_reason",
            "error_mw",
            "abs_error_mw",
            "lead_hours",
            "direction",
            "forecast_publish_local",
            "delivery_utc",
            "cutoff_local",
        ]
    )


def describe_selection(request: SelectionRequest) -> dict:
    if request.mode == CUTOFF_MODE_ABSOLUTE:
        cutoff = to_utc(request.cutoff) if request.cutoff else None
        return {
            "mode": CUTOFF_MODE_ABSOLUTE,
            "lead_hours": None,
            "cutoff_local": format_london(cutoff),
            "cutoff_utc": format_utc(cutoff),
            "description": (
                "A single fixed decision cutoff is applied to every delivery period. Only WINDFOR publications with "
                "publishTime at or before this instant are eligible."
            ),
        }
    return {
        "mode": CUTOFF_MODE_ROLLING,
        "lead_hours": request.lead_hours,
        "cutoff_local": None,
        "cutoff_utc": None,
        "description": (
            f"Rolling cutoff: for each delivery period T the decision cutoff is C = T - {request.lead_hours:g} h. "
            "The latest WINDFOR publication with publishTime <= C is selected. This is an analytical convention, "
            "not an official market deadline."
        ),
    }
