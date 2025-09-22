from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FlicMemoryRead(BaseModel):
    id: int
    movie_id: int
    created_at: datetime

    class Config:
        from_attributes = True
