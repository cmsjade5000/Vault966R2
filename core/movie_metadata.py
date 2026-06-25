from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field

from api.utils.providers import merge_providers, split_providers
from core.enriched_csv import normalize_countries, normalize_languages
from core.genres import split_and_normalize


NULL_STRINGS = {"", "n/a", "na", "none", "null", "unknown", "nan"}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in NULL_STRINGS:
        return None
    return text


def _coerce_int(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None
    if not number.is_integer():
        return None
    return int(number)


def _coerce_float(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except (TypeError, ValueError):
        return None


def _normalize_imdb_id(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    lowered = text.casefold()
    if not lowered.startswith("tt") or not lowered[2:].isdigit():
        return lowered
    return lowered


def _tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        candidates = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        raw = str(value).strip()
        if raw.startswith("["):
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                candidates = decoded
            else:
                candidates = re.split(r"[|;,]", raw)
        else:
            candidates = re.split(r"[|;,]", raw)

    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        label = _clean_text(item)
        if label is None:
            continue
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _first(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if _clean_text(value) is not None:
            return value
    return None


class MovieMetadata(BaseModel):
    """Canonical metadata exchanged by lookup, imports, and persistence."""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    vault_id: str | None = None
    year: int | None = None
    runtime: int | None = None
    plot: str | None = None
    awards: str | None = None
    certificate: str | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    imdb_rating: float | None = None
    imdb_votes: int | None = None
    metascore: int | None = None
    tomato_meter: int | None = None
    tomato_audience: int | None = None
    rt_score: int | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    directors: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    where_to_watch: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    collection: str | None = None
    release_date: str | None = None
    source: str | None = None
    last_tmdb_fetch_at: datetime | None = None
    last_omdb_fetch_at: datetime | None = None
    tmdb_payload_sha: str | None = None
    omdb_payload_sha: str | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "MovieMetadata":
        stream = _tokens(raw.get("providers_stream"))
        rent = [f"{name} (rent)" for name in _tokens(raw.get("providers_rent"))]
        buy = [f"{name} (buy)" for name in _tokens(raw.get("providers_buy"))]
        provider_value = _first(raw, "where_to_watch", "digital_location")
        providers = merge_providers(split_providers(provider_value), stream, rent, buy)

        language_value = _first(raw, "languages_iso", "languages")
        country_value = _first(raw, "countries_iso", "countries")
        language_text = "; ".join(_tokens(language_value))
        country_text = "; ".join(_tokens(country_value))
        genres = [
            genre
            for genre in split_and_normalize(_tokens(_first(raw, "genres", "genre")))
            if genre.casefold() not in NULL_STRINGS
        ]

        title = _clean_text(raw.get("title")) or ""
        return cls(
            title=title,
            vault_id=_clean_text(_first(raw, "vault_id", "legacy_vault_id")),
            year=_coerce_int(_first(raw, "year", "release_year", "verified_year")),
            runtime=_coerce_int(_first(raw, "runtime", "runtime_min", "minutes")),
            plot=_clean_text(_first(raw, "plot", "plot_summary", "overview", "synopsis")),
            awards=_clean_text(raw.get("awards")),
            certificate=_clean_text(_first(raw, "certificate", "rated")),
            imdb_id=_normalize_imdb_id(raw.get("imdb_id")),
            tmdb_id=_coerce_int(raw.get("tmdb_id")),
            imdb_rating=_coerce_float(raw.get("imdb_rating")),
            imdb_votes=_coerce_int(raw.get("imdb_votes")),
            metascore=_coerce_int(raw.get("metascore")),
            tomato_meter=_coerce_int(raw.get("tomato_meter")),
            tomato_audience=_coerce_int(raw.get("tomato_audience")),
            rt_score=_coerce_int(_first(raw, "rt_score", "rt_percent")),
            poster_url=_clean_text(raw.get("poster_url")),
            backdrop_url=_clean_text(raw.get("backdrop_url")),
            genres=genres,
            moods=_tokens(_first(raw, "moods", "mood")),
            keywords=_tokens(raw.get("keywords")),
            directors=_tokens(_first(raw, "directors", "director")),
            cast=_tokens(_first(raw, "cast", "top_3_actors", "top_billed_actor")),
            where_to_watch=providers,
            languages=normalize_languages(language_text).iso,
            countries=normalize_countries(country_text).iso,
            collection=_clean_text(_first(raw, "collection", "franchise")),
            release_date=_clean_text(raw.get("release_date")),
            source=_clean_text(raw.get("source")),
            last_tmdb_fetch_at=raw.get("last_tmdb_fetch_at"),
            last_omdb_fetch_at=raw.get("last_omdb_fetch_at"),
            tmdb_payload_sha=_clean_text(raw.get("tmdb_payload_sha")),
            omdb_payload_sha=_clean_text(raw.get("omdb_payload_sha")),
        )

    def payload_sha(self) -> str:
        payload = self.model_dump(mode="json", exclude_none=True)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_lookup_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["overview"] = self.plot or ""
        payload["synopsis"] = self.plot or ""
        return payload

    def to_import_record(self) -> dict[str, Any]:
        return {
            **self.model_dump(mode="python"),
            "where_to_watch": list(self.where_to_watch) or None,
            "languages": list(self.languages) or None,
            "countries": list(self.countries) or None,
        }


__all__ = ["MovieMetadata"]
