from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.update_preview_api_collection_health_update_preview_get_response_update_preview_api_collection_health_update_preview_get import (
    UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet,
)
from ...types import Response


def _get_kwargs() -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/collection-health/update/preview",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ErrorResponse
    | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
    | None
):
    if response.status_code == 200:
        response_200 = UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet.from_dict(
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
    | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
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
    | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
]:
    """Update Preview

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet]
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
    | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
    | None
):
    """Update Preview

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[
    ErrorResponse
    | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
]:
    """Update Preview

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> (
    ErrorResponse
    | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
    | None
):
    """Update Preview

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UpdatePreviewApiCollectionHealthUpdatePreviewGetResponseUpdatePreviewApiCollectionHealthUpdatePreviewGet
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
