from __future__ import annotations

import pathlib

from fastapi.templating import Jinja2Templates

TEMPLATES = Jinja2Templates(
    directory=str(pathlib.Path(__file__).resolve().parents[3] / "templates")
)

__all__ = ["TEMPLATES"]
