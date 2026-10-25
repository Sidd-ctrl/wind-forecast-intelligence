from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config.settings import get_settings
from app.services.analysis import AnalysisError, DATA_VERSION
from app.services.elexon_client import ElexonError

settings = get_settings()
logger = logging.getLogger("aeron")
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AERON backend starting in %s data mode", settings.data_mode)
    yield
    logger.info("AERON backend shutting down")


app = FastAPI(
    title="AERON — Wind Forecast Intelligence API",
    description=(
        "Historical analysis of Elexon BMRS wind generation forecasts (WINDFOR) against actual wind generation (FUELHH) "
        "for January 2026, selecting only publications available at a configurable decision cutoff."
    ),
    version=DATA_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(router)


def error_payload(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


@app.exception_handler(AnalysisError)
async def analysis_error_handler(request: Request, exc: AnalysisError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_payload(exc.code, exc.message, exc.details))


@app.exception_handler(ElexonError)
async def elexon_error_handler(request: Request, exc: ElexonError) -> JSONResponse:
    logger.warning("Elexon integration error: %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content=error_payload(exc.code, exc.message, exc.details))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    issues = [
        {"field": ".".join(str(part) for part in error.get("loc", [])), "reason": error.get("msg", "invalid value")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_payload("invalid_request", "One or more query parameters are invalid.", {"issues": issues}),
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled backend error")
    return JSONResponse(
        status_code=500,
        content=error_payload("internal_error", "The backend could not complete the request. Please retry."),
    )


@app.get("/", include_in_schema=False)
def index() -> dict:
    return {
        "product": "AERON",
        "version": DATA_VERSION,
        "documentation": "/docs",
        "health": "/health",
    }
