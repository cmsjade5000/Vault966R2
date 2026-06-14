from __future__ import annotations

import hashlib
import pathlib
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from core.display_titles import display_movie_title

ROOT = pathlib.Path(__file__).resolve().parents[3]
STATIC_ROOT = ROOT / "static"


@lru_cache(maxsize=None)
def _asset_version(path: str) -> str:
    asset = (STATIC_ROOT / path).resolve()
    if not asset.is_relative_to(STATIC_ROOT) or asset.suffix not in {".css", ".js"}:
        raise ValueError(f"Unsupported static asset path: {path}")
    return hashlib.sha256(asset.read_bytes()).hexdigest()[:12]


@pass_context
def static_asset(context, path: str) -> str:
    request = context["request"]
    url = request.url_for("static", path=path)
    return f"{url}?v={_asset_version(path)}"


def poster_image_url(value: object, size: str = "w342") -> str:
    url = str(value or "").strip()
    if not url:
        return ""

    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "image.tmdb.org",
        "media.themoviedb.org",
    }:
        return url

    parts = parsed.path.split("/")
    if len(parts) < 5 or parts[1:3] != ["t", "p"]:
        return url

    parts[3] = size
    return urlunsplit(
        ("https", "image.tmdb.org", "/".join(parts), parsed.query, "")
    )


TEMPLATES = Jinja2Templates(
    directory=str(ROOT / "templates")
)
TEMPLATES.env.filters["display_title"] = display_movie_title
TEMPLATES.env.globals["static_asset"] = static_asset
TEMPLATES.env.globals["poster_image_url"] = poster_image_url

__all__ = ["TEMPLATES", "poster_image_url", "static_asset"]
