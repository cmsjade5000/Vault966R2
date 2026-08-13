from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.movie_match_apply_response import MovieMatchApplyResponse
from ...models.movie_match_selection import MovieMatchSelection
from ...types import Response


def _get_kwargs(
    movie_id: int,
    *,
    body: MovieMatchSelection,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/ui/movies/health/review/{movie_id}/matches/apply".format(
            movie_id=quote(str(movie_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | MovieMatchApplyResponse | None:
    if response.status_code == 200:
        response_200 = MovieMatchApplyResponse.from_dict(response.json())

        return response_200

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

        return response_409

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
) -> Response[ErrorResponse | MovieMatchApplyResponse]:
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
    body: MovieMatchSelection,
) -> Response[ErrorResponse | MovieMatchApplyResponse]:
    """Apply Flagged Movie Match

    Args:
        movie_id (int):
        body (MovieMatchSelection):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | MovieMatchApplyResponse]
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
    body: MovieMatchSelection,
) -> ErrorResponse | MovieMatchApplyResponse | None:
    """Apply Flagged Movie Match

    Args:
        movie_id (int):
        body (MovieMatchSelection):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | MovieMatchApplyResponse
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
    body: MovieMatchSelection,
) -> Response[ErrorResponse | MovieMatchApplyResponse]:
    """Apply Flagged Movie Match

    Args:
        movie_id (int):
        body (MovieMatchSelection):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | MovieMatchApplyResponse]
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
    body: MovieMatchSelection,
) -> ErrorResponse | MovieMatchApplyResponse | None:
    """Apply Flagged Movie Match

    Args:
        movie_id (int):
        body (MovieMatchSelection):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | MovieMatchApplyResponse
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            body=body,
        )
    ).parsed
