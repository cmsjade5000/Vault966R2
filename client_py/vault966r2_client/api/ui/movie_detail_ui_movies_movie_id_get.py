from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    movie_id: int,
    *,
    review: bool | Unset = False,
    spotlight: bool | Unset = False,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["review"] = review

    params["spotlight"] = spotlight

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/ui/movies/{movie_id}".format(
            movie_id=quote(str(movie_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | str | None:
    if response.status_code == 200:
        response_200 = response.text
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
) -> Response[HTTPValidationError | str]:
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
    review: bool | Unset = False,
    spotlight: bool | Unset = False,
) -> Response[HTTPValidationError | str]:
    """Movie Detail

    Args:
        movie_id (int):
        review (bool | Unset):  Default: False.
        spotlight (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | str]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        review=review,
        spotlight=spotlight,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    review: bool | Unset = False,
    spotlight: bool | Unset = False,
) -> HTTPValidationError | str | None:
    """Movie Detail

    Args:
        movie_id (int):
        review (bool | Unset):  Default: False.
        spotlight (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | str
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
        review=review,
        spotlight=spotlight,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    review: bool | Unset = False,
    spotlight: bool | Unset = False,
) -> Response[HTTPValidationError | str]:
    """Movie Detail

    Args:
        movie_id (int):
        review (bool | Unset):  Default: False.
        spotlight (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | str]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        review=review,
        spotlight=spotlight,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    review: bool | Unset = False,
    spotlight: bool | Unset = False,
) -> HTTPValidationError | str | None:
    """Movie Detail

    Args:
        movie_id (int):
        review (bool | Unset):  Default: False.
        spotlight (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | str
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            review=review,
            spotlight=spotlight,
        )
    ).parsed
