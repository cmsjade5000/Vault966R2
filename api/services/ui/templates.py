from __future__ import annotations

import pathlib

from fastapi.templating import Jinja2Templates

from core.display_titles import display_movie_title

TEMPLATES = Jinja2Templates(
    directory=str(pathlib.Path(__file__).resolve().parents[3] / "templates")
)
TEMPLATES.env.filters["display_title"] = display_movie_title

__all__ = ["TEMPLATES"]
