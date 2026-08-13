from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app_name": settings.app_name,
    }


@router.get("/livez")
def liveness():
    return {"status": "alive"}


@router.get(
    "/readyz",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database readiness check failed."}
    },
)
def readiness(db: Session = Depends(get_db)):
    try:
        database_ready = db.execute(text("SELECT 1")).scalar_one() == 1
    except SQLAlchemyError:
        database_ready = False

    if not database_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check failed.",
        )

    return {"status": "ready"}
