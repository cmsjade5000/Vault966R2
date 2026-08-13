from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.update_run_api_collection_health_update_run_post_response_update_run_api_collection_health_update_run_post import (
    UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    task: str | Unset = "all",
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["task"] = task

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/collection-health/update/run",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost | None:
    if response.status_code == 200:
        response_200 = (
            UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost.from_dict(
                response.json()
            )
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

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

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
    ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
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
    task: str | Unset = "all",
) -> Response[
    ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
]:
    """Update Run

    Args:
        task (str | Unset):  Default: 'all'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]
    """

    kwargs = _get_kwargs(
        task=task,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    task: str | Unset = "all",
) -> ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost | None:
    """Update Run

    Args:
        task (str | Unset):  Default: 'all'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
    """

    return sync_detailed(
        client=client,
        task=task,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    task: str | Unset = "all",
) -> Response[
    ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
]:
    """Update Run

    Args:
        task (str | Unset):  Default: 'all'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost]
    """

    kwargs = _get_kwargs(
        task=task,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    task: str | Unset = "all",
) -> ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost | None:
    """Update Run

    Args:
        task (str | Unset):  Default: 'all'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UpdateRunApiCollectionHealthUpdateRunPostResponseUpdateRunApiCollectionHealthUpdateRunPost
    """

    return (
        await asyncio_detailed(
            client=client,
            task=task,
        )
    ).parsed
