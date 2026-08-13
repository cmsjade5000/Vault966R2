from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.config import settings
from api.db import get_db
from api.schemas.common import ErrorResponse
from api.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app_name": settings.app_name,
    }


@router.get("/livez", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse(status="alive")


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Database readiness check failed.",
            "model": ErrorResponse,
        }
    },
)
def readiness(db: Session = Depends(get_db)) -> ReadinessResponse:
    try:
        database_ready = db.execute(text("SELECT 1")).scalar_one() == 1
    except SQLAlchemyError:
        database_ready = False

    if not database_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check failed.",
        )

    return ReadinessResponse(status="ready")
