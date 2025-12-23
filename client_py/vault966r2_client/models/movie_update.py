import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieUpdate")


@_attrs_define
class MovieUpdate:
    """
    Attributes:
        awards (Union[None, Unset, str]):
        backdrop_url (Union[None, Unset, str]):
        collection (Union[None, Unset, str]):
        countries (Union[None, Unset, list[str], str]):
        genres (Union[None, Unset, list[str]]):
        imdb_id (Union[None, Unset, str]):
        imdb_rating (Union[None, Unset, float]):
        imdb_votes (Union[None, Unset, int]):
        languages (Union[None, Unset, list[str], str]):
        last_omdb_fetch_at (Union[None, Unset, datetime.datetime]):
        last_tmdb_fetch_at (Union[None, Unset, datetime.datetime]):
        metascore (Union[None, Unset, int]):
        omdb_payload_sha (Union[None, Unset, str]):
        plot (Union[None, Unset, str]):
        poster_url (Union[None, Unset, str]):
        resolve_flag (Union[Unset, bool]):  Default: False.
        rt_score (Union[None, Unset, int]):
        runtime (Union[None, Unset, int]):
        title (Union[None, Unset, str]):
        tmdb_etag (Union[None, Unset, str]):
        tmdb_id (Union[None, Unset, int]):
        tmdb_payload_sha (Union[None, Unset, str]):
        tomato_audience (Union[None, Unset, int]):
        tomato_meter (Union[None, Unset, int]):
        where_to_watch (Union[None, Unset, list[str]]):
        year (Union[None, Unset, int]):
    """

    awards: Union[None, Unset, str] = UNSET
    backdrop_url: Union[None, Unset, str] = UNSET
    collection: Union[None, Unset, str] = UNSET
    countries: Union[None, Unset, list[str], str] = UNSET
    genres: Union[None, Unset, list[str]] = UNSET
    imdb_id: Union[None, Unset, str] = UNSET
    imdb_rating: Union[None, Unset, float] = UNSET
    imdb_votes: Union[None, Unset, int] = UNSET
    languages: Union[None, Unset, list[str], str] = UNSET
    last_omdb_fetch_at: Union[None, Unset, datetime.datetime] = UNSET
    last_tmdb_fetch_at: Union[None, Unset, datetime.datetime] = UNSET
    metascore: Union[None, Unset, int] = UNSET
    omdb_payload_sha: Union[None, Unset, str] = UNSET
    plot: Union[None, Unset, str] = UNSET
    poster_url: Union[None, Unset, str] = UNSET
    resolve_flag: Union[Unset, bool] = False
    rt_score: Union[None, Unset, int] = UNSET
    runtime: Union[None, Unset, int] = UNSET
    title: Union[None, Unset, str] = UNSET
    tmdb_etag: Union[None, Unset, str] = UNSET
    tmdb_id: Union[None, Unset, int] = UNSET
    tmdb_payload_sha: Union[None, Unset, str] = UNSET
    tomato_audience: Union[None, Unset, int] = UNSET
    tomato_meter: Union[None, Unset, int] = UNSET
    where_to_watch: Union[None, Unset, list[str]] = UNSET
    year: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        awards: Union[None, Unset, str]
        if isinstance(self.awards, Unset):
            awards = UNSET
        else:
            awards = self.awards

        backdrop_url: Union[None, Unset, str]
        if isinstance(self.backdrop_url, Unset):
            backdrop_url = UNSET
        else:
            backdrop_url = self.backdrop_url

        collection: Union[None, Unset, str]
        if isinstance(self.collection, Unset):
            collection = UNSET
        else:
            collection = self.collection

        countries: Union[None, Unset, list[str], str]
        if isinstance(self.countries, Unset):
            countries = UNSET
        elif isinstance(self.countries, list):
            countries = self.countries

        else:
            countries = self.countries

        genres: Union[None, Unset, list[str]]
        if isinstance(self.genres, Unset):
            genres = UNSET
        elif isinstance(self.genres, list):
            genres = self.genres

        else:
            genres = self.genres

        imdb_id: Union[None, Unset, str]
        if isinstance(self.imdb_id, Unset):
            imdb_id = UNSET
        else:
            imdb_id = self.imdb_id

        imdb_rating: Union[None, Unset, float]
        if isinstance(self.imdb_rating, Unset):
            imdb_rating = UNSET
        else:
            imdb_rating = self.imdb_rating

        imdb_votes: Union[None, Unset, int]
        if isinstance(self.imdb_votes, Unset):
            imdb_votes = UNSET
        else:
            imdb_votes = self.imdb_votes

        languages: Union[None, Unset, list[str], str]
        if isinstance(self.languages, Unset):
            languages = UNSET
        elif isinstance(self.languages, list):
            languages = self.languages

        else:
            languages = self.languages

        last_omdb_fetch_at: Union[None, Unset, str]
        if isinstance(self.last_omdb_fetch_at, Unset):
            last_omdb_fetch_at = UNSET
        elif isinstance(self.last_omdb_fetch_at, datetime.datetime):
            last_omdb_fetch_at = self.last_omdb_fetch_at.isoformat()
        else:
            last_omdb_fetch_at = self.last_omdb_fetch_at

        last_tmdb_fetch_at: Union[None, Unset, str]
        if isinstance(self.last_tmdb_fetch_at, Unset):
            last_tmdb_fetch_at = UNSET
        elif isinstance(self.last_tmdb_fetch_at, datetime.datetime):
            last_tmdb_fetch_at = self.last_tmdb_fetch_at.isoformat()
        else:
            last_tmdb_fetch_at = self.last_tmdb_fetch_at

        metascore: Union[None, Unset, int]
        if isinstance(self.metascore, Unset):
            metascore = UNSET
        else:
            metascore = self.metascore

        omdb_payload_sha: Union[None, Unset, str]
        if isinstance(self.omdb_payload_sha, Unset):
            omdb_payload_sha = UNSET
        else:
            omdb_payload_sha = self.omdb_payload_sha

        plot: Union[None, Unset, str]
        if isinstance(self.plot, Unset):
            plot = UNSET
        else:
            plot = self.plot

        poster_url: Union[None, Unset, str]
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        resolve_flag = self.resolve_flag

        rt_score: Union[None, Unset, int]
        if isinstance(self.rt_score, Unset):
            rt_score = UNSET
        else:
            rt_score = self.rt_score

        runtime: Union[None, Unset, int]
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        title: Union[None, Unset, str]
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        tmdb_etag: Union[None, Unset, str]
        if isinstance(self.tmdb_etag, Unset):
            tmdb_etag = UNSET
        else:
            tmdb_etag = self.tmdb_etag

        tmdb_id: Union[None, Unset, int]
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

        tmdb_payload_sha: Union[None, Unset, str]
        if isinstance(self.tmdb_payload_sha, Unset):
            tmdb_payload_sha = UNSET
        else:
            tmdb_payload_sha = self.tmdb_payload_sha

        tomato_audience: Union[None, Unset, int]
        if isinstance(self.tomato_audience, Unset):
            tomato_audience = UNSET
        else:
            tomato_audience = self.tomato_audience

        tomato_meter: Union[None, Unset, int]
        if isinstance(self.tomato_meter, Unset):
            tomato_meter = UNSET
        else:
            tomato_meter = self.tomato_meter

        where_to_watch: Union[None, Unset, list[str]]
        if isinstance(self.where_to_watch, Unset):
            where_to_watch = UNSET
        elif isinstance(self.where_to_watch, list):
            where_to_watch = self.where_to_watch

        else:
            where_to_watch = self.where_to_watch

        year: Union[None, Unset, int]
        if isinstance(self.year, Unset):
            year = UNSET
        else:
            year = self.year

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if awards is not UNSET:
            field_dict["awards"] = awards
        if backdrop_url is not UNSET:
            field_dict["backdrop_url"] = backdrop_url
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
        if plot is not UNSET:
            field_dict["plot"] = plot
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if resolve_flag is not UNSET:
            field_dict["resolve_flag"] = resolve_flag
        if rt_score is not UNSET:
            field_dict["rt_score"] = rt_score
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if title is not UNSET:
            field_dict["title"] = title
        if tmdb_etag is not UNSET:
            field_dict["tmdb_etag"] = tmdb_etag
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
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_awards(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        awards = _parse_awards(d.pop("awards", UNSET))

        def _parse_backdrop_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        backdrop_url = _parse_backdrop_url(d.pop("backdrop_url", UNSET))

        def _parse_collection(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        collection = _parse_collection(d.pop("collection", UNSET))

        def _parse_countries(data: object) -> Union[None, Unset, list[str], str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                countries_type_1 = cast(list[str], data)

                return countries_type_1
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str], str], data)

        countries = _parse_countries(d.pop("countries", UNSET))

        def _parse_genres(data: object) -> Union[None, Unset, list[str]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                genres_type_0 = cast(list[str], data)

                return genres_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str]], data)

        genres = _parse_genres(d.pop("genres", UNSET))

        def _parse_imdb_id(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        imdb_id = _parse_imdb_id(d.pop("imdb_id", UNSET))

        def _parse_imdb_rating(data: object) -> Union[None, Unset, float]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, float], data)

        imdb_rating = _parse_imdb_rating(d.pop("imdb_rating", UNSET))

        def _parse_imdb_votes(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        imdb_votes = _parse_imdb_votes(d.pop("imdb_votes", UNSET))

        def _parse_languages(data: object) -> Union[None, Unset, list[str], str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                languages_type_1 = cast(list[str], data)

                return languages_type_1
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str], str], data)

        languages = _parse_languages(d.pop("languages", UNSET))

        def _parse_last_omdb_fetch_at(data: object) -> Union[None, Unset, datetime.datetime]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_omdb_fetch_at_type_0 = isoparse(data)

                return last_omdb_fetch_at_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, datetime.datetime], data)

        last_omdb_fetch_at = _parse_last_omdb_fetch_at(d.pop("last_omdb_fetch_at", UNSET))

        def _parse_last_tmdb_fetch_at(data: object) -> Union[None, Unset, datetime.datetime]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_tmdb_fetch_at_type_0 = isoparse(data)

                return last_tmdb_fetch_at_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, datetime.datetime], data)

        last_tmdb_fetch_at = _parse_last_tmdb_fetch_at(d.pop("last_tmdb_fetch_at", UNSET))

        def _parse_metascore(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        metascore = _parse_metascore(d.pop("metascore", UNSET))

        def _parse_omdb_payload_sha(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        omdb_payload_sha = _parse_omdb_payload_sha(d.pop("omdb_payload_sha", UNSET))

        def _parse_plot(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        plot = _parse_plot(d.pop("plot", UNSET))

        def _parse_poster_url(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        resolve_flag = d.pop("resolve_flag", UNSET)

        def _parse_rt_score(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        rt_score = _parse_rt_score(d.pop("rt_score", UNSET))

        def _parse_runtime(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        def _parse_title(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        title = _parse_title(d.pop("title", UNSET))

        def _parse_tmdb_etag(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        tmdb_etag = _parse_tmdb_etag(d.pop("tmdb_etag", UNSET))

        def _parse_tmdb_id(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

        def _parse_tmdb_payload_sha(data: object) -> Union[None, Unset, str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, str], data)

        tmdb_payload_sha = _parse_tmdb_payload_sha(d.pop("tmdb_payload_sha", UNSET))

        def _parse_tomato_audience(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        tomato_audience = _parse_tomato_audience(d.pop("tomato_audience", UNSET))

        def _parse_tomato_meter(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        tomato_meter = _parse_tomato_meter(d.pop("tomato_meter", UNSET))

        def _parse_where_to_watch(data: object) -> Union[None, Unset, list[str]]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                where_to_watch_type_0 = cast(list[str], data)

                return where_to_watch_type_0
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str]], data)

        where_to_watch = _parse_where_to_watch(d.pop("where_to_watch", UNSET))

        def _parse_year(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year = _parse_year(d.pop("year", UNSET))

        movie_update = cls(
            awards=awards,
            backdrop_url=backdrop_url,
            collection=collection,
            countries=countries,
            genres=genres,
            imdb_id=imdb_id,
            imdb_rating=imdb_rating,
            imdb_votes=imdb_votes,
            languages=languages,
            last_omdb_fetch_at=last_omdb_fetch_at,
            last_tmdb_fetch_at=last_tmdb_fetch_at,
            metascore=metascore,
            omdb_payload_sha=omdb_payload_sha,
            plot=plot,
            poster_url=poster_url,
            resolve_flag=resolve_flag,
            rt_score=rt_score,
            runtime=runtime,
            title=title,
            tmdb_etag=tmdb_etag,
            tmdb_id=tmdb_id,
            tmdb_payload_sha=tmdb_payload_sha,
            tomato_audience=tomato_audience,
            tomato_meter=tomato_meter,
            where_to_watch=where_to_watch,
            year=year,
        )

        movie_update.additional_properties = d
        return movie_update

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
