from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CacheInfo(BaseModel):
    status: str
    backend: str
    directory: str
    ttl_hours: float
    age_seconds: float | None = None
    enabled: bool
    retrieval_timestamp_utc: str
    retrieval_timestamp_local: str
    retrieval_duration_ms: int
    note: str


class DataMeta(BaseModel):
    product: str = "AERON"
    analysis_start_date: str
    analysis_end_date: str
    timezone: str = "Europe/London"
    unit: str = "MW"
    data_mode: Literal["live", "sample"]
    generated_at_utc: str
    generated_at_local: str
    cache: CacheInfo
    forecast_granularity: str
    actual_granularity: str
    scope_note: str


class SelectionInfo(BaseModel):
    mode: str
    lead_hours: float | None = None
    cutoff_local: str | None = None
    cutoff_utc: str | None = None
    description: str


class QualityInfo(BaseModel):
    periods_total: int
    matched: int
    missing_forecast: int
    missing_actual: int
    missing_both: int
    published_after_cutoff: int
    coverage_pct: float | None = None
    duplicate_actuals_removed: int = 0
    duplicate_forecasts_removed: int = 0
    invalid_actuals_removed: int = 0
    invalid_forecasts_removed: int = 0
    warnings: list[str] = Field(default_factory=list)


class MetricsModel(BaseModel):
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
    notes: list[str] = Field(default_factory=list)


class SeriesPoint(BaseModel):
    period_start_utc: str
    delivery_local: str
    delivery_date_local: str
    period_index: int
    time_label: str
    forecast_mw: float | None = None
    actual_mw: float | None = None
    error_mw: float | None = None
    abs_error_mw: float | None = None
    direction: str
    status: str
    forecast_publish_local: str | None = None
    forecast_publish_utc: str | None = None
    lead_hours: float | None = None
    cutoff_local: str | None = None
    forecast_missing_reason: str | None = None


class ForecastRow(SeriesPoint):
    delivery_utc: str
    settlement_period: float | None = None


class LargestError(BaseModel):
    delivery_local: str
    delivery_utc: str
    period_index: int
    forecast_mw: float
    actual_mw: float
    error_mw: float
    abs_error_mw: float
    direction: str
    forecast_publish_local: str | None = None
    lead_hours: float | None = None


class UncertaintyBandPoint(BaseModel):
    time_label: str
    delivery_local: str
    nominal_mw: float | None = None
    lower_mw: float | None = None
    upper_mw: float | None = None


class UncertaintyInfo(BaseModel):
    abs_error_p50_mw: float | None = None
    abs_error_p90_mw: float | None = None
    abs_error_max_mw: float | None = None
    error_p05_mw: float | None = None
    error_p95_mw: float | None = None
    band: list[UncertaintyBandPoint] = Field(default_factory=list)
    band_basis: str
    realised_lead_median_hours: float | None = None
    realised_lead_min_hours: float | None = None
    realised_lead_max_hours: float | None = None


class InsightItem(BaseModel):
    severity: Literal["info", "attention", "critical"]
    title: str
    detail: str


class OverviewResponse(BaseModel):
    meta: DataMeta
    selection: SelectionInfo
    metrics: MetricsModel
    quality: QualityInfo
    series: list[SeriesPoint]
    largest_error: LargestError | None = None
    uncertainty: UncertaintyInfo
    insights: list[InsightItem]
    scope_note: str


class ForecastResponse(BaseModel):
    meta: DataMeta
    selection: SelectionInfo
    metrics: MetricsModel
    quality: QualityInfo
    rows: list[ForecastRow]
    row_count: int
    truncated: bool = False
    filters_applied: dict[str, Any] = Field(default_factory=dict)


class HistogramBin(BaseModel):
    label: str
    lower_mw: float
    upper_mw: float
    count: int


class DirectionSplit(BaseModel):
    overforecast: int
    underforecast: int
    exact: int


class AccuracyResponse(BaseModel):
    meta: DataMeta
    selection: SelectionInfo
    metrics: MetricsModel
    quality: QualityInfo
    histogram: list[HistogramBin]
    direction: DirectionSplit
    by_period: list[ForecastRow]
    explanations: dict[str, str]
    notes: list[str] = Field(default_factory=list)
    scope_note: str


class CompareEntry(BaseModel):
    label: str
    mode: str
    lead_hours: float | None = None
    cutoff_local: str | None = None
    metrics: MetricsModel
    n_common: int
    n_native: int
    notes: list[str] = Field(default_factory=list)


class CompareCommonMetrics(BaseModel):
    label: str
    lead_hours: float | None = None
    mae_mw: float | None = None
    rmse_mw: float | None = None
    bias_mw: float | None = None
    wape_pct: float | None = None
    n_observations: int = 0


class CompareResponse(BaseModel):
    meta: DataMeta
    quality: QualityInfo
    entries: list[CompareEntry]
    common_metrics: list[CompareCommonMetrics]
    common_period_count: int
    recommended_metric: str
    verdict: str
    disclosures: list[str]
    explanations: dict[str, str]


class ProvenanceRecordCounts(BaseModel):
    actual_records_raw: int
    actual_records_used: int
    forecast_records_raw: int
    forecast_records_used: int
    matched_observations: int
    missing_actual: int
    missing_forecast: int
    duplicate_actuals_removed: int
    duplicate_forecasts_removed: int
    invalid_actuals_removed: int
    invalid_forecasts_removed: int


class ProvenanceResponse(BaseModel):
    meta: DataMeta
    sources: list[dict[str, Any]]
    analysis_range: dict[str, str]
    retrieval: dict[str, Any]
    counts: ProvenanceRecordCounts
    coverage: dict[str, Any]
    duplicates: dict[str, int]
    cache: CacheInfo
    warnings: list[str]
    failures: list[dict[str, str]]
    limitations: list[str]
    chunk_plan: dict[str, list[dict[str, Any]]]
    request_parameters: dict[str, Any]


class RecordsResponse(BaseModel):
    meta: DataMeta
    selection: SelectionInfo
    rows: list[ForecastRow]
    row_count: int
    truncated: bool = False


class RefreshResponse(BaseModel):
    status: str
    message: str
    cache: CacheInfo
    retrieval: dict[str, Any]
    counts: ProvenanceRecordCounts


class HealthResponse(BaseModel):
    status: str
    data_mode: str
    dataset_loaded: bool
    cache_status: str | None = None
    retrieval_timestamp_utc: str | None = None
    analysis_start_date: str
    analysis_end_date: str
    version: str


class MetadataResponse(BaseModel):
    meta: DataMeta
    analysis_dates: list[str]
    default_lead_hours: int
    allowed_lead_hours: list[int]
    cutoff_modes: list[dict[str, str]]
    metric_definitions: dict[str, str]
    error_sign_convention: str
    scope_note: str


class ErrorResponse(BaseModel):
    error: dict[str, Any]
