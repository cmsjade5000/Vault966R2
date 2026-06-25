from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ManualMovieMetadata")


@_attrs_define
class ManualMovieMetadata:
    """
    Attributes:
        awards (None | str | Unset):
        backdrop_url (None | str | Unset):
        certificate (None | str | Unset):
        collection (None | str | Unset):
        countries (list[str] | Unset):
        genres (list[str] | Unset):
        imdb_id (None | str | Unset):
        imdb_rating (float | None | Unset):
        imdb_votes (int | None | Unset):
        keywords (list[str] | Unset):
        languages (list[str] | Unset):
        last_omdb_fetch_at (None | str | Unset):
        last_tmdb_fetch_at (None | str | Unset):
        metascore (int | None | Unset):
        omdb_payload_sha (None | str | Unset):
        overview (None | str | Unset):
        poster_url (None | str | Unset):
        release_date (None | str | Unset):
        rt_score (int | None | Unset):
        runtime (int | None | Unset):
        source (None | str | Unset):
        tmdb_id (int | None | Unset):
        tmdb_payload_sha (None | str | Unset):
        tomato_audience (int | None | Unset):
        tomato_meter (int | None | Unset):
        where_to_watch (list[str] | Unset):
    """

    awards: None | str | Unset = UNSET
    backdrop_url: None | str | Unset = UNSET
    certificate: None | str | Unset = UNSET
    collection: None | str | Unset = UNSET
    countries: list[str] | Unset = UNSET
    genres: list[str] | Unset = UNSET
    imdb_id: None | str | Unset = UNSET
    imdb_rating: float | None | Unset = UNSET
    imdb_votes: int | None | Unset = UNSET
    keywords: list[str] | Unset = UNSET
    languages: list[str] | Unset = UNSET
    last_omdb_fetch_at: None | str | Unset = UNSET
    last_tmdb_fetch_at: None | str | Unset = UNSET
    metascore: int | None | Unset = UNSET
    omdb_payload_sha: None | str | Unset = UNSET
    overview: None | str | Unset = UNSET
    poster_url: None | str | Unset = UNSET
    release_date: None | str | Unset = UNSET
    rt_score: int | None | Unset = UNSET
    runtime: int | None | Unset = UNSET
    source: None | str | Unset = UNSET
    tmdb_id: int | None | Unset = UNSET
    tmdb_payload_sha: None | str | Unset = UNSET
    tomato_audience: int | None | Unset = UNSET
    tomato_meter: int | None | Unset = UNSET
    where_to_watch: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        awards: None | str | Unset
        if isinstance(self.awards, Unset):
            awards = UNSET
        else:
            awards = self.awards

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

        collection: None | str | Unset
        if isinstance(self.collection, Unset):
            collection = UNSET
        else:
            collection = self.collection

        countries: list[str] | Unset = UNSET
        if not isinstance(self.countries, Unset):
            countries = self.countries

        genres: list[str] | Unset = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres

        imdb_id: None | str | Unset
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        imdb_rating: float | None | Unset
        if isinstance(self.imdb_rating, Unset):
            imdb_rating = UNSET
        else:
            imdb_rating = self.imdb_rating

        imdb_votes: int | None | Unset
        if isinstance(self.imdb_votes, Unset):
            imdb_votes = UNSET
        else:
            imdb_votes = self.imdb_votes

        keywords: list[str] | Unset = UNSET
        if not isinstance(self.keywords, Unset):
            keywords = self.keywords

        languages: list[str] | Unset = UNSET
        if not isinstance(self.languages, Unset):
            languages = self.languages

        last_omdb_fetch_at: None | str | Unset
        if isinstance(self.last_omdb_fetch_at, Unset):
            last_omdb_fetch_at = UNSET
        else:
            last_omdb_fetch_at = self.last_omdb_fetch_at

        last_tmdb_fetch_at: None | str | Unset
        if isinstance(self.last_tmdb_fetch_at, Unset):
            last_tmdb_fetch_at = UNSET
        else:
            last_tmdb_fetch_at = self.last_tmdb_fetch_at

        metascore: int | None | Unset
        if isinstance(self.metascore, Unset):
            metascore = UNSET
        else:
            metascore = self.metascore

        omdb_payload_sha: None | str | Unset
        if isinstance(self.omdb_payload_sha, Unset):
            omdb_payload_sha = UNSET
        else:
            omdb_payload_sha = self.omdb_payload_sha

        overview: None | str | Unset
        if isinstance(self.overview, Unset):
            overview = UNSET
        else:
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

        rt_score: int | None | Unset
        if isinstance(self.rt_score, Unset):
            rt_score = UNSET
        else:
            rt_score = self.rt_score

        runtime: int | None | Unset
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        source: None | str | Unset
        if isinstance(self.source, Unset):
            source = UNSET
        else:
            source = self.source

        tmdb_id: int | None | Unset
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

        tmdb_payload_sha: None | str | Unset
        if isinstance(self.tmdb_payload_sha, Unset):
            tmdb_payload_sha = UNSET
        else:
            tmdb_payload_sha = self.tmdb_payload_sha

        tomato_audience: int | None | Unset
        if isinstance(self.tomato_audience, Unset):
            tomato_audience = UNSET
        else:
            tomato_audience = self.tomato_audience

        tomato_meter: int | None | Unset
        if isinstance(self.tomato_meter, Unset):
            tomato_meter = UNSET
        else:
            tomato_meter = self.tomato_meter

        where_to_watch: list[str] | Unset = UNSET
        if not isinstance(self.where_to_watch, Unset):
            where_to_watch = self.where_to_watch

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if awards is not UNSET:
            field_dict["awards"] = awards
        if backdrop_url is not UNSET:
            field_dict["backdrop_url"] = backdrop_url
        if certificate is not UNSET:
            field_dict["certificate"] = certificate
        if collection is not UNSET:
            field_dict["collection"] = collection
        if countries is not UNSET:
            field_dict["countries"] = countries
        if genres is not UNSET:
            field_dict["genres"] = genres
        if imdb_id is not UNSET:
            field_dict["imdb_id"] = imdb_id
        if imdb_rating is not UNSET:
            field_dict["imdb_rating"] = imdb_rating
        if imdb_votes is not UNSET:
            field_dict["imdb_votes"] = imdb_votes
        if keywords is not UNSET:
            field_dict["keywords"] = keywords
        if languages is not UNSET:
            field_dict["languages"] = languages
        if last_omdb_fetch_at is not UNSET:
            field_dict["last_omdb_fetch_at"] = last_omdb_fetch_at
        if last_tmdb_fetch_at is not UNSET:
            field_dict["last_tmdb_fetch_at"] = last_tmdb_fetch_at
        if metascore is not UNSET:
            field_dict["metascore"] = metascore
        if omdb_payload_sha is not UNSET:
            field_dict["omdb_payload_sha"] = omdb_payload_sha
        if overview is not UNSET:
            field_dict["overview"] = overview
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if release_date is not UNSET:
            field_dict["release_date"] = release_date
        if rt_score is not UNSET:
            field_dict["rt_score"] = rt_score
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if source is not UNSET:
            field_dict["source"] = source
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
        if tmdb_payload_sha is not UNSET:
            field_dict["tmdb_payload_sha"] = tmdb_payload_sha
        if tomato_audience is not UNSET:
            field_dict["tomato_audience"] = tomato_audience
        if tomato_meter is not UNSET:
            field_dict["tomato_meter"] = tomato_meter
        if where_to_watch is not UNSET:
            field_dict["where_to_watch"] = where_to_watch

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_awards(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        awards = _parse_awards(d.pop("awards", UNSET))

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

        def _parse_collection(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        collection = _parse_collection(d.pop("collection", UNSET))

        countries = cast(list[str], d.pop("countries", UNSET))

        genres = cast(list[str], d.pop("genres", UNSET))

        def _parse_imdb_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        def _parse_imdb_rating(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        imdb_rating = _parse_imdb_rating(d.pop("imdb_rating", UNSET))

        def _parse_imdb_votes(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        imdb_votes = _parse_imdb_votes(d.pop("imdb_votes", UNSET))

        keywords = cast(list[str], d.pop("keywords", UNSET))

        languages = cast(list[str], d.pop("languages", UNSET))

        def _parse_last_omdb_fetch_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        last_omdb_fetch_at = _parse_last_omdb_fetch_at(d.pop("last_omdb_fetch_at", UNSET))

        def _parse_last_tmdb_fetch_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        last_tmdb_fetch_at = _parse_last_tmdb_fetch_at(d.pop("last_tmdb_fetch_at", UNSET))

        def _parse_metascore(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        metascore = _parse_metascore(d.pop("metascore", UNSET))

        def _parse_omdb_payload_sha(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        omdb_payload_sha = _parse_omdb_payload_sha(d.pop("omdb_payload_sha", UNSET))

        def _parse_overview(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        overview = _parse_overview(d.pop("overview", UNSET))

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

        def _parse_rt_score(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        rt_score = _parse_rt_score(d.pop("rt_score", UNSET))

        def _parse_runtime(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        def _parse_source(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        source = _parse_source(d.pop("source", UNSET))

        def _parse_tmdb_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        def _parse_tmdb_payload_sha(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tmdb_payload_sha = _parse_tmdb_payload_sha(d.pop("tmdb_payload_sha", UNSET))

        def _parse_tomato_audience(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        tomato_audience = _parse_tomato_audience(d.pop("tomato_audience", UNSET))

        def _parse_tomato_meter(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        tomato_meter = _parse_tomato_meter(d.pop("tomato_meter", UNSET))

        where_to_watch = cast(list[str], d.pop("where_to_watch", UNSET))

        manual_movie_metadata = cls(
            awards=awards,
            backdrop_url=backdrop_url,
            certificate=certificate,
            collection=collection,
            countries=countries,
            genres=genres,
            imdb_id=imdb_id,
            imdb_rating=imdb_rating,
            imdb_votes=imdb_votes,
            keywords=keywords,
            languages=languages,
            last_omdb_fetch_at=last_omdb_fetch_at,
            last_tmdb_fetch_at=last_tmdb_fetch_at,
            metascore=metascore,
            omdb_payload_sha=omdb_payload_sha,
            overview=overview,
            poster_url=poster_url,
            release_date=release_date,
            rt_score=rt_score,
            runtime=runtime,
            source=source,
            tmdb_id=tmdb_id,
            tmdb_payload_sha=tmdb_payload_sha,
            tomato_audience=tomato_audience,
            tomato_meter=tomato_meter,
            where_to_watch=where_to_watch,
        )

        manual_movie_metadata.additional_properties = d
        return manual_movie_metadata

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
