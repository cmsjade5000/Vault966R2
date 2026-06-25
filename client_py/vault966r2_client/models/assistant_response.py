from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.assistant_movie import AssistantMovie


T = TypeVar("T", bound="AssistantResponse")


@_attrs_define
class AssistantResponse:
    """
    Attributes:
        reply (str):
        movies (list[AssistantMovie] | Unset):
    """

    reply: str
    movies: list[AssistantMovie] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        reply = self.reply

        movies: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.movies, Unset):
            movies = []
            for movies_item_data in self.movies:
                movies_item = movies_item_data.to_dict()
                movies.append(movies_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "reply": reply,
            }
        )
        if movies is not UNSET:
            field_dict["movies"] = movies

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.assistant_movie import AssistantMovie

        d = dict(src_dict)
        reply = d.pop("reply")

        _movies = d.pop("movies", UNSET)
        movies: list[AssistantMovie] | Unset = UNSET
        if _movies is not UNSET:
            movies = []
            for movies_item_data in _movies:
                movies_item = AssistantMovie.from_dict(movies_item_data)

                movies.append(movies_item)

        assistant_response = cls(
            reply=reply,
            movies=movies,
        )

        assistant_response.additional_properties = d
        return assistant_response

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
