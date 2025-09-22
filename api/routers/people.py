from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.db import Base, engine, get_db
from api.deps.auth import require_admin
from api.models.person import Person
from api.schemas.person import PersonCreate, PersonListResponse, PersonRead
from api.utils.pagination import paginate

Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/people", tags=["people"])


@router.get("/", response_model=PersonListResponse)
def list_people(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Person).order_by(Person.name.asc())
    items, total = paginate(query, page=page, page_size=page_size)
    return PersonListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/", response_model=PersonRead, status_code=201)
def create_person(
    payload: PersonCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    person = Person(
        name=payload.name,
        tmdb_id=payload.tmdb_id,
        imdb_id=payload.imdb_id,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person
