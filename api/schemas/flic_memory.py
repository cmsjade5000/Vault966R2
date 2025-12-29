from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FlicMemoryRead(BaseModel):
    id: int
    movie_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
