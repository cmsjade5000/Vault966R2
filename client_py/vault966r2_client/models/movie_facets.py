from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.movie_facets_genres import MovieFacetsGenres
    from ..models.movie_facets_moods import MovieFacetsMoods


T = TypeVar("T", bound="MovieFacets")


@_attrs_define
class MovieFacets:
    """
    Attributes:
        genres (Union[Unset, MovieFacetsGenres]):
        moods (Union[Unset, MovieFacetsMoods]):
    """

    genres: Union[Unset, "MovieFacetsGenres"] = UNSET
    moods: Union[Unset, "MovieFacetsMoods"] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        genres: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.genres, Unset):
            genres = self.genres.to_dict()

        moods: Union[Unset, dict[str, Any]] = UNSET
        if not isinstance(self.moods, Unset):
            moods = self.moods.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if genres is not UNSET:
            field_dict["genres"] = genres
        if moods is not UNSET:
            field_dict["moods"] = moods

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.movie_facets_genres import MovieFacetsGenres
        from ..models.movie_facets_moods import MovieFacetsMoods

        d = dict(src_dict)
        _genres = d.pop("genres", UNSET)
        genres: Union[Unset, MovieFacetsGenres]
        if isinstance(_genres, Unset):
            genres = UNSET
        else:
            genres = MovieFacetsGenres.from_dict(_genres)

        _moods = d.pop("moods", UNSET)
        moods: Union[Unset, MovieFacetsMoods]
        if isinstance(_moods, Unset):
            moods = UNSET
        else:
            moods = MovieFacetsMoods.from_dict(_moods)

        movie_facets = cls(
            genres=genres,
            moods=moods,
        )

        movie_facets.additional_properties = d
        return movie_facets

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
