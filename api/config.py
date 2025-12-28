import json
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="vault966-r2 API", validation_alias="APP_NAME")
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")
    cors_origins: List[str] = Field(default_factory=list, validation_alias="CORS_ORIGINS")
    admin_token: Optional[str] = Field(default=None, validation_alias="ADMIN_TOKEN")
    tmdb_api_key: Optional[str] = Field(default=None, validation_alias="TMDB_API_KEY")
    omdb_api_key: Optional[str] = Field(default=None, validation_alias="OMDB_API_KEY")
    llm_api_key: Optional[str] = Field(default=None, validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="LLM_BASE_URL",
    )
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value):
        if value in (None, "", []):
            return []

        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    candidates = [str(part).strip() for part in parsed]
                else:
                    candidates = [part.strip() for part in raw.split(",")]
            else:
                candidates = [part.strip() for part in raw.split(",")]
        elif isinstance(value, (list, tuple)):
            candidates = [str(part).strip() for part in value]
        else:
            raise ValueError("CORS_ORIGINS must be a comma separated string or list")

        origins: List[str] = []
        seen = set()
        for candidate in candidates:
            if not candidate:
                continue
            parsed = urlparse(candidate)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"Invalid CORS origin '{candidate}'")
            normalized = f"{parsed.scheme}://{parsed.netloc}"
            if normalized not in seen:
                seen.add(normalized)
                origins.append(normalized)
        return origins


settings = Settings()
