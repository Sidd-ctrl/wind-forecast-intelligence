from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from app.analytics.normalize import NormalizationReport, normalize_actuals, normalize_forecasts
from app.config.constants import (
    ACTUAL_DATASET,
    ACTUAL_ENDPOINT_PATH,
    ACTUAL_SOURCE_URL,
    FORECAST_DATASET,
    FORECAST_ENDPOINT_PATH,
    FORECAST_SOURCE_URL,
)
from app.config.settings import Settings
from app.services.elexon_client import ChunkResult, ElexonClient, ElexonError, RetrievalResult
from app.utils.timezones import format_london, parse_date, parse_instant, to_utc

CACHE_HIT = "hit"
CACHE_MISS = "miss"
CACHE_REFRESHED = "refreshed"
CACHE_STALE = "stale"
CACHE_DISABLED = "disabled"
CACHE_UNAVAILABLE = "unavailable"


@dataclass
class DatasetSnapshot:
    actuals: pd.DataFrame
    forecasts: pd.DataFrame
    actual_report: NormalizationReport
    forecast_report: NormalizationReport
    actual_retrieval: RetrievalResult
    forecast_retrieval: RetrievalResult
    retrieval_timestamp: datetime
    retrieval_duration_ms: int
    cache_status: str
    cache_age_seconds: float | None
    data_mode: str
    warnings: list[str] = field(default_factory=list)

    @property
    def actual_count(self) -> int:
        return int(len(self.actuals))

    @property
    def forecast_count(self) -> int:
        return int(len(self.forecasts))


