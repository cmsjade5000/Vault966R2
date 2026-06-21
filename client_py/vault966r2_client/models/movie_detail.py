from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.role_with_person_read import RoleWithPersonRead
    from ..models.similar_movie import SimilarMovie
    from ..models.top_billed_entry import TopBilledEntry


T = TypeVar("T", bound="MovieDetail")


@_attrs_define
class MovieDetail:
    """
    Attributes:
        id (int):
        title (str):
        awards (None | str | Unset):
        backdrop_url (None | str | Unset):
        certificate (None | str | Unset):
        collection (None | str | Unset):
        countries (list[str] | None | str | Unset):
        countries_display (list[str] | Unset):
        countries_iso (list[str] | Unset):
        flag_notes (None | str | Unset):
        flag_reason (None | str | Unset):
        flagged (bool | Unset):  Default: False.
        genres (list[str] | Unset):
        imdb_id (None | str | Unset):
        imdb_rating (float | None | Unset):
        imdb_votes (int | None | Unset):
        keywords (list[str] | Unset):
        languages (list[str] | None | str | Unset):
        languages_display (list[str] | Unset):
        languages_iso (list[str] | Unset):
        last_omdb_fetch_at (datetime.datetime | None | Unset):
        last_tmdb_fetch_at (datetime.datetime | None | Unset):
        metascore (int | None | Unset):
        moods (list[str] | Unset):
        omdb_payload_sha (None | str | Unset):
        plot (None | str | Unset):
        poster_theme (None | str | Unset):
        poster_url (None | str | Unset):
        roles (list[RoleWithPersonRead] | Unset):
        rt_score (int | None | Unset):
        runtime (int | None | Unset):
        similar (list[SimilarMovie] | Unset):
        tmdb_etag (None | str | Unset):
        tmdb_id (int | None | Unset):
        tmdb_payload_sha (None | str | Unset):
        tomato_audience (int | None | Unset):
        tomato_meter (int | None | Unset):
        top_billed (list[TopBilledEntry] | Unset):
        vault_id (None | str | Unset):
        where_to_watch (list[str] | Unset):
        year (int | None | Unset):
    """

    id: int
    title: str
    awards: None | str | Unset = UNSET
    backdrop_url: None | str | Unset = UNSET
    certificate: None | str | Unset = UNSET
    collection: None | str | Unset = UNSET
    countries: list[str] | None | str | Unset = UNSET
    countries_display: list[str] | Unset = UNSET
    countries_iso: list[str] | Unset = UNSET
    flag_notes: None | str | Unset = UNSET
    flag_reason: None | str | Unset = UNSET
    flagged: bool | Unset = False
    genres: list[str] | Unset = UNSET
    imdb_id: None | str | Unset = UNSET
    imdb_rating: float | None | Unset = UNSET
    imdb_votes: int | None | Unset = UNSET
    keywords: list[str] | Unset = UNSET
    languages: list[str] | None | str | Unset = UNSET
    languages_display: list[str] | Unset = UNSET
    languages_iso: list[str] | Unset = UNSET
    last_omdb_fetch_at: datetime.datetime | None | Unset = UNSET
    last_tmdb_fetch_at: datetime.datetime | None | Unset = UNSET
    metascore: int | None | Unset = UNSET
    moods: list[str] | Unset = UNSET
    omdb_payload_sha: None | str | Unset = UNSET
    plot: None | str | Unset = UNSET
    poster_theme: None | str | Unset = UNSET
    poster_url: None | str | Unset = UNSET
    roles: list[RoleWithPersonRead] | Unset = UNSET
    rt_score: int | None | Unset = UNSET
    runtime: int | None | Unset = UNSET
    similar: list[SimilarMovie] | Unset = UNSET
    tmdb_etag: None | str | Unset = UNSET
    tmdb_id: int | None | Unset = UNSET
    tmdb_payload_sha: None | str | Unset = UNSET
    tomato_audience: int | None | Unset = UNSET
    tomato_meter: int | None | Unset = UNSET
    top_billed: list[TopBilledEntry] | Unset = UNSET
    vault_id: None | str | Unset = UNSET
    where_to_watch: list[str] | Unset = UNSET
    year: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        title = self.title

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

        countries: list[str] | None | str | Unset
        if isinstance(self.countries, Unset):
            countries = UNSET
        elif isinstance(self.countries, list):
            countries = self.countries

        else:
            countries = self.countries

        countries_display: list[str] | Unset = UNSET
        if not isinstance(self.countries_display, Unset):
            countries_display = self.countries_display

        countries_iso: list[str] | Unset = UNSET
        if not isinstance(self.countries_iso, Unset):
            countries_iso = self.countries_iso

        flag_notes: None | str | Unset
        if isinstance(self.flag_notes, Unset):
            flag_notes = UNSET
        else:
            flag_notes = self.flag_notes

        flag_reason: None | str | Unset
        if isinstance(self.flag_reason, Unset):
            flag_reason = UNSET
        else:
            flag_reason = self.flag_reason

        flagged = self.flagged

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

        languages: list[str] | None | str | Unset
        if isinstance(self.languages, Unset):
            languages = UNSET
        elif isinstance(self.languages, list):
            languages = self.languages

        else:
            languages = self.languages

        languages_display: list[str] | Unset = UNSET
        if not isinstance(self.languages_display, Unset):
            languages_display = self.languages_display

        languages_iso: list[str] | Unset = UNSET
        if not isinstance(self.languages_iso, Unset):
            languages_iso = self.languages_iso

        last_omdb_fetch_at: None | str | Unset
        if isinstance(self.last_omdb_fetch_at, Unset):
            last_omdb_fetch_at = UNSET
        elif isinstance(self.last_omdb_fetch_at, datetime.datetime):
            last_omdb_fetch_at = self.last_omdb_fetch_at.isoformat()
        else:
            last_omdb_fetch_at = self.last_omdb_fetch_at

        last_tmdb_fetch_at: None | str | Unset
        if isinstance(self.last_tmdb_fetch_at, Unset):
            last_tmdb_fetch_at = UNSET
        elif isinstance(self.last_tmdb_fetch_at, datetime.datetime):
            last_tmdb_fetch_at = self.last_tmdb_fetch_at.isoformat()
        else:
            last_tmdb_fetch_at = self.last_tmdb_fetch_at

        metascore: int | None | Unset
        if isinstance(self.metascore, Unset):
            metascore = UNSET
        else:
            metascore = self.metascore

        moods: list[str] | Unset = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods

        omdb_payload_sha: None | str | Unset
        if isinstance(self.omdb_payload_sha, Unset):
            omdb_payload_sha = UNSET
        else:
            omdb_payload_sha = self.omdb_payload_sha

        plot: None | str | Unset
        if isinstance(self.plot, Unset):
            plot = UNSET
        else:
            plot = self.plot

        poster_theme: None | str | Unset
        if isinstance(self.poster_theme, Unset):
            poster_theme = UNSET
        else:
            poster_theme = self.poster_theme

        poster_url: None | str | Unset
        if isinstance(self.poster_url, Unset):
            poster_url = UNSET
        else:
            poster_url = self.poster_url

        roles: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.roles, Unset):
            roles = []
            for roles_item_data in self.roles:
                roles_item = roles_item_data.to_dict()
                roles.append(roles_item)

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

        similar: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.similar, Unset):
            similar = []
            for similar_item_data in self.similar:
                similar_item = similar_item_data.to_dict()
                similar.append(similar_item)

        tmdb_etag: None | str | Unset
        if isinstance(self.tmdb_etag, Unset):
            tmdb_etag = UNSET
        else:
            tmdb_etag = self.tmdb_etag

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

        top_billed: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.top_billed, Unset):
            top_billed = []
            for top_billed_item_data in self.top_billed:
                top_billed_item = top_billed_item_data.to_dict()
                top_billed.append(top_billed_item)

        vault_id: None | str | Unset
        if isinstance(self.vault_id, Unset):
            vault_id = UNSET
        else:
            vault_id = self.vault_id

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
                "id": id,
                "title": title,
            }
        )
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
        if countries_display is not UNSET:
            field_dict["countries_display"] = countries_display
        if countries_iso is not UNSET:
            field_dict["countries_iso"] = countries_iso
        if flag_notes is not UNSET:
            field_dict["flag_notes"] = flag_notes
        if flag_reason is not UNSET:
            field_dict["flag_reason"] = flag_reason
        if flagged is not UNSET:
            field_dict["flagged"] = flagged
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
        if languages_display is not UNSET:
            field_dict["languages_display"] = languages_display
        if languages_iso is not UNSET:
            field_dict["languages_iso"] = languages_iso
        if last_omdb_fetch_at is not UNSET:
            field_dict["last_omdb_fetch_at"] = last_omdb_fetch_at
        if last_tmdb_fetch_at is not UNSET:
            field_dict["last_tmdb_fetch_at"] = last_tmdb_fetch_at
        if metascore is not UNSET:
            field_dict["metascore"] = metascore
        if moods is not UNSET:
            field_dict["moods"] = moods
        if omdb_payload_sha is not UNSET:
            field_dict["omdb_payload_sha"] = omdb_payload_sha
        if plot is not UNSET:
            field_dict["plot"] = plot
        if poster_theme is not UNSET:
            field_dict["poster_theme"] = poster_theme
        if poster_url is not UNSET:
            field_dict["poster_url"] = poster_url
        if roles is not UNSET:
            field_dict["roles"] = roles
        if rt_score is not UNSET:
            field_dict["rt_score"] = rt_score
        if runtime is not UNSET:
            field_dict["runtime"] = runtime
        if similar is not UNSET:
            field_dict["similar"] = similar
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
        if top_billed is not UNSET:
            field_dict["top_billed"] = top_billed
        if vault_id is not UNSET:
            field_dict["vault_id"] = vault_id
        if where_to_watch is not UNSET:
            field_dict["where_to_watch"] = where_to_watch
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.role_with_person_read import RoleWithPersonRead
        from ..models.similar_movie import SimilarMovie
        from ..models.top_billed_entry import TopBilledEntry

        d = dict(src_dict)
        id = d.pop("id")

        title = d.pop("title")

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

        def _parse_countries(data: object) -> list[str] | None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                countries_type_1 = cast(list[str], data)

                return countries_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | str | Unset, data)

        countries = _parse_countries(d.pop("countries", UNSET))

        countries_display = cast(list[str], d.pop("countries_display", UNSET))

        countries_iso = cast(list[str], d.pop("countries_iso", UNSET))

        def _parse_flag_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        flag_notes = _parse_flag_notes(d.pop("flag_notes", UNSET))

        def _parse_flag_reason(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        flag_reason = _parse_flag_reason(d.pop("flag_reason", UNSET))

        flagged = d.pop("flagged", UNSET)

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

        def _parse_languages(data: object) -> list[str] | None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                languages_type_1 = cast(list[str], data)

                return languages_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | str | Unset, data)

        languages = _parse_languages(d.pop("languages", UNSET))

        languages_display = cast(list[str], d.pop("languages_display", UNSET))

        languages_iso = cast(list[str], d.pop("languages_iso", UNSET))

        def _parse_last_omdb_fetch_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_omdb_fetch_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_omdb_fetch_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        last_omdb_fetch_at = _parse_last_omdb_fetch_at(d.pop("last_omdb_fetch_at", UNSET))

        def _parse_last_tmdb_fetch_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                last_tmdb_fetch_at_type_0 = datetime.datetime.fromisoformat(data)

                return last_tmdb_fetch_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        last_tmdb_fetch_at = _parse_last_tmdb_fetch_at(d.pop("last_tmdb_fetch_at", UNSET))

        def _parse_metascore(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        metascore = _parse_metascore(d.pop("metascore", UNSET))

        moods = cast(list[str], d.pop("moods", UNSET))

        def _parse_omdb_payload_sha(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        omdb_payload_sha = _parse_omdb_payload_sha(d.pop("omdb_payload_sha", UNSET))

        def _parse_plot(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        plot = _parse_plot(d.pop("plot", UNSET))

        def _parse_poster_theme(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        poster_theme = _parse_poster_theme(d.pop("poster_theme", UNSET))

        def _parse_poster_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        poster_url = _parse_poster_url(d.pop("poster_url", UNSET))

        _roles = d.pop("roles", UNSET)
        roles: list[RoleWithPersonRead] | Unset = UNSET
        if _roles is not UNSET:
            roles = []
            for roles_item_data in _roles:
                roles_item = RoleWithPersonRead.from_dict(roles_item_data)

                roles.append(roles_item)

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

        _similar = d.pop("similar", UNSET)
        similar: list[SimilarMovie] | Unset = UNSET
        if _similar is not UNSET:
            similar = []
            for similar_item_data in _similar:
                similar_item = SimilarMovie.from_dict(similar_item_data)

                similar.append(similar_item)

        def _parse_tmdb_etag(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tmdb_etag = _parse_tmdb_etag(d.pop("tmdb_etag", UNSET))

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

        _top_billed = d.pop("top_billed", UNSET)
        top_billed: list[TopBilledEntry] | Unset = UNSET
        if _top_billed is not UNSET:
            top_billed = []
            for top_billed_item_data in _top_billed:
                top_billed_item = TopBilledEntry.from_dict(top_billed_item_data)

                top_billed.append(top_billed_item)

        def _parse_vault_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        vault_id = _parse_vault_id(d.pop("vault_id", UNSET))

        where_to_watch = cast(list[str], d.pop("where_to_watch", UNSET))

        def _parse_year(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        year = _parse_year(d.pop("year", UNSET))

        movie_detail = cls(
            id=id,
            title=title,
            awards=awards,
            backdrop_url=backdrop_url,
            certificate=certificate,
            collection=collection,
            countries=countries,
            countries_display=countries_display,
            countries_iso=countries_iso,
            flag_notes=flag_notes,
            flag_reason=flag_reason,
            flagged=flagged,
            genres=genres,
            imdb_id=imdb_id,
            imdb_rating=imdb_rating,
            imdb_votes=imdb_votes,
            keywords=keywords,
            languages=languages,
            languages_display=languages_display,
            languages_iso=languages_iso,
            last_omdb_fetch_at=last_omdb_fetch_at,
            last_tmdb_fetch_at=last_tmdb_fetch_at,
            metascore=metascore,
            moods=moods,
            omdb_payload_sha=omdb_payload_sha,
            plot=plot,
            poster_theme=poster_theme,
            poster_url=poster_url,
            roles=roles,
            rt_score=rt_score,
            runtime=runtime,
            similar=similar,
            tmdb_etag=tmdb_etag,
            tmdb_id=tmdb_id,
            tmdb_payload_sha=tmdb_payload_sha,
            tomato_audience=tomato_audience,
            tomato_meter=tomato_meter,
            top_billed=top_billed,
            vault_id=vault_id,
            where_to_watch=where_to_watch,
            year=year,
        )

        movie_detail.additional_properties = d
        return movie_detail

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
