from functools import lru_cache

from app.config.settings import Settings, get_settings
from app.services.repository import DatasetRepository


@lru_cache
def get_repository() -> DatasetRepository:
    return DatasetRepository(get_settings())


def settings_dependency() -> Settings:
    return get_settings()
