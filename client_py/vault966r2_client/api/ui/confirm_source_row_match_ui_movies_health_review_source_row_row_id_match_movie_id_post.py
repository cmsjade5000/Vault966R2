from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    row_id: int,
    movie_id: int,
    *,
    view: str | Unset = "ambiguous",
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["view"] = view

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/ui/movies/health/review/source-row/{row_id}/match/{movie_id}".format(
            row_id=quote(str(row_id), safe=""),
            movie_id=quote(str(movie_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Any | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = response.json()
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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[Any | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    row_id: int,
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    view: str | Unset = "ambiguous",
) -> Response[Any | ErrorResponse]:
    """Confirm Source Row Match

    Args:
        row_id (int):
        movie_id (int):
        view (str | Unset):  Default: 'ambiguous'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        row_id=row_id,
        movie_id=movie_id,
        view=view,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    row_id: int,
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    view: str | Unset = "ambiguous",
) -> Any | ErrorResponse | None:
    """Confirm Source Row Match

    Args:
        row_id (int):
        movie_id (int):
        view (str | Unset):  Default: 'ambiguous'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return sync_detailed(
        row_id=row_id,
        movie_id=movie_id,
        client=client,
        view=view,
    ).parsed


async def asyncio_detailed(
    row_id: int,
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    view: str | Unset = "ambiguous",
) -> Response[Any | ErrorResponse]:
    """Confirm Source Row Match

    Args:
        row_id (int):
        movie_id (int):
        view (str | Unset):  Default: 'ambiguous'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        row_id=row_id,
        movie_id=movie_id,
        view=view,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    row_id: int,
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    view: str | Unset = "ambiguous",
) -> Any | ErrorResponse | None:
    """Confirm Source Row Match

    Args:
        row_id (int):
        movie_id (int):
        view (str | Unset):  Default: 'ambiguous'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return (
        await asyncio_detailed(
            row_id=row_id,
            movie_id=movie_id,
            client=client,
            view=view,
        )
    ).parsed
