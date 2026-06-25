from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar(
    "T",
    bound="RefreshRecommendationApiCollectionHealthRecommendationRefreshPostResponseRefreshRecommendationApiCollectionHealthRecommendationRefreshPost",
)


@_attrs_define
class RefreshRecommendationApiCollectionHealthRecommendationRefreshPostResponseRefreshRecommendationApiCollectionHealthRecommendationRefreshPost:
    """ """

    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        refresh_recommendation_api_collection_health_recommendation_refresh_post_response_refresh_recommendation_api_collection_health_recommendation_refresh_post = cls()

        refresh_recommendation_api_collection_health_recommendation_refresh_post_response_refresh_recommendation_api_collection_health_recommendation_refresh_post.additional_properties = d
        return refresh_recommendation_api_collection_health_recommendation_refresh_post_response_refresh_recommendation_api_collection_health_recommendation_refresh_post

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
