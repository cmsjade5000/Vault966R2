from collections.abc import Mapping
from typing import Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MovieCreate")


@_attrs_define
class MovieCreate:
    """
    Attributes:
        title (str):
        awards (Union[None, Unset, str]):
        backdrop_url (Union[None, Unset, str]):
        collection (Union[None, Unset, str]):
        countries (Union[None, Unset, list[str], str]):
        genres (Union[Unset, list[str]]):
        imdb_id (Union[None, Unset, str]):
        imdb_rating (Union[None, Unset, float]):
        imdb_votes (Union[None, Unset, int]):
        languages (Union[None, Unset, list[str], str]):
        metascore (Union[None, Unset, int]):
        moods (Union[Unset, list[str]]):
        plot (Union[None, Unset, str]):
        poster_url (Union[None, Unset, str]):
        runtime (Union[None, Unset, int]):
        tmdb_id (Union[None, Unset, int]):
        tomato_audience (Union[None, Unset, int]):
        tomato_meter (Union[None, Unset, int]):
        where_to_watch (Union[None, Unset, list[str], str]):
        year (Union[None, Unset, int]):
    """

    title: str
    awards: Union[None, Unset, str] = UNSET
    backdrop_url: Union[None, Unset, str] = UNSET
    collection: Union[None, Unset, str] = UNSET
    countries: Union[None, Unset, list[str], str] = UNSET
    genres: Union[Unset, list[str]] = UNSET
    imdb_id: Union[None, Unset, str] = UNSET
    imdb_rating: Union[None, Unset, float] = UNSET
    imdb_votes: Union[None, Unset, int] = UNSET
    languages: Union[None, Unset, list[str], str] = UNSET
    metascore: Union[None, Unset, int] = UNSET
    moods: Union[Unset, list[str]] = UNSET
    plot: Union[None, Unset, str] = UNSET
    poster_url: Union[None, Unset, str] = UNSET
    runtime: Union[None, Unset, int] = UNSET
    tmdb_id: Union[None, Unset, int] = UNSET
    tomato_audience: Union[None, Unset, int] = UNSET
    tomato_meter: Union[None, Unset, int] = UNSET
    where_to_watch: Union[None, Unset, list[str], str] = UNSET
    year: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        title = self.title

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

        genres: Union[Unset, list[str]] = UNSET
        if not isinstance(self.genres, Unset):
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

        metascore: Union[None, Unset, int]
        if isinstance(self.metascore, Unset):
            metascore = UNSET
        else:
            metascore = self.metascore

        moods: Union[Unset, list[str]] = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

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

        runtime: Union[None, Unset, int]
        if isinstance(self.runtime, Unset):
            runtime = UNSET
        else:
            runtime = self.runtime

        tmdb_id: Union[None, Unset, int]
        if isinstance(self.tmdb_id, Unset):
            tmdb_id = UNSET
        else:
            tmdb_id = self.tmdb_id

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

        where_to_watch: Union[None, Unset, list[str], str]
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
        field_dict.update(
            {
                "title": title,
            }
        )
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
        if metascore is not UNSET:
            field_dict["metascore"] = metascore
        if moods is not UNSET:
            field_dict["moods"] = moods
        if plot is not UNSET:
            field_dict["plot"] = plot
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if tmdb_id is not UNSET:
            field_dict["tmdb_id"] = tmdb_id
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
        title = d.pop("title")

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

        genres = cast(list[str], d.pop("genres", UNSET))

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

        def _parse_metascore(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        metascore = _parse_metascore(d.pop("metascore", UNSET))

        moods = cast(list[str], d.pop("moods", UNSET))

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

        def _parse_runtime(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        runtime = _parse_runtime(d.pop("runtime", UNSET))

        def _parse_tmdb_id(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        tmdb_id = _parse_tmdb_id(d.pop("tmdb_id", UNSET))

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

        def _parse_where_to_watch(data: object) -> Union[None, Unset, list[str], str]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                where_to_watch_type_1 = cast(list[str], data)

                return where_to_watch_type_1
            except:  # noqa: E722
                pass
            return cast(Union[None, Unset, list[str], str], data)

        where_to_watch = _parse_where_to_watch(d.pop("where_to_watch", UNSET))

        def _parse_year(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year = _parse_year(d.pop("year", UNSET))

        movie_create = cls(
            title=title,
            awards=awards,
            backdrop_url=backdrop_url,
            collection=collection,
            countries=countries,
            genres=genres,
            imdb_id=imdb_id,
            imdb_rating=imdb_rating,
            imdb_votes=imdb_votes,
            languages=languages,
            metascore=metascore,
            moods=moods,
            plot=plot,
            poster_url=poster_url,
            runtime=runtime,
            tmdb_id=tmdb_id,
            tomato_audience=tomato_audience,
            tomato_meter=tomato_meter,
            where_to_watch=where_to_watch,
            year=year,
        )

        movie_create.additional_properties = d
        return movie_create

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
