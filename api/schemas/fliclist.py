from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class FlicFilters(BaseModel):
    q: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    runtime_max: Optional[int] = None


class FlicPresetCreate(BaseModel):
    name: str
    filters: FlicFilters

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned


class FlicPresetRead(BaseModel):
    id: int
    name: str
    filters: FlicFilters
    created_at: datetime

    class Config:
        from_attributes = True
