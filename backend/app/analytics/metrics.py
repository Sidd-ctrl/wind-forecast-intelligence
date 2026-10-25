from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.config.constants import STATUS_MATCHED


@dataclass
class MetricSet:
    mae_mw: float | None = None
    rmse_mw: float | None = None
    bias_mw: float | None = None
    wape_pct: float | None = None
    n_observations: int = 0
    periods_total: int = 0
    missing_forecast: int = 0
    missing_actual: int = 0
    overforecast_count: int = 0
    underforecast_count: int = 0
    exact_count: int = 0
    overforecast_pct: float | None = None
    mean_actual_mw: float | None = None
    mean_forecast_mw: float | None = None
    max_abs_error_mw: float | None = None
    error_p05_mw: float | None = None
    error_p95_mw: float | None = None
    abs_error_p50_mw: float | None = None
    abs_error_p90_mw: float | None = None
    notes: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "mae_mw": self.mae_mw,
            "rmse_mw": self.rmse_mw,
            "bias_mw": self.bias_mw,
            "wape_pct": self.wape_pct,
            "n_observations": self.n_observations,
            "periods_total": self.periods_total,
            "missing_forecast": self.missing_forecast,
            "missing_actual": self.missing_actual,
            "overforecast_count": self.overforecast_count,
            "underforecast_count": self.underforecast_count,
            "exact_count": self.exact_count,
            "overforecast_pct": self.overforecast_pct,
            "mean_actual_mw": self.mean_actual_mw,
            "mean_forecast_mw": self.mean_forecast_mw,
            "max_abs_error_mw": self.max_abs_error_mw,
            "error_p05_mw": self.error_p05_mw,
            "error_p95_mw": self.error_p95_mw,
            "abs_error_p50_mw": self.abs_error_p50_mw,
            "abs_error_p90_mw": self.abs_error_p90_mw,
            "notes": self.notes or [],
        }


def _finite(value: float | None) -> float | None:
    if value is None:
        return None
    if not np.isfinite(value):
        return None
    return float(value)


def safe_wape(absolute_error_sum: float, actual_sum: float) -> float | None:
    if actual_sum == 0 or not np.isfinite(actual_sum):
        return None
    return float(absolute_error_sum / actual_sum * 100.0)


def compute_metrics(frame: pd.DataFrame) -> MetricSet:
    metrics = MetricSet()
    if frame is None or frame.empty:
        metrics.notes = ["No delivery periods were supplied, so no metrics can be calculated."]
        return metrics

    metrics.periods_total = int(len(frame))
    statuses = frame.get("status")
    if statuses is not None:
        metrics.missing_forecast = int((frame["status"] == "missing_forecast").sum())
        metrics.missing_actual = int((frame["status"] == "missing_actual").sum())

    matched = frame[frame["error_mw"].notna()] if "error_mw" in frame.columns else frame.iloc[0:0]
    metrics.n_observations = int(len(matched))
    if matched.empty:
        metrics.notes = ["No delivery period has both a valid eligible forecast and a valid actual value."]
        return metrics

    error = matched["error_mw"].astype(float)
    absolute = error.abs()
    actual = matched["actual_mw"].astype(float)
    forecast = matched["forecast_mw"].astype(float)

    metrics.mae_mw = _finite(absolute.mean())
    metrics.rmse_mw = _finite(np.sqrt(np.mean(np.square(error))))
    metrics.bias_mw = _finite(error.mean())
    metrics.wape_pct = _finite(safe_wape(float(absolute.sum()), float(actual.sum())))
    metrics.mean_actual_mw = _finite(actual.mean())
    metrics.mean_forecast_mw = _finite(forecast.mean())
    metrics.max_abs_error_mw = _finite(absolute.max())
    metrics.error_p05_mw = _finite(np.percentile(error, 5))
    metrics.error_p95_mw = _finite(np.percentile(error, 95))
    metrics.abs_error_p50_mw = _finite(np.percentile(absolute, 50))
    metrics.abs_error_p90_mw = _finite(np.percentile(absolute, 90))

    metrics.overforecast_count = int((error > 0).sum())
    metrics.underforecast_count = int((error < 0).sum())
    metrics.exact_count = int((error == 0).sum())
    metrics.overforecast_pct = _finite(metrics.overforecast_count / metrics.n_observations * 100.0)

    notes: list[str] = []
    if metrics.wape_pct is None:
        notes.append("WAPE is undefined because the summed actual generation over the matched periods is zero.")
    if metrics.n_observations < metrics.periods_total:
        notes.append(
            f"{metrics.periods_total - metrics.n_observations} of {metrics.periods_total} delivery periods were excluded "
            "from the metrics because a valid forecast/actual pair was not available."
        )
    metrics.notes = notes
    return metrics


