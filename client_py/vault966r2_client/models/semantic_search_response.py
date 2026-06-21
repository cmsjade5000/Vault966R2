from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.movie_facets import MovieFacets
    from ..models.semantic_search_item import SemanticSearchItem


T = TypeVar("T", bound="SemanticSearchResponse")


@_attrs_define
class SemanticSearchResponse:
    """
    Attributes:
        facets (MovieFacets):
        items (list[SemanticSearchItem]):
        mode (str):
        page (int):
        page_size (int):
        total (int):
        notice (None | str | Unset):
    """

    facets: MovieFacets
    items: list[SemanticSearchItem]
    mode: str
    page: int
    page_size: int
    total: int
    notice: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        facets = self.facets.to_dict()

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        mode = self.mode

        page = self.page

        page_size = self.page_size

        total = self.total

        notice: None | str | Unset
        if isinstance(self.notice, Unset):
            notice = UNSET
        else:
            notice = self.notice

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "facets": facets,
                "items": items,
                "mode": mode,
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        )
        if notice is not UNSET:
            field_dict["notice"] = notice

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.movie_facets import MovieFacets
        from ..models.semantic_search_item import SemanticSearchItem

        d = dict(src_dict)
        facets = MovieFacets.from_dict(d.pop("facets"))

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = SemanticSearchItem.from_dict(items_item_data)

            items.append(items_item)

        mode = d.pop("mode")

        page = d.pop("page")

        page_size = d.pop("page_size")

        total = d.pop("total")

        def _parse_notice(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        notice = _parse_notice(d.pop("notice", UNSET))

        semantic_search_response = cls(
            facets=facets,
            items=items,
            mode=mode,
            page=page,
            page_size=page_size,
            total=total,
            notice=notice,
        )

        semantic_search_response.additional_properties = d
        return semantic_search_response

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
