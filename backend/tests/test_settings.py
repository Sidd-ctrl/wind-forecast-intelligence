from __future__ import annotations

import pytest

from app.config.settings import Settings


def build(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_defaults_apply_without_any_configuration(monkeypatch):
    monkeypatch.delenv("ALLOWED_LEAD_HOURS", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("DATA_MODE", raising=False)
    settings = build()
    assert settings.allowed_lead_hours == [4, 8, 12, 24, 36, 48]
    assert "http://localhost:5173" in settings.cors_origins
    assert settings.data_mode == "live"


def test_comma_separated_lead_hours_from_environment(monkeypatch):
    monkeypatch.setenv("ALLOWED_LEAD_HOURS", "4,8,12,24,36,48")
    settings = build()
    assert settings.allowed_lead_hours == [4, 8, 12, 24, 36, 48]


def test_comma_separated_lead_hours_from_dotenv_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ALLOWED_LEAD_HOURS=4,8,12,24,36,48\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.allowed_lead_hours == [4, 8, 12, 24, 36, 48]


def test_lead_hours_tolerate_spacing_and_quotes(monkeypatch):
    monkeypatch.setenv("ALLOWED_LEAD_HOURS", ' "4", 8, "12" ')
    assert build().allowed_lead_hours == [4, 8, 12]


def test_lead_hours_accept_json_array(monkeypatch):
    monkeypatch.setenv("ALLOWED_LEAD_HOURS", "[4, 12, 24]")
    assert build().allowed_lead_hours == [4, 12, 24]


def test_lead_hours_accept_json_string_array(monkeypatch):
    monkeypatch.setenv("ALLOWED_LEAD_HOURS", '["4", "12"]')
    assert build().allowed_lead_hours == [4, 12]


def test_single_lead_hour_value(monkeypatch):
    monkeypatch.setenv("ALLOWED_LEAD_HOURS", "24")
    assert build().allowed_lead_hours == [24]


def test_cors_origins_from_comma_separated_environment(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    settings = build()
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_origins_from_dotenv_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("CORS_ORIGINS=https://a.example.com,https://b.example.com\n", encoding="utf-8")
    settings = Settings(_env_file=env_file)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_cors_origins_accept_json_array(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example.com"]')
    assert build().cors_origins == ["https://a.example.com"]


def test_data_mode_validation(monkeypatch):
    monkeypatch.setenv("DATA_MODE", "SAMPLE")
    assert build().data_mode == "sample"
    with pytest.raises(ValueError):
        build(data_mode="production")


def test_invalid_lead_hour_value_is_rejected(monkeypatch):
    monkeypatch.setenv("ALLOWED_LEAD_HOURS", "4,eight,12")
    with pytest.raises(ValueError):
        build()


def test_example_env_file_is_loadable():
    from pathlib import Path

    example = Path(__file__).resolve().parent.parent / ".env.example"
    settings = Settings(_env_file=example)
    assert settings.allowed_lead_hours == [4, 8, 12, 24, 36, 48]
    assert settings.cors_origins
    assert settings.elexon_max_chunk_days == 7
