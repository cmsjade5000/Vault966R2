from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar(
    "T", bound="FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost"
)


@_attrs_define
class FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost:
    """ """

    additional_properties: dict[str, bool | int] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        field_dict: dict[str, Any] = {}
        for prop_name, prop in self.additional_properties.items():
            field_dict[prop_name] = prop

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        flag_movie_for_review_ui_movies_movie_id_review_flag_post_response_flag_movie_for_review_ui_movies_movie_id_review_flag_post = cls()

        additional_properties = {}
        for prop_name, prop_dict in d.items():

            def _parse_additional_property(data: object) -> bool | int:
                return cast(bool | int, data)

            additional_property = _parse_additional_property(prop_dict)

            additional_properties[prop_name] = additional_property

        flag_movie_for_review_ui_movies_movie_id_review_flag_post_response_flag_movie_for_review_ui_movies_movie_id_review_flag_post.additional_properties = additional_properties
        return flag_movie_for_review_ui_movies_movie_id_review_flag_post_response_flag_movie_for_review_ui_movies_movie_id_review_flag_post

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> bool | int:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: bool | int) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
