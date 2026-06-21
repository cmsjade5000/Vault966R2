from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="LlmMovieSearchRequest")


@_attrs_define
class LlmMovieSearchRequest:
    """
    Attributes:
        query (str):
        page (int | Unset):  Default: 1.
        page_size (int | Unset):  Default: 24.
    """

    query: str
    page: int | Unset = 1
    page_size: int | Unset = 24

    def to_dict(self) -> dict[str, Any]:
        query = self.query

        page = self.page

        page_size = self.page_size

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "query": query,
            }
        )
        if page is not UNSET:
            field_dict["page"] = page
        if page_size is not UNSET:
            field_dict["page_size"] = page_size

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        query = d.pop("query")

        page = d.pop("page", UNSET)

        page_size = d.pop("page_size", UNSET)

        llm_movie_search_request = cls(
            query=query,
            page=page,
            page_size=page_size,
        )

        return llm_movie_search_request
