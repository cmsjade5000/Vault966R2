from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.discover_refresh_api_discover_refresh_get_response_discover_refresh_api_discover_refresh_get import (
    DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet,
)
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    seed: int | None | Unset = UNSET,
    pairings_limit: int | Unset = 2,
    genre_limit: int | Unset = 6,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_seed: int | None | Unset
    if isinstance(seed, Unset):
        json_seed = UNSET
    else:
        json_seed = seed
    params["seed"] = json_seed

    params["pairings_limit"] = pairings_limit

    params["genre_limit"] = genre_limit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/discover/refresh",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet.from_dict(
            response.json()
        )

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    seed: int | None | Unset = UNSET,
    pairings_limit: int | Unset = 2,
    genre_limit: int | Unset = 6,
) -> Response[DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError]:
    """Discover Refresh

    Args:
        seed (int | None | Unset):
        pairings_limit (int | Unset):  Default: 2.
        genre_limit (int | Unset):  Default: 6.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        seed=seed,
        pairings_limit=pairings_limit,
        genre_limit=genre_limit,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    seed: int | None | Unset = UNSET,
    pairings_limit: int | Unset = 2,
    genre_limit: int | Unset = 6,
) -> DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError | None:
    """Discover Refresh

    Args:
        seed (int | None | Unset):
        pairings_limit (int | Unset):  Default: 2.
        genre_limit (int | Unset):  Default: 6.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        seed=seed,
        pairings_limit=pairings_limit,
        genre_limit=genre_limit,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    seed: int | None | Unset = UNSET,
    pairings_limit: int | Unset = 2,
    genre_limit: int | Unset = 6,
) -> Response[DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError]:
    """Discover Refresh

    Args:
        seed (int | None | Unset):
        pairings_limit (int | Unset):  Default: 2.
        genre_limit (int | Unset):  Default: 6.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        seed=seed,
        pairings_limit=pairings_limit,
        genre_limit=genre_limit,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    seed: int | None | Unset = UNSET,
    pairings_limit: int | Unset = 2,
    genre_limit: int | Unset = 6,
) -> DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError | None:
    """Discover Refresh

    Args:
        seed (int | None | Unset):
        pairings_limit (int | Unset):  Default: 2.
        genre_limit (int | Unset):  Default: 6.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DiscoverRefreshApiDiscoverRefreshGetResponseDiscoverRefreshApiDiscoverRefreshGet | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            seed=seed,
            pairings_limit=pairings_limit,
            genre_limit=genre_limit,
        )
    ).parsed
