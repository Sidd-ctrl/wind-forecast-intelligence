from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterable

import httpx

from app.config.constants import ACTUAL_ENDPOINT_PATH, FORECAST_ENDPOINT_PATH, WIND_FUEL_TYPE
from app.config.settings import Settings


class ElexonError(Exception):
    status_code = 502
    code = "elexon_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ElexonUnavailableError(ElexonError):
    status_code = 503
    code = "elexon_unavailable"


class ElexonValidationError(ElexonError):
    status_code = 502
    code = "elexon_validation_error"


class ElexonRateLimitError(ElexonError):
    status_code = 429
    code = "elexon_rate_limited"


@dataclass
class ChunkResult:
    label: str
    record_count: int


@dataclass
class RetrievalResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[ChunkResult] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)
    request_urls: list[str] = field(default_factory=list)

    @property
    def partial(self) -> bool:
        return bool(self.failures)


class ElexonClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._settings.elexon_base_url.rstrip("/"),
            timeout=httpx.Timeout(self._settings.elexon_timeout_seconds),
            headers={"Accept": "application/json", "User-Agent": "AERON-Wind-Forecast-Intelligence/1.0"},
            transport=self._transport,
        )

    def _request(self, client: httpx.Client, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        attempts = max(1, self._settings.elexon_max_retries)
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                response = client.get(path, params=params)
            except httpx.TimeoutException as exc:
                last_error = exc
                self._sleep_before_retry(attempt, attempts)
                continue
            except httpx.HTTPError as exc:
                last_error = exc
                self._sleep_before_retry(attempt, attempts)
                continue

            if response.status_code == 429:
                last_error = ElexonRateLimitError("Elexon rate limit reached")
                self._sleep_before_retry(attempt, attempts, multiplier=2.0)
                continue

            if response.status_code >= 500:
                last_error = ElexonUnavailableError(f"Elexon returned status {response.status_code}")
                self._sleep_before_retry(attempt, attempts)
                continue

            if response.status_code >= 400:
                raise ElexonValidationError(
                    "Elexon rejected the request",
                    details={"status": response.status_code, "body": response.text[:400], "params": params},
                )

            return self._extract_records(response)

        raise ElexonUnavailableError(
            "Elexon API did not respond successfully after retries",
            details={"reason": str(last_error) if last_error else "unknown"},
        )

    def _extract_records(self, response: httpx.Response) -> list[dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ElexonValidationError("Elexon returned a non-JSON response") from exc

        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
            records = payload["data"]
        else:
            raise ElexonValidationError("Unexpected Elexon response envelope")

        for record in records:
            if not isinstance(record, dict):
                raise ElexonValidationError("Elexon response contained a non-object record")
        return records

    def _sleep_before_retry(self, attempt: int, attempts: int, multiplier: float = 1.0) -> None:
        if attempt >= attempts - 1:
            return
        delay = self._settings.elexon_retry_backoff_seconds * (2**attempt) * multiplier
        time.sleep(min(delay, 8.0))

    def fetch_actual_wind(self, start_day: date, end_day: date) -> RetrievalResult:
        result = RetrievalResult()
        with self._client() as client:
            for chunk_start, chunk_end in self._date_chunks(start_day, end_day):
                params = {
                    "settlementDateFrom": chunk_start.isoformat(),
                    "settlementDateTo": chunk_end.isoformat(),
                    "fuelType": WIND_FUEL_TYPE,
                }
                label = f"{chunk_start.isoformat()}..{chunk_end.isoformat()}"
                try:
                    records = self._request(client, ACTUAL_ENDPOINT_PATH, params)
                except ElexonError as exc:
                    result.failures.append({"dataset": "FUELHH", "window": label, "error": exc.message})
                    continue
                result.records.extend(records)
                result.chunks.append(ChunkResult(label=label, record_count=len(records)))
                result.request_urls.append(f"{self._settings.elexon_base_url}{ACTUAL_ENDPOINT_PATH}?{self._encode(params)}")
        return result

    def fetch_forecast_wind(self, publish_from: datetime, publish_to: datetime) -> RetrievalResult:
        result = RetrievalResult()
        with self._client() as client:
            for chunk_start, chunk_end in self._instant_chunks(publish_from, publish_to):
                params = {
                    "publishDateTimeFrom": chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "publishDateTimeTo": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                label = f"{params['publishDateTimeFrom']}..{params['publishDateTimeTo']}"
                try:
                    records = self._request(client, FORECAST_ENDPOINT_PATH, params)
                except ElexonError as exc:
                    result.failures.append({"dataset": "WINDFOR", "window": label, "error": exc.message})
                    continue
                result.records.extend(records)
                result.chunks.append(ChunkResult(label=label, record_count=len(records)))
                result.request_urls.append(
                    f"{self._settings.elexon_base_url}{FORECAST_ENDPOINT_PATH}?{self._encode(params)}"
                )
        return result

    def _date_chunks(self, start_day: date, end_day: date) -> Iterable[tuple[date, date]]:
        span = max(1, self._settings.elexon_max_chunk_days - 1)
        cursor = start_day
        while cursor <= end_day:
            chunk_end = min(cursor + timedelta(days=span), end_day)
            yield cursor, chunk_end
            cursor = chunk_end + timedelta(days=1)

    def _instant_chunks(self, start: datetime, end: datetime) -> Iterable[tuple[datetime, datetime]]:
        span = timedelta(days=max(1, self._settings.elexon_max_chunk_days))
        cursor = start
        while cursor < end:
            chunk_end = min(cursor + span, end)
            yield cursor, chunk_end
            cursor = chunk_end

    @staticmethod
    def _encode(params: dict[str, Any]) -> str:
        return httpx.QueryParams(params).__str__()
