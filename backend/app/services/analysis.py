from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Iterable

import pandas as pd

from app.analytics.metrics import (
    MetricSet,
    common_observation_frame,
    compute_metrics,
    direction_split,
    error_histogram,
    largest_absolute_error,
    matched_frame,
)
from app.analytics.selection import SelectionRequest, SelectionResult, describe_selection, select_forecasts
from app.config.constants import (
    ASSIGNMENT_SCOPE_NOTE,
    CUTOFF_MODE_ABSOLUTE,
    CUTOFF_MODE_ROLLING,
    STATUS_MATCHED,
    STATUS_MISSING_ACTUAL,
    STATUS_MISSING_BOTH,
    STATUS_MISSING_FORECAST,
)
from app.config.settings import Settings
from app.schemas.models import (
    AccuracyResponse,
    CacheInfo,
    CompareCommonMetrics,
    CompareEntry,
    CompareResponse,
    DataMeta,
    DirectionSplit,
    ForecastRow,
    ForecastResponse,
    HistogramBin,
    InsightItem,
    LargestError,
    MetadataResponse,
    MetricsModel,
    OverviewResponse,
    ProvenanceRecordCounts,
    ProvenanceResponse,
    QualityInfo,
    RecordsResponse,
    SelectionInfo,
    SeriesPoint,
    UncertaintyBandPoint,
    UncertaintyInfo,
)
from app.services.repository import (
    DatasetSnapshot,
    chunk_details,
    describe_cache,
    describe_sources,
    failure_details,
    snapshot_coverage,
)
from app.utils.timezones import format_london, format_utc, parse_instant, to_london

PRODUCT_NAME = "AERON"
DATA_VERSION = "1.0.0"
TABLE_ROW_LIMIT = 6000

METRIC_EXPLANATIONS = {
    "error": "error = forecast_generation - actual_generation, in MW. A positive value means the forecast was higher than actual generation (overforecast).",
    "mae": "MAE = mean(|forecast - actual|). Average magnitude of the miss in MW, direction ignored.",
    "rmse": "RMSE = sqrt(mean((forecast - actual)^2)). Penalises large misses more heavily than MAE.",
    "bias": "Bias = mean(forecast - actual). Average signed miss in MW; positive indicates systematic overforecasting.",
    "wape": "WAPE = sum(|forecast - actual|) / sum(actual) * 100. Scale-free absolute error relative to total actual generation. Undefined when summed actual generation is zero.",
    "lead_time": "Realised lead time = delivery period start minus the publishTime of the selected WINDFOR record, in hours.",
    "cutoff": "Decision cutoff: the instant by which a forecast must already have been published to be eligible. The selection takes the latest publication with publishTime <= cutoff for each delivery period.",
    "overforecast_pct": "Percentage of matched delivery periods where forecast generation exceeded actual generation.",
    "coverage": "Matched delivery periods divided by the total number of half-hourly delivery periods in the selected range.",
}

CUTOFF_MODES = [
    {
        "value": CUTOFF_MODE_ROLLING,
        "label": "Rolling lead time cutoff",
        "description": "Cutoff is calculated per delivery period as C = T - lead_hours. Mirrors a trading process that always decides a fixed number of hours ahead.",
    },
    {
        "value": CUTOFF_MODE_ABSOLUTE,
        "label": "Fixed decision instant",
        "description": "One absolute cutoff instant applies to every delivery period in the range. Mirrors a single day-ahead gate-closure style decision.",
    },
]


class AnalysisError(Exception):
    status_code = 400
    code = "analysis_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


def parse_date_arg(value: str | None, fallback: date, field: str) -> date:
    if value is None or value == "":
        return fallback
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AnalysisError(f"{field} must use the format yyyy-MM-dd") from exc


