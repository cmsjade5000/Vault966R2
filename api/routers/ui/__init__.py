from __future__ import annotations

from fastapi import APIRouter

from . import (
    detail,
    discover,
    events,
    first_import,
    flags,
    grid,
    login,
    manual_add,
    posters,
    review,
    source_sync,
    top,
)

router = APIRouter(tags=["ui"])
router.include_router(login.router, tags=["ui"])
router.include_router(grid.router, tags=["ui"])
router.include_router(discover.router, tags=["ui"])
router.include_router(posters.router, tags=["ui"])
router.include_router(top.router, tags=["ui"])
router.include_router(detail.router, tags=["ui"])
router.include_router(manual_add.router, tags=["ui"])
router.include_router(first_import.router, tags=["ui"])
router.include_router(flags.router, tags=["ui"])
router.include_router(review.router, tags=["ui"])
router.include_router(source_sync.router, tags=["ui"])
router.include_router(events.router, tags=["ui"])

__all__ = ["router"]
