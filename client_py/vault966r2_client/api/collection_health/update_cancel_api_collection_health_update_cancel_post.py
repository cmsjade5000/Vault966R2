from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.update_cancel_api_collection_health_update_cancel_post_response_update_cancel_api_collection_health_update_cancel_post import (
    UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost,
)
from ...types import Response


def _get_kwargs() -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/collection-health/update/cancel",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ErrorResponse
    | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
    | None
):
    if response.status_code == 200:
        response_200 = UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost.from_dict(
            response.json()
        )

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

    if response.status_code == 429:
        response_429 = ErrorResponse.from_dict(response.json())

        return response_429

    if response.status_code == 500:
        response_500 = ErrorResponse.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ErrorResponse
    | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[
    ErrorResponse
    | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
]:
    """Update Cancel

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> (
    ErrorResponse
    | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
    | None
):
    """Update Cancel

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[
    ErrorResponse
    | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
]:
    """Update Cancel

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> (
    ErrorResponse
    | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
    | None
):
    """Update Cancel

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UpdateCancelApiCollectionHealthUpdateCancelPostResponseUpdateCancelApiCollectionHealthUpdateCancelPost
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