class DatasetRepository:
    def __init__(self, settings: Settings, client: ElexonClient | None = None) -> None:
        self._settings = settings
        self._client = client or ElexonClient(settings)
        self._lock = threading.RLock()
        self._snapshot: DatasetSnapshot | None = None

    def snapshot(self, force_refresh: bool = False) -> DatasetSnapshot:
        with self._lock:
            if not force_refresh and self._snapshot is not None:
                return self._snapshot

            if not force_refresh and self._settings.cache_enabled:
                cached = self._load_disk_cache()
                if cached is not None:
                    self._snapshot = cached
                    return cached

            if self._settings.data_mode == "sample":
                snapshot = self._build_sample_snapshot()
            else:
                snapshot = self._build_live_snapshot(force_refresh=force_refresh)

            self._persist_disk_cache(snapshot)
            self._snapshot = snapshot
            return snapshot

    def clear_memory(self) -> None:
        with self._lock:
            self._snapshot = None

    def peek(self) -> DatasetSnapshot | None:
        return self._snapshot

    def _build_live_snapshot(self, force_refresh: bool) -> DatasetSnapshot:
        started = time.perf_counter()
        start_day = parse_date(self._settings.analysis_start_date)
        end_day = parse_date(self._settings.analysis_end_date)

        publish_from = datetime.combine(
            start_day - timedelta(days=self._settings.forecast_publish_lookback_days),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        publish_to = datetime.combine(
            end_day + timedelta(days=self._settings.forecast_publish_lookahead_days),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        actual_retrieval = self._client.fetch_actual_wind(start_day, end_day)
        forecast_retrieval = self._client.fetch_forecast_wind(publish_from, publish_to)

        if not actual_retrieval.records and not forecast_retrieval.records:
            raise ElexonError(
                "No data could be retrieved from Elexon for the analysis period.",
                details={"failures": actual_retrieval.failures + forecast_retrieval.failures},
            )

        actual_result = normalize_actuals(actual_retrieval.records)
        forecast_result = normalize_forecasts(forecast_retrieval.records)

        warnings: list[str] = []
        warnings.extend(actual_result.report.warnings)
        warnings.extend(forecast_result.report.warnings)
        warnings.extend(actual_result.report.errors)
        warnings.extend(forecast_result.report.errors)
        for failure in actual_retrieval.failures + forecast_retrieval.failures:
            warnings.append(f"Partial retrieval: {failure['dataset']} window {failure['window']} failed ({failure['error']}).")

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return DatasetSnapshot(
            actuals=actual_result.frame,
            forecasts=forecast_result.frame,
            actual_report=actual_result.report,
            forecast_report=forecast_result.report,
            actual_retrieval=actual_retrieval,
            forecast_retrieval=forecast_retrieval,
            retrieval_timestamp=datetime.now(timezone.utc),
            retrieval_duration_ms=elapsed_ms,
            cache_status=CACHE_REFRESHED if force_refresh else CACHE_MISS,
            cache_age_seconds=0.0,
            data_mode="live",
            warnings=warnings,
        )

    def _build_sample_snapshot(self) -> DatasetSnapshot:
        started = time.perf_counter()
        sample_dir = self._settings.sample_data_dir
        actuals_path = sample_dir / "fuelhh_wind_2026_01.csv.gz"
        forecasts_path = sample_dir / "windfor_2026_01.csv.gz"

        if not actuals_path.exists() or not forecasts_path.exists():
            raise FileNotFoundError("Bundled sample dataset files are missing from app/data/sample.")

        actual_raw = pd.read_csv(actuals_path)
        forecast_raw = pd.read_csv(forecasts_path)

        actual_records = actual_raw.to_dict(orient="records")
        forecast_records = forecast_raw.to_dict(orient="records")

        actual_result = normalize_actuals(actual_records)
        forecast_result = normalize_forecasts(forecast_records)

        actual_retrieval = RetrievalResult(
            records=actual_records,
            chunks=[ChunkResult(label="sample-dataset", record_count=len(actual_records))],
        )
        forecast_retrieval = RetrievalResult(
            records=forecast_records,
            chunks=[ChunkResult(label="sample-dataset", record_count=len(forecast_records))],
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return DatasetSnapshot(
            actuals=actual_result.frame,
            forecasts=forecast_result.frame,
            actual_report=actual_result.report,
            forecast_report=forecast_result.report,
            actual_retrieval=actual_retrieval,
            forecast_retrieval=forecast_retrieval,
            retrieval_timestamp=datetime.now(timezone.utc),
            retrieval_duration_ms=elapsed_ms,
            cache_status=CACHE_DISABLED,
            cache_age_seconds=None,
            data_mode="sample",
            warnings=[
                "SAMPLE DATA MODE: the figures shown come from a bundled static snapshot and are not fetched live from Elexon."
            ]
            + actual_result.report.warnings
            + forecast_result.report.warnings,
        )

    def _cache_files(self) -> tuple[Path, Path, Path]:
        base = self._settings.cache_path
        prefix = f"{self._settings.data_mode}"
        return (
            base / f"{prefix}_actuals.csv.gz",
            base / f"{prefix}_forecasts.csv.gz",
            base / f"{prefix}_meta.json",
        )

    def _load_disk_cache(self) -> DatasetSnapshot | None:
        actuals_file, forecasts_file, meta_file = self._cache_files()
        if not (actuals_file.exists() and forecasts_file.exists() and meta_file.exists()):
            return None

        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            stored_at = to_utc(datetime.fromisoformat(meta["stored_at"]))
        except (OSError, ValueError, KeyError):
            return None

        age_seconds = (datetime.now(timezone.utc) - stored_at).total_seconds()
        if age_seconds > self._settings.cache_ttl_hours * 3600:
            return None

        try:
            actuals = pd.read_csv(actuals_file, parse_dates=["start_time_utc", "publish_time_utc"])
            forecasts = pd.read_csv(forecasts_file, parse_dates=["start_time_utc", "publish_time_utc"])
        except (OSError, ValueError):
            return None

        for column in ("start_time_utc", "publish_time_utc"):
            if column in actuals.columns:
                actuals[column] = pd.to_datetime(actuals[column], utc=True)
            if column in forecasts.columns:
                forecasts[column] = pd.to_datetime(forecasts[column], utc=True)

        actual_chunks = meta.get("actual_chunks") or [{"label": "cached retrieval", "record_count": len(actuals)}]
        forecast_chunks = meta.get("forecast_chunks") or [{"label": "cached retrieval", "record_count": len(forecasts)}]

        return DatasetSnapshot(
            actuals=actuals,
            forecasts=forecasts,
            actual_report=NormalizationReport(parsed=len(actuals)),
            forecast_report=NormalizationReport(parsed=len(forecasts)),
            actual_retrieval=RetrievalResult(
                chunks=[ChunkResult(label=item["label"], record_count=item["record_count"]) for item in actual_chunks],
                request_urls=list(meta.get("actual_request_urls", [])),
            ),
            forecast_retrieval=RetrievalResult(
                chunks=[ChunkResult(label=item["label"], record_count=item["record_count"]) for item in forecast_chunks],
                request_urls=list(meta.get("forecast_request_urls", [])),
            ),
            retrieval_timestamp=stored_at,
            retrieval_duration_ms=int(meta.get("retrieval_duration_ms", 0)),
            cache_status=CACHE_HIT,
            cache_age_seconds=age_seconds,
            data_mode=meta.get("data_mode", self._settings.data_mode),
            warnings=list(meta.get("warnings", [])),
        )

    def _persist_disk_cache(self, snapshot: DatasetSnapshot) -> None:
        if not self._settings.cache_enabled or snapshot.data_mode == "sample":
            return
        actuals_file, forecasts_file, meta_file = self._cache_files()
        try:
            actuals_file.parent.mkdir(parents=True, exist_ok=True)
            snapshot.actuals.to_csv(actuals_file, index=False)
            snapshot.forecasts.to_csv(forecasts_file, index=False)
            meta = {
                "stored_at": snapshot.retrieval_timestamp.isoformat(),
                "data_mode": snapshot.data_mode,
                "retrieval_duration_ms": snapshot.retrieval_duration_ms,
                "warnings": snapshot.warnings,
                "actual_chunks": chunk_details(snapshot.actual_retrieval),
                "forecast_chunks": chunk_details(snapshot.forecast_retrieval),
                "actual_request_urls": snapshot.actual_retrieval.request_urls,
                "forecast_request_urls": snapshot.forecast_retrieval.request_urls,
                "analysis_start_date": self._settings.analysis_start_date,
                "analysis_end_date": self._settings.analysis_end_date,
                "actual_records": snapshot.actual_count,
                "forecast_records": snapshot.forecast_count,
            }
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except OSError:
            return


def describe_cache(snapshot: DatasetSnapshot, settings: Settings) -> dict:
    if snapshot.data_mode == "sample":
        status = CACHE_DISABLED
    elif not settings.cache_enabled:
        status = CACHE_DISABLED
    elif snapshot.cache_status in {CACHE_HIT, CACHE_STALE}:
        status = CACHE_HIT
    else:
        status = CACHE_MISS

    return {
        "status": status,
        "backend": "filesystem",
        "directory": settings.cache_dir,
        "ttl_hours": settings.cache_ttl_hours,
        "age_seconds": round(snapshot.cache_age_seconds, 1) if snapshot.cache_age_seconds is not None else None,
        "enabled": settings.cache_enabled and snapshot.data_mode != "sample",
        "retrieval_timestamp_utc": snapshot.retrieval_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "retrieval_timestamp_local": format_london(snapshot.retrieval_timestamp),
        "retrieval_duration_ms": snapshot.retrieval_duration_ms,
        "note": (
            "Sample mode reads a bundled dataset and never calls Elexon."
            if snapshot.data_mode == "sample"
            else "Historical records are persisted to the filesystem cache and reused until the TTL expires or a refresh is requested."
        ),
    }


def describe_sources() -> list[dict]:
    return [
        {
            "dataset": ACTUAL_DATASET,
            "label": "Half-hourly generation outturn by fuel type (actual wind)",
            "endpoint": f"https://data.elexon.co.uk/bmrs/api/v1{ACTUAL_ENDPOINT_PATH}",
            "documentation": ACTUAL_SOURCE_URL,
            "filter": "fuelType=WIND",
            "fields": ["startTime", "publishTime", "settlementDate", "settlementPeriod", "fuelType", "generation"],
            "granularity": "30 minutes",
            "request_parameters": ["settlementDateFrom", "settlementDateTo", "fuelType"],
        },
        {
            "dataset": FORECAST_DATASET,
            "label": "Wind generation forecast (WINDFOR)",
            "endpoint": f"https://data.elexon.co.uk/bmrs/api/v1{FORECAST_ENDPOINT_PATH}",
            "documentation": FORECAST_SOURCE_URL,
            "filter": "publication window only",
            "fields": ["startTime", "publishTime", "generation"],
            "granularity": "hourly delivery targets published roughly every 2-4 hours",
            "request_parameters": ["publishDateTimeFrom", "publishDateTimeTo"],
        },
    ]


def snapshot_coverage(snapshot: DatasetSnapshot) -> dict:
    def bounds(frame: pd.DataFrame, column: str) -> dict:
        if frame.empty or column not in frame.columns:
            return {"first": None, "last": None}
        series = frame[column].dropna()
        if series.empty:
            return {"first": None, "last": None}
        return {"first": format_london(series.min().to_pydatetime()), "last": format_london(series.max().to_pydatetime())}

    latest_forecast_publication = None
    if not snapshot.forecasts.empty:
        latest = snapshot.forecasts["publish_time_utc"].max()
        if pd.notna(latest):
            latest_forecast_publication = format_london(latest.to_pydatetime())

    return {
        "actual_delivery_window": bounds(snapshot.actuals, "start_time_utc"),
        "forecast_delivery_window": bounds(snapshot.forecasts, "start_time_utc"),
        "forecast_publication_window": bounds(snapshot.forecasts, "publish_time_utc"),
        "latest_forecast_publication": latest_forecast_publication,
        "distinct_publications": int(snapshot.forecasts["publish_time_utc"].nunique()) if not snapshot.forecasts.empty else 0,
    }


def chunk_details(retrieval: RetrievalResult) -> list[dict]:
    return [{"label": chunk.label, "record_count": chunk.record_count} for chunk in retrieval.chunks]


def failure_details(snapshot: DatasetSnapshot) -> list[dict]:
    return list(snapshot.actual_retrieval.failures) + list(snapshot.forecast_retrieval.failures)


def analysis_window(settings: Settings) -> tuple[date, date]:
    return parse_date(settings.analysis_start_date), parse_date(settings.analysis_end_date)


def cache_age_label(snapshot: DatasetSnapshot) -> str:
    if snapshot.cache_age_seconds is None:
        return "not cached"
    if snapshot.cache_age_seconds < 90:
        return f"{snapshot.cache_age_seconds:.0f} seconds old"
    return f"{snapshot.cache_age_seconds / 60:.1f} minutes old"


def parse_timestamp(value: str) -> datetime:
    return parse_instant(value)
