from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.movie_lookup_response import MovieLookupResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    movie_id: int,
    *,
    title: str,
    year: int | None | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["title"] = title

    json_year: int | None | Unset
    if isinstance(year, Unset):
        json_year = UNSET
    else:
        json_year = year
    params["year"] = json_year

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/ui/movies/health/review/{movie_id}/matches".format(
            movie_id=quote(str(movie_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | MovieLookupResponse | None:
    if response.status_code == 200:
        response_200 = MovieLookupResponse.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if response.status_code == 500:
        response_500 = ErrorResponse.from_dict(response.json())

        return response_500

    if response.status_code == 502:
        response_502 = ErrorResponse.from_dict(response.json())

        return response_502

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | MovieLookupResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: str,
    year: int | None | Unset = UNSET,
) -> Response[ErrorResponse | MovieLookupResponse]:
    """Search Flagged Movie Matches

    Args:
        movie_id (int):
        title (str):
        year (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | MovieLookupResponse]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        title=title,
        year=year,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: str,
    year: int | None | Unset = UNSET,
) -> ErrorResponse | MovieLookupResponse | None:
    """Search Flagged Movie Matches

    Args:
        movie_id (int):
        title (str):
        year (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | MovieLookupResponse
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
        title=title,
        year=year,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: str,
    year: int | None | Unset = UNSET,
) -> Response[ErrorResponse | MovieLookupResponse]:
    """Search Flagged Movie Matches

    Args:
        movie_id (int):
        title (str):
        year (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | MovieLookupResponse]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        title=title,
        year=year,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: str,
    year: int | None | Unset = UNSET,
) -> ErrorResponse | MovieLookupResponse | None:
    """Search Flagged Movie Matches

    Args:
        movie_id (int):
        title (str):
        year (int | None | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | MovieLookupResponse
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            title=title,
            year=year,
        )
    ).parsed
