"""Exercise real settings sources with synthetic configuration only."""

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from api.config import Settings


@pytest.fixture(autouse=True)
def isolated_settings_environment(monkeypatch):
    for name, field in Settings.model_fields.items():
        for key in (name, field.validation_alias):
            if isinstance(key, str):
                monkeypatch.delenv(key, raising=False)
                monkeypatch.delenv(key.lower(), raising=False)


def load_settings(source, values, tmp_path, monkeypatch):
    if source == "environment":
        for key, value in values.items():
            monkeypatch.setenv(key, value)
        return Settings(_env_file=None)
    env_file = tmp_path / "synthetic.env"
    env_file.write_text("".join(f"{key}='{value}'\n" for key, value in values.items()))
    return Settings(_env_file=env_file)


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_auth_aliases_and_scalar_types(source, tmp_path, monkeypatch):
    settings = load_settings(
        source,
        {
            "LOGIN_SESSION_SECRET": "synthetic-signing-key",
            "LOGIN_ACCESS_KEY_USER_A": "synthetic-user",
            "LOGIN_PASSCODE_USER_A": "synthetic-password",
            "ASSISTANT_API_TOKEN": "synthetic-assistant-token",
            "DISABLE_AUTH": "false",
            "SEMANTIC_SEARCH_ENABLED": "true",
            "LOGIN_SESSION_TTL_HOURS": "24",
            "SEMANTIC_BACKFILL_SLEEP_SECONDS": "0.75",
            "DATABASE_URL": "sqlite://",
            "UNKNOWN_SYNTHETIC_SETTING": "ignored",
        },
        tmp_path,
        monkeypatch,
    )
    assert settings.login_session_secret == "synthetic-signing-key"
    assert settings.login_access_key_user_a == "synthetic-user"
    assert settings.login_passcode_user_a == "synthetic-password"
    assert settings.assistant_access_token == "synthetic-assistant-token"
    assert settings.disable_auth is False
    assert settings.semantic_search_enabled is True
    assert settings.login_session_ttl_hours == 24
    assert settings.semantic_backfill_sleep == 0.75
    assert settings.database_url == "sqlite://"


def test_environment_overrides_dotenv_auth_configuration(tmp_path, monkeypatch):
    env_file = tmp_path / "synthetic.env"
    env_file.write_text("LOGIN_SESSION_SECRET=file-key\nDISABLE_AUTH=true\n")
    monkeypatch.setenv("LOGIN_SESSION_SECRET", "environment-key")
    monkeypatch.setenv("DISABLE_AUTH", "false")
    settings = Settings(_env_file=env_file)
    assert settings.login_session_secret == "environment-key"
    assert settings.disable_auth is False


@pytest.mark.parametrize("source", ["environment", "dotenv"])
@pytest.mark.parametrize(
    "value, expected",
    [
        ("[]", []),
        (
            '["https://example.test/path", "https://example.test", "http://localhost:8000"]',
            ["https://example.test", "http://localhost:8000"],
        ),
    ],
)
def test_cors_json_source_normalization(source, value, expected, tmp_path, monkeypatch):
    settings = load_settings(source, {"CORS_ORIGINS": value}, tmp_path, monkeypatch)
    assert settings.cors_origins == expected


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_invalid_cors_origin_is_rejected(source, tmp_path, monkeypatch):
    with pytest.raises(ValidationError, match="Invalid CORS origin"):
        load_settings(source, {"CORS_ORIGINS": '["file:///tmp/synthetic"]'}, tmp_path, monkeypatch)


@pytest.mark.parametrize("source", ["environment", "dotenv"])
@pytest.mark.parametrize("value", ["", "https://one.test,https://two.test"])
def test_non_json_cors_source_retains_baseline_rejection(source, value, tmp_path, monkeypatch):
    # Source JSON decoding precedes the custom field validator. Changing that
    # existing behavior belongs in a separate configuration change.
    with pytest.raises(SettingsError, match="cors_origins"):
        load_settings(source, {"CORS_ORIGINS": value}, tmp_path, monkeypatch)


def test_missing_cors_uses_empty_default():
    assert Settings(_env_file=None).cors_origins == []
