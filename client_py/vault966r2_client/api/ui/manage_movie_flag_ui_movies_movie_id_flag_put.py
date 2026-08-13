from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.movie_flag_create import MovieFlagCreate
from ...models.movie_flag_read import MovieFlagRead
from ...types import Response


def _get_kwargs(
    movie_id: int,
    *,
    body: MovieFlagCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/ui/movies/{movie_id}/flag".format(
            movie_id=quote(str(movie_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | MovieFlagRead | None:
    if response.status_code == 200:
        response_200 = MovieFlagRead.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if response.status_code == 500:
        response_500 = ErrorResponse.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | MovieFlagRead]:
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
    body: MovieFlagCreate,
) -> Response[ErrorResponse | MovieFlagRead]:
    """Manage Movie Flag

    Args:
        movie_id (int):
        body (MovieFlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | MovieFlagRead]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: MovieFlagCreate,
) -> ErrorResponse | MovieFlagRead | None:
    """Manage Movie Flag

    Args:
        movie_id (int):
        body (MovieFlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | MovieFlagRead
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: MovieFlagCreate,
) -> Response[ErrorResponse | MovieFlagRead]:
    """Manage Movie Flag

    Args:
        movie_id (int):
        body (MovieFlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | MovieFlagRead]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: MovieFlagCreate,
) -> ErrorResponse | MovieFlagRead | None:
    """Manage Movie Flag

    Args:
        movie_id (int):
        body (MovieFlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | MovieFlagRead
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            body=body,
        )
    ).parsed
