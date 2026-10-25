from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import get_repository, settings_dependency
from app.config.constants import CUTOFF_MODE_ROLLING
from app.config.settings import Settings
from app.schemas.models import (
    AccuracyResponse,
    CompareResponse,
    ForecastResponse,
    HealthResponse,
    MetadataResponse,
    OverviewResponse,
    ProvenanceResponse,
    RecordsResponse,
    RefreshResponse,
)
from app.services.analysis import (
    DATA_VERSION,
    build_accuracy,
    build_compare,
    build_forecast,
    build_metadata,
    build_overview,
    build_provenance,
    build_records,
    build_selection_request,
    provenance_counts,
    summary_for_refresh,
)
from app.services.csv_export import build_csv, export_filename, frame_from_rows
from app.services.repository import DatasetRepository, describe_cache
from app.utils.timezones import format_utc

router = APIRouter()

StartDate = Annotated[str | None, Query(description="Delivery range start, yyyy-MM-dd")]
EndDate = Annotated[str | None, Query(description="Delivery range end, yyyy-MM-dd")]
DeliveryDate = Annotated[str | None, Query(description="Single delivery date, yyyy-MM-dd")]
Mode = Annotated[str, Query(description="rolling_lead or absolute_cutoff")]
LeadHours = Annotated[float | None, Query(description="Rolling cutoff lead time in hours")]
Cutoff = Annotated[str | None, Query(description="Absolute cutoff instant, ISO-8601 with offset or Z")]


def selection_dependencies(
    settings: Settings = Depends(settings_dependency),
    start_date: StartDate = None,
    end_date: EndDate = None,
    delivery_date: DeliveryDate = None,
    mode: Mode = CUTOFF_MODE_ROLLING,
    lead_hours: LeadHours = None,
    cutoff: Cutoff = None,
):
    return build_selection_request(
        settings=settings,
        start_date=start_date,
        end_date=end_date,
        delivery_date=delivery_date,
        mode=mode,
        lead_hours=lead_hours,
        cutoff=cutoff,
    )


@router.get("/health", response_model=HealthResponse, tags=["status"])
def health(
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> HealthResponse:
    snapshot = repository.peek()
    return HealthResponse(
        status="ok",
        data_mode=settings.data_mode,
        dataset_loaded=snapshot is not None,
        cache_status=describe_cache(snapshot, settings)["status"] if snapshot else None,
        retrieval_timestamp_utc=format_utc(snapshot.retrieval_timestamp) if snapshot else None,
        analysis_start_date=settings.analysis_start_date,
        analysis_end_date=settings.analysis_end_date,
        version=DATA_VERSION,
    )


@router.get("/api/metadata", response_model=MetadataResponse, tags=["metadata"])
def metadata(
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> MetadataResponse:
    snapshot = repository.snapshot()
    return build_metadata(snapshot, settings)


@router.get("/api/overview", response_model=OverviewResponse, tags=["analysis"])
def overview(
    request=Depends(selection_dependencies),
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> OverviewResponse:
    snapshot = repository.snapshot()
    return build_overview(snapshot, settings, request)


@router.get("/api/forecast", response_model=ForecastResponse, tags=["analysis"])
def forecast(
    request=Depends(selection_dependencies),
    status: Annotated[str | None, Query(description="matched, missing_forecast, missing_actual, missing_both")] = None,
    direction: Annotated[str | None, Query(description="overforecast, underforecast, exact")] = None,
    search: Annotated[str | None, Query(description="Free-text filter over the local delivery timestamp")] = None,
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> ForecastResponse:
    snapshot = repository.snapshot()
    return build_forecast(snapshot, settings, request, status_filter=status, direction_filter=direction, search=search)


@router.get("/api/accuracy", response_model=AccuracyResponse, tags=["analysis"])
def accuracy(
    request=Depends(selection_dependencies),
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> AccuracyResponse:
    snapshot = repository.snapshot()
    return build_accuracy(snapshot, settings, request)


@router.get("/api/accuracy/compare", response_model=CompareResponse, tags=["analysis"])
def compare(
    request=Depends(selection_dependencies),
    lead_hours: Annotated[list[float] | None, Query(description="Repeated lead-time values in hours")] = None,
    cutoff: Annotated[list[str] | None, Query(description="Repeated absolute cutoff instants")] = None,
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> CompareResponse:
    snapshot = repository.snapshot()
    return build_compare(snapshot, settings, request, lead_hours_list=lead_hours, absolute_cutoffs=cutoff)


@router.get("/api/data/records", response_model=RecordsResponse, tags=["data"])
def records(
    request=Depends(selection_dependencies),
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> RecordsResponse:
    snapshot = repository.snapshot()
    return build_records(snapshot, settings, request)


@router.get(
    "/api/data/records/export.csv",
    tags=["data"],
    responses={200: {"content": {"text/csv": {}}, "description": "Selected records as CSV"}},
)
def export_records(
    request=Depends(selection_dependencies),
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> Response:
    snapshot = repository.snapshot()
    records_response = build_records(snapshot, settings, request)
    frame = frame_from_rows(records_response.rows)
    body = build_csv(frame, request, snapshot.data_mode)
    filename = export_filename(request, snapshot.data_mode)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/data/refresh", response_model=RefreshResponse, tags=["data"])
def refresh(
    request=Depends(selection_dependencies),
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> RefreshResponse:
    repository.clear_memory()
    snapshot = repository.snapshot(force_refresh=True)
    return RefreshResponse(
        status="refreshed",
        message="Historical datasets were retrieved again from Elexon and the cache was replaced.",
        cache=describe_cache(snapshot, settings),
        retrieval=summary_for_refresh(snapshot),
        counts=provenance_counts(snapshot, request),
    )


@router.get("/api/provenance", response_model=ProvenanceResponse, tags=["data"])
def provenance(
    request=Depends(selection_dependencies),
    repository: DatasetRepository = Depends(get_repository),
    settings: Settings = Depends(settings_dependency),
) -> ProvenanceResponse:
    snapshot = repository.snapshot()
    return build_provenance(snapshot, settings, request)
