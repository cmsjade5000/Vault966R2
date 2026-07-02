from __future__ import annotations

from pydantic import BaseModel, Field


class MovieTrailerRead(BaseModel):
    site: str = Field(pattern=r"^youtube$")
    key: str = Field(pattern=r"^[A-Za-z0-9_-]{6,128}$")
    name: str | None = None
    url: str
    embed_url: str
