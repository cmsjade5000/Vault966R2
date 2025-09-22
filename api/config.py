import os
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = os.getenv("APP_NAME", "vault966-r2 API")
    database_url: Optional[str] = os.getenv("DATABASE_URL")  # if None -> SQLite default
    cors_origins: List[str] = Field(default_factory=list)
    admin_token: Optional[str] = os.getenv("ADMIN_TOKEN")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, value):
        if value in (None, "", []):
            return []

        if isinstance(value, str):
            candidates = [part.strip() for part in value.split(",")]
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
