from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.role_attach import RoleAttach
from ...models.role_read import RoleRead
from ...types import Response


def _get_kwargs(
    movie_id: int,
    *,
    body: RoleAttach,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/movies/{movie_id}/roles".format(
            movie_id=quote(str(movie_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | RoleRead | None:
    if response.status_code == 201:
        response_201 = RoleRead.from_dict(response.json())

        return response_201

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | RoleRead]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient,
    body: RoleAttach,
) -> Response[HTTPValidationError | RoleRead]:
    """Attach Role

    Args:
        movie_id (int):
        body (RoleAttach):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RoleRead]
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
    client: AuthenticatedClient,
    body: RoleAttach,
) -> HTTPValidationError | RoleRead | None:
    """Attach Role

    Args:
        movie_id (int):
        body (RoleAttach):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RoleRead
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient,
    body: RoleAttach,
) -> Response[HTTPValidationError | RoleRead]:
    """Attach Role

    Args:
        movie_id (int):
        body (RoleAttach):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | RoleRead]
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
    client: AuthenticatedClient,
    body: RoleAttach,
) -> HTTPValidationError | RoleRead | None:
    """Attach Role

    Args:
        movie_id (int):
        body (RoleAttach):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | RoleRead
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            body=body,
        )
    ).parsed
