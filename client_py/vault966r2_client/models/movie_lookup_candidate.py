from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieLookupCandidate")


@_attrs_define
class MovieLookupCandidate:
    """
    Attributes:
        title (str):
        backdrop_url (None | str | Unset):
        certificate (None | str | Unset):
        genres (list[str] | Unset):
        imdb_id (None | str | Unset):
        keywords (list[str] | Unset):
        match_confidence (float | None | Unset):
        overview (str | Unset):  Default: ''.
        poster_url (None | str | Unset):
        release_date (None | str | Unset):
        runtime (int | None | Unset):
        source (str | Unset):  Default: 'tmdb'.
        standardized_title (None | str | Unset):
        synopsis (str | Unset):  Default: ''.
        title_match (None | str | Unset):
        tmdb_id (int | None | Unset):
        vault_id (int | None | Unset):
        vault_label (None | str | Unset):
        where_to_watch (list[str] | Unset):
        year (int | None | Unset):
    """

    title: str
    backdrop_url: None | str | Unset = UNSET
    certificate: None | str | Unset = UNSET
    genres: list[str] | Unset = UNSET
    imdb_id: None | str | Unset = UNSET
    keywords: list[str] | Unset = UNSET
    match_confidence: float | None | Unset = UNSET
    overview: str | Unset = ""
    poster_url: None | str | Unset = UNSET
    release_date: None | str | Unset = UNSET
    runtime: int | None | Unset = UNSET
    source: str | Unset = "tmdb"
    standardized_title: None | str | Unset = UNSET
    synopsis: str | Unset = ""
    title_match: None | str | Unset = UNSET
    tmdb_id: int | None | Unset = UNSET
    vault_id: int | None | Unset = UNSET
    vault_label: None | str | Unset = UNSET
    where_to_watch: list[str] | Unset = UNSET
    year: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        title = self.title

        backdrop_url: None | str | Unset
        if isinstance(self.backdrop_url, Unset):
            backdrop_url = UNSET
        else:
            backdrop_url = self.backdrop_url

        certificate: None | str | Unset
        if isinstance(self.certificate, Unset):
            certificate = UNSET
        else:
            certificate = self.certificate

        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        imdb_id: None | str | Unset
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        keywords: list[str] | Unset = UNSET
        if not isinstance(self.keywords, Unset):
            keywords = self.keywords

        match_confidence: float | None | Unset
        if isinstance(self.match_confidence, Unset):
            match_confidence = UNSET
        else:
            match_confidence = self.match_confidence

        overview = self.overview

        poster_url: None | str | Unset
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        release_date: None | str | Unset
        if isinstance(self.release_date, Unset):
            release_date = UNSET
        else:
            release_date = self.release_date

        runtime: int | None | Unset
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        source = self.source

        standardized_title: None | str | Unset
        if isinstance(self.standardized_title, Unset):
            standardized_title = UNSET
        else:
            standardized_title = self.standardized_title

        synopsis = self.synopsis

        title_match: None | str | Unset
        if isinstance(self.title_match, Unset):
            title_match = UNSET
        else:
            title_match = self.title_match

        tmdb_id: int | None | Unset
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

        vault_id: int | None | Unset
        if isinstance(self.vault_id, Unset):
            vault_id = UNSET
        else:
            vault_id = self.vault_id

        vault_label: None | str | Unset
        if isinstance(self.vault_label, Unset):
            vault_label = UNSET
        else:
            vault_label = self.vault_label

        where_to_watch: list[str] | Unset = UNSET
        if not isinstance(self.where_to_watch, Unset):
            where_to_watch = self.where_to_watch

        year: int | None | Unset
        if isinstance(self.year, Unset):
            year = UNSET
        else:
            year = self.year

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "title": title,
            }
        )
        if backdrop_url is not UNSET:
            field_dict["backdrop_url"] = backdrop_url
        if certificate is not UNSET:
            field_dict["certificate"] = certificate
        if genres is not UNSET:
            field_dict["genres"] = genres
        if imdb_id is not UNSET:
            field_dict["imdb_id"] = imdb_id
        if keywords is not UNSET:
            field_dict["keywords"] = keywords
        if match_confidence is not UNSET:
            field_dict["match_confidence"] = match_confidence
        if overview is not UNSET:
            field_dict["overview"] = overview
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if release_date is not UNSET:
            field_dict["release_date"] = release_date
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if source is not UNSET:
            field_dict["source"] = source
        if standardized_title is not UNSET:
            field_dict["standardized_title"] = standardized_title
        if synopsis is not UNSET:
            field_dict["synopsis"] = synopsis
        if title_match is not UNSET:
            field_dict["title_match"] = title_match
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
        if vault_id is not UNSET:
            field_dict["vault_id"] = vault_id
        if vault_label is not UNSET:
            field_dict["vault_label"] = vault_label
        if where_to_watch is not UNSET:
            field_dict["where_to_watch"] = where_to_watch
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        title = d.pop("title")

        def _parse_backdrop_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        backdrop_url = _parse_backdrop_url(d.pop("backdrop_url", UNSET))

        def _parse_certificate(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        certificate = _parse_certificate(d.pop("certificate", UNSET))

        genres = cast(list[str], d.pop("genres", UNSET))

        def _parse_imdb_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        keywords = cast(list[str], d.pop("keywords", UNSET))

        def _parse_match_confidence(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        match_confidence = _parse_match_confidence(d.pop("match_confidence", UNSET))

        overview = d.pop("overview", UNSET)

        def _parse_poster_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        def _parse_release_date(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        release_date = _parse_release_date(d.pop("release_date", UNSET))

        def _parse_runtime(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        source = d.pop("source", UNSET)

        def _parse_standardized_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        standardized_title = _parse_standardized_title(d.pop("standardized_title", UNSET))

        synopsis = d.pop("synopsis", UNSET)

        def _parse_title_match(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title_match = _parse_title_match(d.pop("title_match", UNSET))

        def _parse_tmdb_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        def _parse_vault_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        vault_id = _parse_vault_id(d.pop("vault_id", UNSET))

        def _parse_vault_label(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        vault_label = _parse_vault_label(d.pop("vault_label", UNSET))

        where_to_watch = cast(list[str], d.pop("where_to_watch", UNSET))

        def _parse_year(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year = _parse_year(d.pop("year", UNSET))

        movie_lookup_candidate = cls(
            title=title,
            backdrop_url=backdrop_url,
            certificate=certificate,
            genres=genres,
            imdb_id=imdb_id,
            keywords=keywords,
            match_confidence=match_confidence,
            overview=overview,
            poster_url=poster_url,
            release_date=release_date,
            runtime=runtime,
            source=source,
            standardized_title=standardized_title,
            synopsis=synopsis,
            title_match=title_match,
            tmdb_id=tmdb_id,
            vault_id=vault_id,
            vault_label=vault_label,
            where_to_watch=where_to_watch,
            year=year,
        )

        movie_lookup_candidate.additional_properties = d
        return movie_lookup_candidate

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
