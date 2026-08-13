from __future__ import annotations

import hashlib
import logging
import mimetypes
import pathlib
import re
import uuid
from urllib.parse import urlsplit, urlunsplit

import httpx

from api.db import SessionLocal
from api.models.movie import Movie
from api.utils.provider_errors import format_provider_error

logger = logging.getLogger("vault966")

POSTER_CACHE_DIR = (
    pathlib.Path.home() / "Library" / "Application Support" / "Vault966" / "cache" / "posters"
)
ALLOWED_POSTER_SIZES = {"w185", "w342"}
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_POSTER_BYTES = 2 * 1024 * 1024
_TMDB_IMAGE_HOSTS = {"image.tmdb.org", "media.themoviedb.org"}
_TMDB_POSTER_PATH = re.compile(r"^/t/p/[^/]+/[^/]+\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)
_AMAZON_IMAGE_HOST = "m.media-amazon.com"
_AMAZON_POSTER_PATH = re.compile(
    r"^/images/M/[^/]+\.(?:jpg|jpeg|png|webp)$",
    re.IGNORECASE,
)


def poster_source_url(value: object, size: str) -> str:
    if size not in ALLOWED_POSTER_SIZES:
        raise ValueError("Unsupported poster size")

    parsed = urlsplit(str(value or "").strip())
    if (
        parsed.scheme == "https"
        and parsed.hostname == _AMAZON_IMAGE_HOST
        and _AMAZON_POSTER_PATH.fullmatch(parsed.path)
    ):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))

    if (
        parsed.scheme != "https"
        or parsed.hostname not in _TMDB_IMAGE_HOSTS
        or not _TMDB_POSTER_PATH.fullmatch(parsed.path)
    ):
        raise ValueError("Unsupported poster source")

    parts = parsed.path.split("/")
    parts[3] = size
    return urlunsplit(("https", "image.tmdb.org", "/".join(parts), parsed.query, ""))


def is_cacheable_poster_source(value: object) -> bool:
    try:
        poster_source_url(value, "w185")
    except ValueError:
        return False
    return True


def cache_stem(movie_id: int, size: str, source_url: str) -> str:
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    return f"{movie_id}-{size}-{digest}"


def cached_poster_path(cache_dir: pathlib.Path, stem: str) -> pathlib.Path | None:
    for extension in ALLOWED_IMAGE_TYPES.values():
        candidate = cache_dir / f"{stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def download_poster(
    source_url: str,
    cache_dir: pathlib.Path,
    stem: str,
    *,
    client: httpx.Client | None = None,
) -> pathlib.Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=httpx.Timeout(10.0, connect=3.0))
    try:
        response = client.get(source_url)
        response.raise_for_status()
    finally:
        if owns_client:
            client.close()

    content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
    extension = ALLOWED_IMAGE_TYPES.get(content_type)
    if not extension or not response.content or len(response.content) > MAX_POSTER_BYTES:
        raise ValueError("Unsupported poster response")

    destination = cache_dir / f"{stem}{extension}"
    temporary = cache_dir / f".{stem}-{uuid.uuid4().hex}.tmp"
    temporary.write_bytes(response.content)
    temporary.replace(destination)
    return destination


def poster_media_type(path: pathlib.Path) -> str:
    return mimetypes.types_map.get(path.suffix.lower(), "application/octet-stream")


def cache_movie_posters(
    movie_id: int,
    *,
    sizes: tuple[str, ...] = ("w185", "w342"),
    cache_dir: pathlib.Path = POSTER_CACHE_DIR,
) -> tuple[int, int]:
    with SessionLocal() as db:
        movie = db.get(Movie, movie_id)
        if movie is None or not movie.poster_url:
            return 0, 0
        poster_url = movie.poster_url

    downloaded = 0
    cached = 0
    with httpx.Client(timeout=httpx.Timeout(15.0, connect=4.0)) as client:
        for size in sizes:
            source_url = poster_source_url(poster_url, size)
            stem = cache_stem(movie_id, size, source_url)
            if cached_poster_path(cache_dir, stem):
                cached += 1
                continue
            download_poster(source_url, cache_dir, stem, client=client)
            downloaded += 1
    return downloaded, cached


def cache_movie_posters_safely(movie_id: int) -> None:
    try:
        downloaded, cached = cache_movie_posters(movie_id)
    except (httpx.HTTPError, OSError, ValueError) as exc:
        logger.error(
            "%s",
            format_provider_error("poster_cache_failed", exc),
            extra={"extra": {"movie_id": movie_id}},
        )
        return
    logger.info(
        "poster_cache_complete",
        extra={
            "extra": {
                "movie_id": movie_id,
                "downloaded": downloaded,
                "cached": cached,
            }
        },
    )
