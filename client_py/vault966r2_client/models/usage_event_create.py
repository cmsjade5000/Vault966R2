from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.usage_event_create_event_name import UsageEventCreateEventName
from ..models.usage_event_create_page import UsageEventCreatePage
from ..types import UNSET, Unset

T = TypeVar("T", bound="UsageEventCreate")


@_attrs_define
class UsageEventCreate:
    """
    Attributes:
        event_name (UsageEventCreateEventName):
        page (UsageEventCreatePage):
        context (None | str | Unset):
        movie_id (int | None | Unset):
    """

    event_name: UsageEventCreateEventName
    page: UsageEventCreatePage
    context: None | str | Unset = UNSET
    movie_id: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        event_name = self.event_name.value

        page = self.page.value

        context: None | str | Unset
        if isinstance(self.context, Unset):
            context = UNSET
        else:
            context = self.context

        movie_id: int | None | Unset
        if isinstance(self.movie_id, Unset):
            movie_id = UNSET
        else:
            movie_id = self.movie_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "event_name": event_name,
                "page": page,
            }
        )
        if context is not UNSET:
            field_dict["context"] = context
        if movie_id is not UNSET:
            field_dict["movie_id"] = movie_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        event_name = UsageEventCreateEventName(d.pop("event_name"))

        page = UsageEventCreatePage(d.pop("page"))

        def _parse_context(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        context = _parse_context(d.pop("context", UNSET))

        def _parse_movie_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        movie_id = _parse_movie_id(d.pop("movie_id", UNSET))

        usage_event_create = cls(
            event_name=event_name,
            page=page,
            context=context,
            movie_id=movie_id,
        )

        return usage_event_create
