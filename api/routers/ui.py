from __future__ import annotations

import importlib
import sys
from types import ModuleType

_pkg = importlib.import_module("api.routers.ui.__init__")
router = _pkg.router

for _name in ("grid", "detail", "manual_add", "top"):
    module: ModuleType = importlib.import_module(f"api.routers.ui.{_name}")
    sys.modules[f"{__name__}.{_name}"] = module

__all__ = ["router"]