def parse_cutoff_arg(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AnalysisError("cutoff must be an ISO-8601 instant, for example 2026-01-15T09:00:00Z") from exc
    if parsed.tzinfo is None:
        from app.config.constants import LONDON

        parsed = parsed.replace(tzinfo=LONDON)
    return parsed.astimezone(timezone.utc)


def build_selection_request(
    settings: Settings,
    start_date: str | None,
    end_date: str | None,
    delivery_date: str | None,
    mode: str | None,
    lead_hours: float | None,
    cutoff: str | None,
) -> SelectionRequest:
    window_start, window_end = (
        parse_date_arg(settings.analysis_start_date, date(2026, 1, 1), "analysis_start_date"),
        parse_date_arg(settings.analysis_end_date, date(2026, 1, 31), "analysis_end_date"),
    )

    if delivery_date:
        target = parse_date_arg(delivery_date, window_start, "delivery_date")
        start_day, end_day = target, target
    else:
        start_day = parse_date_arg(start_date, window_start, "start_date")
        end_day = parse_date_arg(end_date, start_day, "end_date")

    if start_day < window_start or end_day > window_end:
        raise AnalysisError(
            "The requested dates fall outside the January 2026 analysis period covered by this deployment.",
            details={"allowed_start": window_start.isoformat(), "allowed_end": window_end.isoformat()},
        )
    if end_day < start_day:
        raise AnalysisError("end_date must not be before start_date")

    resolved_mode = (mode or CUTOFF_MODE_ROLLING).strip().lower()
    if resolved_mode not in {CUTOFF_MODE_ROLLING, CUTOFF_MODE_ABSOLUTE}:
        raise AnalysisError("mode must be 'rolling_lead' or 'absolute_cutoff'")

    if resolved_mode == CUTOFF_MODE_ABSOLUTE:
        cutoff_instant = parse_cutoff_arg(cutoff)
        if cutoff_instant is None:
            raise AnalysisError("cutoff is required when mode is absolute_cutoff")
        return SelectionRequest(start_day=start_day, end_day=end_day, mode=resolved_mode, cutoff=cutoff_instant)

    resolved_lead = settings.default_lead_hours if lead_hours is None else float(lead_hours)
    if resolved_lead <= 0 or resolved_lead > 96:
        raise AnalysisError("lead_hours must be greater than 0 and no more than 96")
    return SelectionRequest(start_day=start_day, end_day=end_day, mode=resolved_mode, lead_hours=resolved_lead)


def run_selection(snapshot: DatasetSnapshot, request: SelectionRequest) -> SelectionResult:
    return select_forecasts(snapshot.forecasts, snapshot.actuals, request)


def build_meta(snapshot: DatasetSnapshot, settings: Settings) -> DataMeta:
    now = datetime.now(timezone.utc)
    return DataMeta(
        analysis_start_date=settings.analysis_start_date,
        analysis_end_date=settings.analysis_end_date,
        data_mode=snapshot.data_mode,
        generated_at_utc=format_utc(now),
        generated_at_local=format_london(now),
        cache=CacheInfo(**describe_cache(snapshot, settings)),
        forecast_granularity="Hourly delivery targets published on an irregular 2-4 hour cycle",
        actual_granularity="Half-hourly settlement periods",
        scope_note=ASSIGNMENT_SCOPE_NOTE,
    )


def build_selection_info(request: SelectionRequest) -> SelectionInfo:
    return SelectionInfo(**describe_selection(request))


def build_quality(result: SelectionResult, snapshot: DatasetSnapshot) -> QualityInfo:
    frame = result.frame
    matched = int((frame["status"] == STATUS_MATCHED).sum()) if not frame.empty else 0
    missing_forecast = int((frame["status"] == STATUS_MISSING_FORECAST).sum()) if not frame.empty else 0
    missing_actual = int((frame["status"] == STATUS_MISSING_ACTUAL).sum()) if not frame.empty else 0
    missing_both = int((frame["status"] == STATUS_MISSING_BOTH).sum()) if not frame.empty else 0
    periods_total = int(len(frame))
    after_cutoff = int((frame["forecast_missing_reason"] == "published_after_cutoff").sum()) if not frame.empty else 0

    warnings = list(result.warnings) + list(snapshot.warnings)
    if after_cutoff:
        warnings.append(
            f"{after_cutoff} delivery periods had WINDFOR publications but none were published early enough for the selected cutoff."
        )

    return QualityInfo(
        periods_total=periods_total,
        matched=matched,
        missing_forecast=missing_forecast,
        missing_actual=missing_actual,
        missing_both=missing_both,
        published_after_cutoff=after_cutoff,
        coverage_pct=round(matched / periods_total * 100.0, 2) if periods_total else None,
        duplicate_actuals_removed=snapshot.actual_report.duplicates_removed,
        duplicate_forecasts_removed=snapshot.forecast_report.duplicates_removed,
        invalid_actuals_removed=snapshot.actual_report.dropped_invalid_generation + snapshot.actual_report.dropped_invalid_timestamp,
        invalid_forecasts_removed=snapshot.forecast_report.dropped_invalid_generation + snapshot.forecast_report.dropped_invalid_timestamp,
        warnings=warnings,
    )


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return float(value)


def row_to_series_point(row: pd.Series) -> SeriesPoint:
    return SeriesPoint(
        period_start_utc=str(row["delivery_utc"]),
        delivery_local=str(row["delivery_local"]),
        delivery_date_local=str(row["delivery_date_local"]),
        period_index=int(row["period_index"]),
        time_label=str(row["time_label"]),
        forecast_mw=_num(row["forecast_mw"]),
        actual_mw=_num(row["actual_mw"]),
        error_mw=_num(row["error_mw"]),
        abs_error_mw=_num(row["abs_error_mw"]),
        direction=str(row["direction"]),
        status=str(row["status"]),
        forecast_publish_local=row["forecast_publish_local"] if pd.notna(row["forecast_publish_local"]) else None,
        forecast_publish_utc=format_utc(row["publish_time_utc"].to_pydatetime()) if pd.notna(row["publish_time_utc"]) else None,
        lead_hours=_num(row["lead_hours"]),
        cutoff_local=row["cutoff_local"] if pd.notna(row["cutoff_local"]) else None,
        forecast_missing_reason=row["forecast_missing_reason"] if pd.notna(row["forecast_missing_reason"]) else None,
    )


def row_to_forecast_row(row: pd.Series) -> ForecastRow:
    base = row_to_series_point(row)
    return ForecastRow(
        **base.model_dump(),
        delivery_utc=str(row["delivery_utc"]),
        settlement_period=_num(row.get("settlement_period")),
    )


def series_from_frame(frame: pd.DataFrame) -> list[SeriesPoint]:
    return [row_to_series_point(row) for _, row in frame.iterrows()]


def forecast_rows_from_frame(frame: pd.DataFrame) -> list[ForecastRow]:
    return [row_to_forecast_row(row) for _, row in frame.iterrows()]


def build_uncertainty(frame: pd.DataFrame, metrics: MetricSet) -> UncertaintyInfo:
    band: list[UncertaintyBandPoint] = []
    if not frame.empty:
        for _, row in frame.iterrows():
            nominal = _num(row["forecast_mw"])
            if nominal is None:
                band.append(
                    UncertaintyBandPoint(time_label=str(row["time_label"]), delivery_local=str(row["delivery_local"]))
                )
                continue
            lower = None if metrics.error_p05_mw is None else nominal + metrics.error_p05_mw
            upper = None if metrics.error_p95_mw is None else nominal + metrics.error_p95_mw
            band.append(
                UncertaintyBandPoint(
                    time_label=str(row["time_label"]),
                    delivery_local=str(row["delivery_local"]),
                    nominal_mw=nominal,
                    lower_mw=lower,
                    upper_mw=upper,
                )
            )

    lead = frame["lead_hours"].dropna() if "lead_hours" in frame.columns else pd.Series(dtype="float64")
    return UncertaintyInfo(
        abs_error_p50_mw=metrics.abs_error_p50_mw,
        abs_error_p90_mw=metrics.abs_error_p90_mw,
        abs_error_max_mw=metrics.max_abs_error_mw,
        error_p05_mw=metrics.error_p05_mw,
        error_p95_mw=metrics.error_p95_mw,
        band=band,
        band_basis=(
            "Band = selected forecast plus the empirical 5th and 95th percentile of signed forecast error across the "
            "matched periods. It is a retrospective error envelope for the selected records, not a live predictive interval."
        ),
        realised_lead_median_hours=_num(lead.median()) if not lead.empty else None,
        realised_lead_min_hours=_num(lead.min()) if not lead.empty else None,
        realised_lead_max_hours=_num(lead.max()) if not lead.empty else None,
    )


def _headline_instant(value: str) -> str:
    return to_london(parse_instant(value)).strftime("%d %b %Y, %H:%M")


def build_insights(frame: pd.DataFrame, metrics: MetricSet, quality: QualityInfo, request: SelectionRequest) -> list[InsightItem]:
    insights: list[InsightItem] = []
    if metrics.n_observations == 0:
        return [
            InsightItem(
                severity="critical",
                title="No matched observations",
                detail="No delivery period in the selected range has both an eligible forecast and an actual record, so no interpretation is possible.",
            )
        ]

    largest = largest_absolute_error(frame)
    if largest:
        direction_text = "an overforecast" if largest["direction"] == "overforecast" else "an underforecast"
        insights.append(
            InsightItem(
                severity="attention",
                title=f"Largest absolute error at {_headline_instant(largest['delivery_utc'])}",
                detail=(
                    f"The selected forecast was {largest['forecast_mw']:,.0f} MW against an actual of {largest['actual_mw']:,.0f} MW, "
                    f"{direction_text} of {abs(largest['error_mw']):,.0f} MW ({largest['error_mw']:+,.0f} MW signed). "
                    f"That publication was issued at {_headline_instant(largest['forecast_publish_local'])}."
                ),
            )
        )

    if metrics.bias_mw is not None and metrics.mean_actual_mw:
        relative = metrics.bias_mw / metrics.mean_actual_mw * 100.0
        if abs(relative) < 2.0:
            insights.append(
                InsightItem(
                    severity="info",
                    title="Forecast bias is close to neutral",
                    detail=(
                        f"Mean signed error is {metrics.bias_mw:+,.0f} MW, which is {relative:+.1f}% of mean actual wind "
                        f"generation of {metrics.mean_actual_mw:,.0f} MW over {metrics.n_observations} matched periods."
                    ),
                )
            )
        else:
            bias_word = "overforecasting" if metrics.bias_mw > 0 else "underforecasting"
            insights.append(
                InsightItem(
                    severity="attention",
                    title=f"Systematic {bias_word} detected",
                    detail=(
                        f"Mean signed error is {metrics.bias_mw:+,.0f} MW ({relative:+.1f}% of mean actual wind generation), "
                        f"so the forecast available at this cutoff ran {'high' if metrics.bias_mw > 0 else 'low'} on average."
                    ),
                )
            )

    if metrics.overforecast_pct is not None:
        insights.append(
            InsightItem(
                severity="info",
                title=f"{metrics.overforecast_pct:.0f}% of matched periods were overforecast",
                detail=(
                    f"{metrics.overforecast_count} of {metrics.n_observations} matched periods had forecast above actual, "
                    f"{metrics.underforecast_count} were below actual and {metrics.exact_count} matched exactly."
                ),
            )
        )

    lead = frame["lead_hours"].dropna()
    if not lead.empty:
        insights.append(
            InsightItem(
                severity="info",
                title="Realised forecast lead time",
                detail=(
                    f"Selected publications were issued a median of {lead.median():.1f} h before delivery "
                    f"(range {lead.min():.1f} h to {lead.max():.1f} h), reflecting the WINDFOR publication cycle rather than a fixed horizon."
                ),
            )
        )

    if quality.missing_forecast or quality.missing_actual:
        insights.append(
            InsightItem(
                severity="attention",
                title="Incomplete observation coverage",
                detail=(
                    f"{quality.missing_forecast} delivery periods have no eligible forecast and {quality.missing_actual} have no actual record. "
                    f"Metrics use only the {quality.matched} matched periods ({quality.coverage_pct:.1f}% coverage)."
                ),
            )
        )

    if metrics.wape_pct is not None:
        insights.append(
            InsightItem(
                severity="info",
                title="Error relative to generation volume",
                detail=(
                    f"Total absolute error of {frame['abs_error_mw'].sum():,.0f} MW against total actual generation of "
                    f"{frame['actual_mw'].sum():,.0f} MW gives a WAPE of {metrics.wape_pct:.2f}%."
                ),
            )
        )

    return insights


def build_overview(snapshot: DatasetSnapshot, settings: Settings, request: SelectionRequest) -> OverviewResponse:
    result = run_selection(snapshot, request)
    frame = result.frame
    metrics = compute_metrics(frame)
    quality = build_quality(result, snapshot)
    largest = largest_absolute_error(frame)

    return OverviewResponse(
        meta=build_meta(snapshot, settings),
        selection=build_selection_info(request),
        metrics=MetricsModel(**metrics.as_dict()),
        quality=quality,
        series=series_from_frame(frame),
        largest_error=LargestError(**largest) if largest else None,
        uncertainty=build_uncertainty(frame, metrics),
        insights=build_insights(frame, metrics, quality, request),
        scope_note=ASSIGNMENT_SCOPE_NOTE,
    )


def build_forecast(
    snapshot: DatasetSnapshot,
    settings: Settings,
    request: SelectionRequest,
    status_filter: str | None = None,
    direction_filter: str | None = None,
    search: str | None = None,
) -> ForecastResponse:
    result = run_selection(snapshot, request)
    frame = result.frame.copy()

    if status_filter and status_filter != "all":
        frame = frame[frame["status"] == status_filter]
    if direction_filter and direction_filter != "all":
        frame = frame[frame["direction"] == direction_filter]
    if search:
        needle = search.strip().lower()
        frame = frame[frame["delivery_local"].str.lower().str.contains(needle, na=False)]

    truncated = len(frame) > TABLE_ROW_LIMIT
    limited = frame.head(TABLE_ROW_LIMIT)
    metrics = compute_metrics(result.frame)

    return ForecastResponse(
        meta=build_meta(snapshot, settings),
        selection=build_selection_info(request),
        metrics=MetricsModel(**metrics.as_dict()),
        quality=build_quality(result, snapshot),
        rows=forecast_rows_from_frame(limited),
        row_count=int(len(limited)),
        truncated=truncated,
        filters_applied={
            "status": status_filter or "all",
            "direction": direction_filter or "all",
            "search": search or "",
        },
    )


def build_accuracy(snapshot: DatasetSnapshot, settings: Settings, request: SelectionRequest) -> AccuracyResponse:
    result = run_selection(snapshot, request)
    frame = result.frame
    metrics = compute_metrics(frame)
    quality = build_quality(result, snapshot)
    split = direction_split(frame)
    histogram = [HistogramBin(**item) for item in error_histogram(frame)]

    notes = list(metrics.notes)
    notes.append(
        "Metrics are computed only from delivery periods with both a valid eligible forecast and a valid actual value."
    )
    if quality.duplicate_forecasts_removed or quality.duplicate_actuals_removed:
        notes.append(
            f"{quality.duplicate_forecasts_removed} duplicate forecast records and {quality.duplicate_actuals_removed} duplicate actual records were removed before matching."
        )

    return AccuracyResponse(
        meta=build_meta(snapshot, settings),
        selection=build_selection_info(request),
        metrics=MetricsModel(**metrics.as_dict()),
        quality=quality,
        histogram=histogram,
        direction=DirectionSplit(**split),
        by_period=forecast_rows_from_frame(frame),
        explanations=METRIC_EXPLANATIONS,
        notes=notes,
        scope_note=ASSIGNMENT_SCOPE_NOTE,
    )


def _comparison_label(lead_hours: float | None, mode: str, cutoff: datetime | None) -> str:
    if mode == CUTOFF_MODE_ABSOLUTE and cutoff is not None:
        return f"Fixed cutoff {format_london(cutoff)}"
    return f"{lead_hours:g} h lead cutoff"


def build_compare(
    snapshot: DatasetSnapshot,
    settings: Settings,
    start_request: SelectionRequest,
    lead_hours_list: Iterable[float] | None,
    absolute_cutoffs: Iterable[str] | None = None,
    baseline_lead_hours: float | None = None,
) -> CompareResponse:
    leads: list[float] = [float(value) for value in (lead_hours_list or settings.allowed_lead_hours)]
    if not leads:
        raise AnalysisError("At least one lead time is required for a comparison")

    for lead in leads:
        if lead <= 0 or lead > 96:
            raise AnalysisError("Each lead time must be greater than 0 and no more than 96 hours")

    selections: list[tuple[str, str, float | None, datetime | None, SelectionResult]] = []
    for lead in sorted(set(leads)):
        request = SelectionRequest(
            start_day=start_request.start_day,
            end_day=start_request.end_day,
            mode=CUTOFF_MODE_ROLLING,
            lead_hours=lead,
        )
        selections.append((_comparison_label(lead, CUTOFF_MODE_ROLLING, None), CUTOFF_MODE_ROLLING, lead, None, run_selection(snapshot, request)))

    for raw_cutoff in absolute_cutoffs or []:
        cutoff = parse_cutoff_arg(raw_cutoff)
        if cutoff is None:
            continue
        request = SelectionRequest(
            start_day=start_request.start_day,
            end_day=start_request.end_day,
            mode=CUTOFF_MODE_ABSOLUTE,
            cutoff=cutoff,
        )
        selections.append((_comparison_label(None, CUTOFF_MODE_ABSOLUTE, cutoff), CUTOFF_MODE_ABSOLUTE, None, cutoff, run_selection(snapshot, request)))

    if not selections:
        raise AnalysisError("No comparison selection could be constructed")

    period_sets = []
    for _, _, _, _, result in selections:
        matched = matched_frame(result.frame)
        period_sets.append(set(matched["period_start_utc"]) if not matched.empty else set())

    common_periods = set.intersection(*period_sets) if all(period_sets) else set()

    entries: list[CompareEntry] = []
    common_metrics: list[CompareCommonMetrics] = []
    for label, mode, lead, cutoff, result in selections:
        matched = matched_frame(result.frame)
        native_metrics = compute_metrics(result.frame)
        notes: list[str] = []
        if matched.empty:
            notes.append("No matched observation is available for this cutoff.")
        if common_periods:
            subset = matched[matched["period_start_utc"].isin(common_periods)]
            subset_metrics = compute_metrics(subset)
        else:
            subset_metrics = MetricSet()
        entries.append(
            CompareEntry(
                label=label,
                mode=mode,
                lead_hours=lead,
                cutoff_local=format_london(cutoff) if cutoff else None,
                metrics=MetricsModel(**native_metrics.as_dict()),
                n_common=subset_metrics.n_observations,
                n_native=native_metrics.n_observations,
                notes=notes,
            )
        )
        common_metrics.append(
            CompareCommonMetrics(
                label=label,
                lead_hours=lead,
                mae_mw=subset_metrics.mae_mw,
                rmse_mw=subset_metrics.rmse_mw,
                bias_mw=subset_metrics.bias_mw,
                wape_pct=subset_metrics.wape_pct,
                n_observations=subset_metrics.n_observations,
            )
        )

    ranked = [item for item in common_metrics if item.mae_mw is not None]
    ranked.sort(key=lambda item: item.mae_mw)
    if len(ranked) >= 2:
        best, runner_up = ranked[0], ranked[1]
        improvement = (runner_up.mae_mw - best.mae_mw) / runner_up.mae_mw * 100.0 if runner_up.mae_mw else 0.0
        if improvement >= 2.0:
            verdict = (
                f"On the {best.n_observations} common delivery periods, {best.label} has the lowest MAE at "
                f"{best.mae_mw:,.0f} MW, {improvement:.1f}% below the next best cutoff ({runner_up.label}, {runner_up.mae_mw:,.0f} MW). "
                "This conclusion is drawn on MAE only; bias or WAPE may rank the cutoffs differently."
            )
        else:
            verdict = (
                f"On the {best.n_observations} common delivery periods the cutoffs are not materially different under MAE: "
                f"{best.label} scores {best.mae_mw:,.0f} MW against {runner_up.label} at {runner_up.mae_mw:,.0f} MW "
                f"({improvement:.1f}% difference). No cutoff is claimed to be more accurate."
            )
    elif len(ranked) == 1:
        verdict = f"Only {ranked[0].label} produces matched observations, so no comparison is possible."
    else:
        verdict = "No cutoff produced matched observations on common delivery periods, so no comparison is possible."

    disclosures = [
        f"Comparison uses the {len(common_periods)} delivery periods that are matched under every selected cutoff, so differences are not caused by differing sample composition.",
        "Native observation counts per cutoff are reported separately because longer lead times can lose delivery periods that were never published early enough.",
        "Realised lead time can be shorter than the requested cutoff because WINDFOR publishes on an irregular cycle.",
    ]

    return CompareResponse(
        meta=build_meta(snapshot, settings),
        quality=build_quality(selections[0][4], snapshot),
        entries=entries,
        common_metrics=common_metrics,
        common_period_count=len(common_periods),
        recommended_metric="mae_mw",
        verdict=verdict,
        disclosures=disclosures,
        explanations=METRIC_EXPLANATIONS,
    )


def build_provenance(snapshot: DatasetSnapshot, settings: Settings, request: SelectionRequest) -> ProvenanceResponse:
    result = run_selection(snapshot, request)
    quality = build_quality(result, snapshot)
    coverage = snapshot_coverage(snapshot)

    limitations = [
        "WINDFOR delivery targets are hourly while FUELHH actuals are half-hourly; each half-hour uses the forecast published for the hour containing it.",
        "WINDFOR publishes on an irregular 2-4 hour cycle, so the forecast actually used is the latest published at or before the cutoff rather than a fixed horizon product.",
        "The Elexon API limits each request to a 7-day range, so the analysis period is retrieved in multiple chunks and any chunk failure is reported as a partial retrieval.",
        "Publication timestamps describe when Elexon published a record, not the internal model run time of the underlying forecast.",
        ASSIGNMENT_SCOPE_NOTE,
    ]

    return ProvenanceResponse(
        meta=build_meta(snapshot, settings),
        sources=describe_sources(),
        analysis_range={
            "start_date": settings.analysis_start_date,
            "end_date": settings.analysis_end_date,
            "forecast_publish_from": (snapshot.forecasts["publish_time_utc"].min().isoformat() if not snapshot.forecasts.empty else None),
            "forecast_publish_to": (snapshot.forecasts["publish_time_utc"].max().isoformat() if not snapshot.forecasts.empty else None),
        },
        retrieval={
            "retrieval_timestamp_utc": snapshot.retrieval_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "retrieval_timestamp_local": format_london(snapshot.retrieval_timestamp),
            "duration_ms": snapshot.retrieval_duration_ms,
            "actual_chunks": chunk_details(snapshot.actual_retrieval),
            "forecast_chunks": chunk_details(snapshot.forecast_retrieval),
            "actual_request_urls": snapshot.actual_retrieval.request_urls,
            "forecast_request_urls": snapshot.forecast_retrieval.request_urls,
            "data_mode": snapshot.data_mode,
        },
        counts=ProvenanceRecordCounts(
            actual_records_raw=snapshot.actual_report.parsed,
            actual_records_used=snapshot.actual_count,
            forecast_records_raw=snapshot.forecast_report.parsed,
            forecast_records_used=snapshot.forecast_count,
            matched_observations=quality.matched,
            missing_actual=quality.missing_actual,
            missing_forecast=quality.missing_forecast,
            duplicate_actuals_removed=snapshot.actual_report.duplicates_removed,
            duplicate_forecasts_removed=snapshot.forecast_report.duplicates_removed,
            invalid_actuals_removed=snapshot.actual_report.dropped_invalid_generation + snapshot.actual_report.dropped_invalid_timestamp,
            invalid_forecasts_removed=snapshot.forecast_report.dropped_invalid_generation + snapshot.forecast_report.dropped_invalid_timestamp,
        ),
        coverage=coverage,
        duplicates={
            "actual_duplicates_removed": snapshot.actual_report.duplicates_removed,
            "forecast_duplicates_removed": snapshot.forecast_report.duplicates_removed,
            "wrong_fuel_type_dropped": snapshot.actual_report.dropped_wrong_fuel_type,
            "negative_actual_values": snapshot.actual_report.negative_values,
            "negative_forecast_values": snapshot.forecast_report.negative_values,
        },
        cache=CacheInfo(**describe_cache(snapshot, settings)),
        warnings=quality.warnings,
        failures=failure_details(snapshot),
        limitations=limitations,
        chunk_plan={
            "actuals": chunk_details(snapshot.actual_retrieval),
            "forecasts": chunk_details(snapshot.forecast_retrieval),
        },
        request_parameters={
            "actuals": {
                "settlementDateFrom": settings.analysis_start_date,
                "settlementDateTo": settings.analysis_end_date,
                "fuelType": "WIND",
            },
            "forecasts": {
                "publishDateTimeFrom": snapshot.forecasts["publish_time_utc"].min().strftime("%Y-%m-%dT%H:%M:%SZ")
                if not snapshot.forecasts.empty
                else None,
                "publishDateTimeTo": snapshot.forecasts["publish_time_utc"].max().strftime("%Y-%m-%dT%H:%M:%SZ")
                if not snapshot.forecasts.empty
                else None,
            },
            "maximum_window_days_per_request": settings.elexon_max_chunk_days,
        },
    )


def build_records(snapshot: DatasetSnapshot, settings: Settings, request: SelectionRequest) -> RecordsResponse:
    result = run_selection(snapshot, request)
    frame = result.frame
    truncated = len(frame) > TABLE_ROW_LIMIT
    limited = frame.head(TABLE_ROW_LIMIT)
    return RecordsResponse(
        meta=build_meta(snapshot, settings),
        selection=build_selection_info(request),
        rows=forecast_rows_from_frame(limited),
        row_count=int(len(limited)),
        truncated=truncated,
    )


def build_metadata(snapshot: DatasetSnapshot, settings: Settings) -> MetadataResponse:
    days = pd.date_range(settings.analysis_start_date, settings.analysis_end_date, freq="D")
    return MetadataResponse(
        meta=build_meta(snapshot, settings),
        analysis_dates=[day.date().isoformat() for day in days],
        default_lead_hours=settings.default_lead_hours,
        allowed_lead_hours=list(settings.allowed_lead_hours),
        cutoff_modes=CUTOFF_MODES,
        metric_definitions=METRIC_EXPLANATIONS,
        error_sign_convention="error = forecast - actual. Positive values indicate overforecasting, negative values indicate underforecasting. All generation values are average MW over the delivery period.",
        scope_note=ASSIGNMENT_SCOPE_NOTE,
    )


def provenance_counts(snapshot: DatasetSnapshot, request: SelectionRequest) -> ProvenanceRecordCounts:
    result = run_selection(snapshot, request)
    quality = build_quality(result, snapshot)
    return ProvenanceRecordCounts(
        actual_records_raw=snapshot.actual_report.parsed,
        actual_records_used=snapshot.actual_count,
        forecast_records_raw=snapshot.forecast_report.parsed,
        forecast_records_used=snapshot.forecast_count,
        matched_observations=quality.matched,
        missing_actual=quality.missing_actual,
        missing_forecast=quality.missing_forecast,
        duplicate_actuals_removed=snapshot.actual_report.duplicates_removed,
        duplicate_forecasts_removed=snapshot.forecast_report.duplicates_removed,
        invalid_actuals_removed=snapshot.actual_report.dropped_invalid_generation + snapshot.actual_report.dropped_invalid_timestamp,
        invalid_forecasts_removed=snapshot.forecast_report.dropped_invalid_generation + snapshot.forecast_report.dropped_invalid_timestamp,
    )


def summary_for_refresh(snapshot: DatasetSnapshot) -> dict[str, Any]:
    return {
        "retrieval_timestamp_utc": snapshot.retrieval_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "retrieval_timestamp_local": format_london(snapshot.retrieval_timestamp),
        "duration_ms": snapshot.retrieval_duration_ms,
        "actual_records_used": snapshot.actual_count,
        "forecast_records_used": snapshot.forecast_count,
        "data_mode": snapshot.data_mode,
    }


def utc_now_iso() -> str:
    return format_utc(datetime.now(timezone.utc))
