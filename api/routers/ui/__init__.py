from __future__ import annotations

from fastapi import APIRouter

from . import detail, grid, manual_add

router = APIRouter(tags=["ui"])
router.include_router(grid.router, tags=["ui"])
router.include_router(detail.router, tags=["ui"])
router.include_router(manual_add.router, tags=["ui"])

__all__ = ["router"]
