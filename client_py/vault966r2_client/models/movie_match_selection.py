from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.movie_match_selection_source import MovieMatchSelectionSource
from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieMatchSelection")


@_attrs_define
class MovieMatchSelection:
    """
    Attributes:
        source (MovieMatchSelectionSource):
        title (str):
        imdb_id (None | str | Unset):
        tmdb_id (int | None | Unset):
        year (int | None | Unset):
    """

    source: MovieMatchSelectionSource
    title: str
    imdb_id: None | str | Unset = UNSET
    tmdb_id: int | None | Unset = UNSET
    year: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        source = self.source.value

        title = self.title

        imdb_id: None | str | Unset
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        tmdb_id: int | None | Unset
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

        year: int | None | Unset
        if isinstance(self.year, Unset):
            year = UNSET
        else:
            year = self.year

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "source": source,
                "title": title,
            }
        )
        if imdb_id is not UNSET:
            field_dict["imdb_id"] = imdb_id
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        source = MovieMatchSelectionSource(d.pop("source"))

        title = d.pop("title")

        def _parse_imdb_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        def _parse_tmdb_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        def _parse_year(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year = _parse_year(d.pop("year", UNSET))

        movie_match_selection = cls(
            source=source,
            title=title,
            imdb_id=imdb_id,
            tmdb_id=tmdb_id,
            year=year,
        )

        return movie_match_selection
