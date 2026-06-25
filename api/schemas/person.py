from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PersonCreate(BaseModel):
    name: str
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None


class PersonRead(PersonCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PersonListResponse(BaseModel):
    items: List[PersonRead]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(from_attributes=True)
