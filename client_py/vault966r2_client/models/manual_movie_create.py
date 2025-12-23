from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, Union, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.manual_movie_metadata import ManualMovieMetadata


T = TypeVar("T", bound="ManualMovieCreate")


@_attrs_define
class ManualMovieCreate:
    """
    Attributes:
        title (str):
        metadata (Union['ManualMovieMetadata', None, Unset]):
        vudu (Union[Unset, bool]):  Default: False.
        year (Union[None, Unset, int]):
    """

    title: str
    metadata: Union["ManualMovieMetadata", None, Unset] = UNSET
    vudu: Union[Unset, bool] = False
    year: Union[None, Unset, int] = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.manual_movie_metadata import ManualMovieMetadata

        title = self.title

        metadata: Union[None, Unset, dict[str, Any]]
        if isinstance(self.metadata, Unset):
            metadata = UNSET
        elif isinstance(self.metadata, ManualMovieMetadata):
            metadata = self.metadata.to_dict()
        else:
            metadata = self.metadata

        vudu = self.vudu

        year: Union[None, Unset, int]
        if isinstance(self.year, Unset):
            year = UNSET
        else:
            year = self.year

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "title": title,
            }
        )
        if metadata is not UNSET:
            field_dict["metadata"] = metadata
        if vudu is not UNSET:
            field_dict["vudu"] = vudu
        if year is not UNSET:
            field_dict["year"] = year

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.manual_movie_metadata import ManualMovieMetadata

        d = dict(src_dict)
        title = d.pop("title")

        def _parse_metadata(data: object) -> Union["ManualMovieMetadata", None, Unset]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                metadata_type_0 = ManualMovieMetadata.from_dict(data)

                return metadata_type_0
            except:  # noqa: E722
                pass
            return cast(Union["ManualMovieMetadata", None, Unset], data)

        metadata = _parse_metadata(d.pop("metadata", UNSET))

        vudu = d.pop("vudu", UNSET)

        def _parse_year(data: object) -> Union[None, Unset, int]:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(Union[None, Unset, int], data)

        year = _parse_year(d.pop("year", UNSET))

        manual_movie_create = cls(
            title=title,
            metadata=metadata,
            vudu=vudu,
            year=year,
        )

        manual_movie_create.additional_properties = d
        return manual_movie_create

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
