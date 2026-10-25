from __future__ import annotations

import csv
import io
from datetime import date

import pandas as pd

from app.analytics.selection import SelectionRequest

EXPORT_COLUMNS = [
    "delivery_local",
    "delivery_date_local",
    "period_index",
    "settlement_period",
    "delivery_utc",
    "time_label",
    "status",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "abs_error_mw",
    "direction",
    "forecast_publish_local",
    "forecast_publish_utc",
    "lead_hours",
    "cutoff_local",
    "forecast_missing_reason",
]


def _format_number(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, (int,)):
        return str(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.2f}"


def _format_cell(column: str, value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if column == "settlement_period":
        try:
            return str(int(float(value)))
        except (TypeError, ValueError):
            return ""
    if column.endswith("_mw") or column == "lead_hours":
        return _format_number(value)
    return str(value)


def frame_from_rows(rows: list) -> pd.DataFrame:
    records = [row.model_dump() if hasattr(row, "model_dump") else row for row in rows]
    if not records:
        return pd.DataFrame(columns=EXPORT_COLUMNS)
    return pd.DataFrame(records)


def build_csv(frame: pd.DataFrame, request: SelectionRequest, data_mode: str) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)

    for _, row in frame.iterrows():
        writer.writerow(
            [
                _format_cell(column, row[column]) if column in frame.columns else ""
                for column in EXPORT_COLUMNS
            ]
        )

    return buffer.getvalue()


def export_filename(request: SelectionRequest, data_mode: str) -> str:
    start: date = request.start_day
    end: date = request.end_day
    if request.mode == "rolling_lead":
        suffix = f"lead{request.lead_hours:g}h"
    else:
        suffix = "fixedcutoff"
    date_part = start.isoformat() if start == end else f"{start.isoformat()}_{end.isoformat()}"
    return f"aeron_wind_{date_part}_{suffix}_{data_mode}.csv"
