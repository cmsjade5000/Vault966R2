from __future__ import annotations

from fastapi import APIRouter

from . import detail, flags, grid, manual_add, top

router = APIRouter(tags=["ui"])
router.include_router(grid.router, tags=["ui"])
router.include_router(top.router, tags=["ui"])
router.include_router(detail.router, tags=["ui"])
router.include_router(manual_add.router, tags=["ui"])
router.include_router(flags.router, tags=["ui"])

__all__ = ["router"]
