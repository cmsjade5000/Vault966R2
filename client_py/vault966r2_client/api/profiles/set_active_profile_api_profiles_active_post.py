from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.active_profile_request import ActiveProfileRequest
from ...models.http_validation_error import HTTPValidationError
from ...models.set_active_profile_api_profiles_active_post_response_set_active_profile_api_profiles_active_post import (
    SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost,
)
from ...types import Response


def _get_kwargs(
    *,
    body: ActiveProfileRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/profiles/active",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost | None:
    if response.status_code == 200:
        response_200 = SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost.from_dict(
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
) -> Response[HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ActiveProfileRequest,
) -> Response[HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost]:
    """Set Active Profile

    Args:
        body (ActiveProfileRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: ActiveProfileRequest,
) -> HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost | None:
    """Set Active Profile

    Args:
        body (ActiveProfileRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ActiveProfileRequest,
) -> Response[HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost]:
    """Set Active Profile

    Args:
        body (ActiveProfileRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ActiveProfileRequest,
) -> HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost | None:
    """Set Active Profile

    Args:
        body (ActiveProfileRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SetActiveProfileApiProfilesActivePostResponseSetActiveProfileApiProfilesActivePost
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
