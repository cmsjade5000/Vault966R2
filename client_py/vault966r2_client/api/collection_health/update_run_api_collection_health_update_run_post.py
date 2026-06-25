from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.update_run_api_collection_health_update_run_post_response_update_run_api_collection_health_update_run_post import (
    UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost,
)
from ...types import Response


def _get_kwargs() -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/collection-health/update/run",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost | None:
    if response.status_code == 200:
        response_200 = (
            UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost.from_dict(
                response.json()
            )
        )

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]:
    """Update Run

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
) -> UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost | None:
    """Update Run

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
) -> Response[UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]:
    """Update Run

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
) -> UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost | None:
    """Update Run

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
