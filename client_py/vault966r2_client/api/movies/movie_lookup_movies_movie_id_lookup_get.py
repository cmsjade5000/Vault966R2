from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.movie_lookup_response import MovieLookupResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    movie_id: int,
    *,
    title: Union[None, Unset, str] = UNSET,
    year: Union[None, Unset, int] = UNSET,
    limit: Union[Unset, int] = 5,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_title: Union[None, Unset, str]
    if isinstance(title, Unset):
        json_title = UNSET
    else:
        json_title = title
    params["title"] = json_title

    json_year: Union[None, Unset, int]
    if isinstance(year, Unset):
        json_year = UNSET
    else:
        json_year = year
    params["year"] = json_year

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": f"/movies/{movie_id}/lookup",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[HTTPValidationError, MovieLookupResponse]]:
    if response.status_code == 200:
        response_200 = MovieLookupResponse.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[HTTPValidationError, MovieLookupResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    movie_id: int,
    *,
    client: Union[AuthenticatedClient, Client],
    title: Union[None, Unset, str] = UNSET,
    year: Union[None, Unset, int] = UNSET,
    limit: Union[Unset, int] = 5,
) -> Response[Union[HTTPValidationError, MovieLookupResponse]]:
    """Movie Lookup

    Args:
        movie_id (int):
        title (Union[None, Unset, str]): Override title to search
        year (Union[None, Unset, int]):
        limit (Union[Unset, int]):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, MovieLookupResponse]]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        title=title,
        year=year,
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: Union[AuthenticatedClient, Client],
    title: Union[None, Unset, str] = UNSET,
    year: Union[None, Unset, int] = UNSET,
    limit: Union[Unset, int] = 5,
) -> Optional[Union[HTTPValidationError, MovieLookupResponse]]:
    """Movie Lookup

    Args:
        movie_id (int):
        title (Union[None, Unset, str]): Override title to search
        year (Union[None, Unset, int]):
        limit (Union[Unset, int]):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, MovieLookupResponse]
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
        title=title,
        year=year,
        limit=limit,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: Union[AuthenticatedClient, Client],
    title: Union[None, Unset, str] = UNSET,
    year: Union[None, Unset, int] = UNSET,
    limit: Union[Unset, int] = 5,
) -> Response[Union[HTTPValidationError, MovieLookupResponse]]:
    """Movie Lookup

    Args:
        movie_id (int):
        title (Union[None, Unset, str]): Override title to search
        year (Union[None, Unset, int]):
        limit (Union[Unset, int]):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, MovieLookupResponse]]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        title=title,
        year=year,
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: Union[AuthenticatedClient, Client],
    title: Union[None, Unset, str] = UNSET,
    year: Union[None, Unset, int] = UNSET,
    limit: Union[Unset, int] = 5,
) -> Optional[Union[HTTPValidationError, MovieLookupResponse]]:
    """Movie Lookup

    Args:
        movie_id (int):
        title (Union[None, Unset, str]): Override title to search
        year (Union[None, Unset, int]):
        limit (Union[Unset, int]):  Default: 5.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, MovieLookupResponse]
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            title=title,
            year=year,
            limit=limit,
        )
    ).parsed
