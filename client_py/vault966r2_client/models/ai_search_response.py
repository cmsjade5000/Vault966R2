from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.movie_facets import MovieFacets
    from ..models.movie_read import MovieRead
    from ..models.search_plan import SearchPlan


T = TypeVar("T", bound="AiSearchResponse")


@_attrs_define
class AiSearchResponse:
    """
    Attributes:
        explanation (str):
        facets (MovieFacets):
        items (list['MovieRead']):
        page (int):
        page_size (int):
        plan (SearchPlan):
        total (int):
    """

    explanation: str
    facets: "MovieFacets"
    items: list["MovieRead"]
    page: int
    page_size: int
    plan: "SearchPlan"
    total: int

    def to_dict(self) -> dict[str, Any]:
        explanation = self.explanation

        facets = self.facets.to_dict()

        items = []
        for items_item_data in self.items:
            items_item = items_item_data.to_dict()
            items.append(items_item)

        page = self.page

        page_size = self.page_size

        plan = self.plan.to_dict()

        total = self.total

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "explanation": explanation,
                "facets": facets,
                "items": items,
                "page": page,
                "page_size": page_size,
                "plan": plan,
                "total": total,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.movie_facets import MovieFacets
        from ..models.movie_read import MovieRead
        from ..models.search_plan import SearchPlan

        d = dict(src_dict)
        explanation = d.pop("explanation")

        facets = MovieFacets.from_dict(d.pop("facets"))

        items = []
        _items = d.pop("items")
        for items_item_data in _items:
            items_item = MovieRead.from_dict(items_item_data)

            items.append(items_item)

        page = d.pop("page")

        page_size = d.pop("page_size")

        plan = SearchPlan.from_dict(d.pop("plan"))

        total = d.pop("total")

        ai_search_response = cls(
            explanation=explanation,
            facets=facets,
            items=items,
            page=page,
            page_size=page_size,
            plan=plan,
            total=total,
        )

        return ai_search_response
