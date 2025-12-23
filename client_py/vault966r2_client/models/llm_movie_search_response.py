from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.llm_movie_filters import LlmMovieFilters
    from ..models.movie_facets import MovieFacets
    from ..models.movie_read import MovieRead


T = TypeVar("T", bound="LlmMovieSearchResponse")


@_attrs_define
class LlmMovieSearchResponse:
    """
    Attributes:
        facets (MovieFacets):
        filters (LlmMovieFilters):
        items (list['MovieRead']):
        page (int):
        page_size (int):
        total (int):
    """

    facets: "MovieFacets"
    filters: "LlmMovieFilters"
    items: list["MovieRead"]
    page: int
    page_size: int
    total: int

    def to_dict(self) -> dict[str, Any]:
        facets = self.facets.to_dict()

        filters = self.filters.to_dict()

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        page = self.page

        page_size = self.page_size

        total = self.total

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "facets": facets,
                "filters": filters,
                "items": items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.llm_movie_filters import LlmMovieFilters
        from ..models.movie_facets import MovieFacets
        from ..models.movie_read import MovieRead

        d = dict(src_dict)
        facets = MovieFacets.from_dict(d.pop("facets"))

        filters = LlmMovieFilters.from_dict(d.pop("filters"))

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = MovieRead.from_dict(items_item_data)

            items.append(items_item)

        page = d.pop("page")

        page_size = d.pop("page_size")

        total = d.pop("total")

        llm_movie_search_response = cls(
            facets=facets,
            filters=filters,
            items=items,
            page=page,
            page_size=page_size,
            total=total,
        )

        return llm_movie_search_response
