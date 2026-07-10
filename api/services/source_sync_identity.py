from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from api.services.source_sync_contracts import (
    ResearchLink,
    ResearchLinkSet,
    SourceSyncError,
)

if TYPE_CHECKING:
    from api.models.movie import Movie

SPACE_RE = re.compile(r"\s+")
DIRECTOR_SPLIT_RE = re.compile(r"\s*(?:,|&|;|\band\b)\s*", re.IGNORECASE)
IMDB_ID_RE = re.compile(r"^tt[0-9]{7,10}$")
TRAILING_YEAR_RE = re.compile(r"\s*\((?:18|19|20)\d{2}\)\s*$")
EDITION_SUFFIX_RE = re.compile(
    r"\s*(?:\(|[-:])\s*(?:unrated|extended(?: edition| cut)?|director'?s cut|"
    r"special edition|theatrical cut|restored edition)\)?\s*$",
    re.IGNORECASE,
)
EDITION_PAREN_RE = re.compile(
    r"\s*\((?=[^)]*(?:unrated|extended|director'?s cut|special edition|"
    r"theatrical cut|restored edition))[^)]*\)\s*$",
    re.IGNORECASE,
)


def clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def limited_text(
    value: object,
    *,
    field_name: str,
    max_length: int,
    row_number: int,
) -> str | None:
    text = clean_text(value)
    if text is not None and len(text) > max_length:
        raise SourceSyncError(f"Row {row_number} {field_name} exceeds {max_length} characters")
    return text


def normalize_title(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return SPACE_RE.sub(" ", text).strip()


def clean_research_title(value: object) -> str:
    title = clean_text(value) or ""
    title = TRAILING_YEAR_RE.sub("", title)
    title = EDITION_PAREN_RE.sub("", title)
    title = EDITION_SUFFIX_RE.sub("", title)
    return SPACE_RE.sub(" ", title).strip()[:200]


def _valid_imdb_id(value: object) -> str | None:
    text = clean_text(value)
    if text and IMDB_ID_RE.fullmatch(text):
        return text
    return None


def _valid_tmdb_id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if 0 < number <= 2_147_483_647:
        return number
    return None


def parse_directors(value: object) -> tuple[str, ...]:
    text = clean_text(value)
    if text is None or text.casefold() in {"unknown", "not found", "n/a"}:
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for part in DIRECTOR_SPLIT_RE.split(text):
        name = SPACE_RE.sub(" ", part).strip()
        key = normalize_title(name)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return tuple(names)


def normalized_directors(value: object) -> tuple[str, ...]:
    return tuple(sorted(normalize_title(name) for name in parse_directors(value)))


def build_research_links(
    *,
    source_title: str,
    source_year: int | None,
    source_director: str | None = None,
    movie: Movie | None = None,
) -> ResearchLinkSet:
    search_title = clean_research_title(source_title) or source_title[:200]
    query_parts = [search_title]
    if source_year:
        query_parts.append(str(source_year))
    director_names = parse_directors(source_director)
    if director_names:
        query_parts.append(" and ".join(director_names)[:100])
    query = " ".join(query_parts)[:320]

    current: list[ResearchLink] = []
    tmdb_id = _valid_tmdb_id(movie.tmdb_id if movie else None)
    if tmdb_id is not None:
        current.append(
            ResearchLink(
                label="Open current TMDB",
                url=f"https://www.themoviedb.org/movie/{tmdb_id}",
                provider="tmdb",
                link_type="current",
            )
        )
    imdb_id = _valid_imdb_id(movie.imdb_id if movie else None)
    if imdb_id is not None:
        current.append(
            ResearchLink(
                label="Open current IMDb",
                url=f"https://www.imdb.com/title/{imdb_id}/",
                provider="imdb",
                link_type="current",
            )
        )

    searches = (
        ResearchLink(
            label="Search TMDB",
            url="https://www.themoviedb.org/search/movie?" + urlencode({"query": query}),
            provider="tmdb",
            link_type="search",
        ),
        ResearchLink(
            label="Search IMDb",
            url="https://www.imdb.com/find/?" + urlencode({"q": query, "s": "tt", "ttype": "ft"}),
            provider="imdb",
            link_type="search",
        ),
    )
    return ResearchLinkSet(
        current=tuple(current),
        searches=searches,
        search_title=search_title,
    )


__all__ = [
    "build_research_links",
    "clean_research_title",
    "clean_text",
    "limited_text",
    "normalize_title",
    "normalized_directors",
    "parse_directors",
]