def error_histogram(frame: pd.DataFrame, bins: int = 16) -> list[dict[str, Any]]:
    if frame is None or frame.empty or "abs_error_mw" not in frame.columns:
        return []
    values = frame["abs_error_mw"].dropna().astype(float)
    if values.empty:
        return []
    upper = float(values.max())
    if upper <= 0:
        return [{"label": "0 MW", "lower_mw": 0.0, "upper_mw": 0.0, "count": int(len(values))}]
    edges = np.linspace(0.0, upper, bins + 1)
    counts, _ = np.histogram(values, bins=edges)
    bins_out: list[dict[str, Any]] = []
    for index, count in enumerate(counts):
        lower = float(edges[index])
        upper_edge = float(edges[index + 1])
        bins_out.append(
            {
                "label": f"{lower:,.0f}–{upper_edge:,.0f}",
                "lower_mw": round(lower, 2),
                "upper_mw": round(upper_edge, 2),
                "count": int(count),
            }
        )
    return bins_out


def direction_split(frame: pd.DataFrame) -> dict[str, int]:
    if frame is None or frame.empty or "error_mw" not in frame.columns:
        return {"overforecast": 0, "underforecast": 0, "exact": 0}
    error = frame["error_mw"].dropna()
    return {
        "overforecast": int((error > 0).sum()),
        "underforecast": int((error < 0).sum()),
        "exact": int((error == 0).sum()),
    }


def largest_absolute_error(frame: pd.DataFrame) -> dict[str, Any] | None:
    if frame is None or frame.empty or "abs_error_mw" not in frame.columns:
        return None
    candidates = frame[frame["abs_error_mw"].notna()]
    if candidates.empty:
        return None
    row = candidates.loc[candidates["abs_error_mw"].idxmax()]
    return {
        "delivery_local": row["delivery_local"],
        "delivery_utc": row["delivery_utc"],
        "period_index": int(row["period_index"]),
        "forecast_mw": float(row["forecast_mw"]),
        "actual_mw": float(row["actual_mw"]),
        "error_mw": float(row["error_mw"]),
        "abs_error_mw": float(row["abs_error_mw"]),
        "direction": str(row["direction"]),
        "forecast_publish_local": row["forecast_publish_local"],
        "lead_hours": float(row["lead_hours"]) if pd.notna(row["lead_hours"]) else None,
    }


def matched_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame[frame["status"] == STATUS_MATCHED].copy()


def common_observation_frame(left: pd.DataFrame, right: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if left is None or right is None or left.empty or right.empty:
        return pd.DataFrame(), pd.DataFrame()
    left_matched = matched_frame(left)
    right_matched = matched_frame(right)
    if left_matched.empty or right_matched.empty:
        return pd.DataFrame(), pd.DataFrame()
    common = set(left_matched["period_start_utc"]).intersection(set(right_matched["period_start_utc"]))
    if not common:
        return pd.DataFrame(), pd.DataFrame()
    left_common = left_matched[left_matched["period_start_utc"].isin(common)].sort_values("period_start_utc")
    right_common = right_matched[right_matched["period_start_utc"].isin(common)].sort_values("period_start_utc")
    return left_common.reset_index(drop=True), right_common.reset_index(drop=True)
