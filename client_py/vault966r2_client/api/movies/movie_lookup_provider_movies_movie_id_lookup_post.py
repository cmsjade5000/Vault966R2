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
    title: None | str | Unset = UNSET,
    year: int | None | Unset = UNSET,
    limit: int | Unset = 5,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_title: None | str | Unset
    if isinstance(title, Unset):
        json_title = UNSET
    else:
        json_title = title
    params["title"] = json_title

    json_year: int | None | Unset
    if isinstance(year, Unset):
        json_year = UNSET
    else:
        json_year = year
    params["year"] = json_year

    params["limit"] = limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/movies/{movie_id}/lookup".format(
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

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if response.status_code == 429:
        response_429 = ErrorResponse.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = ErrorResponse.from_dict(response.json())

        return response_500

    if response.status_code == 502:
        response_502 = ErrorResponse.from_dict(response.json())

        return response_502

    if response.status_code == 503:
        response_503 = ErrorResponse.from_dict(response.json())

        return response_503

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
    title: None | str | Unset = UNSET,
    year: int | None | Unset = UNSET,
    limit: int | Unset = 5,
) -> Response[ErrorResponse | MovieLookupResponse]:
    """Movie Lookup Provider

    Args:
        movie_id (int):
        title (None | str | Unset): Override title to search
        year (int | None | Unset):
        limit (int | Unset):  Default: 5.

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
        limit=limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: None | str | Unset = UNSET,
    year: int | None | Unset = UNSET,
    limit: int | Unset = 5,
) -> ErrorResponse | MovieLookupResponse | None:
    """Movie Lookup Provider

    Args:
        movie_id (int):
        title (None | str | Unset): Override title to search
        year (int | None | Unset):
        limit (int | Unset):  Default: 5.

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
        limit=limit,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: None | str | Unset = UNSET,
    year: int | None | Unset = UNSET,
    limit: int | Unset = 5,
) -> Response[ErrorResponse | MovieLookupResponse]:
    """Movie Lookup Provider

    Args:
        movie_id (int):
        title (None | str | Unset): Override title to search
        year (int | None | Unset):
        limit (int | Unset):  Default: 5.

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
        limit=limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    title: None | str | Unset = UNSET,
    year: int | None | Unset = UNSET,
    limit: int | Unset = 5,
) -> ErrorResponse | MovieLookupResponse | None:
    """Movie Lookup Provider

    Args:
        movie_id (int):
        title (None | str | Unset): Override title to search
        year (int | None | Unset):
        limit (int | Unset):  Default: 5.

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
            limit=limit,
        )
    ).parsed
