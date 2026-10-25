import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = APP_DIR.parent


def _split_list(raw: str) -> list[str]:
    text = raw.strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            decoded = json.loads(text)
        except ValueError:
            decoded = None
        if isinstance(decoded, list):
            return [str(item).strip() for item in decoded if str(item).strip()]
    return [part.strip().strip("\"'") for part in text.split(",") if part.strip().strip("\"'")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    elexon_base_url: str = "https://data.elexon.co.uk/bmrs/api/v1"
    elexon_timeout_seconds: float = 30.0
    elexon_max_retries: int = 3
    elexon_retry_backoff_seconds: float = 1.5
    elexon_max_chunk_days: int = 7

    analysis_start_date: str = "2026-01-01"
    analysis_end_date: str = "2026-01-31"
    forecast_publish_lookback_days: int = 7
    forecast_publish_lookahead_days: int = 2

    default_lead_hours: int = 12
    allowed_lead_hours: Annotated[List[int], NoDecode] = Field(default_factory=lambda: [4, 8, 12, 24, 36, 48])

    data_mode: str = "live"
    cache_dir: str = str(BACKEND_DIR / ".cache" / "aeron")
    cache_ttl_hours: float = 24.0
    cache_enabled: bool = True

    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    cors_origin_regex: str = r"https://([a-z0-9-]+\.)*vercel\.app"

    log_level: str = "INFO"

    @field_validator("data_mode")
    @classmethod
    def validate_data_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"live", "sample"}:
            raise ValueError("data_mode must be 'live' or 'sample'")
        return normalized

    @field_validator("allowed_lead_hours", mode="before")
    @classmethod
    def parse_lead_hours(cls, value):
        if isinstance(value, str):
            return [int(part) for part in _split_list(value)]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return _split_list(value)
        return value

    @property
    def sample_data_dir(self) -> Path:
        return APP_DIR / "data" / "sample"

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
