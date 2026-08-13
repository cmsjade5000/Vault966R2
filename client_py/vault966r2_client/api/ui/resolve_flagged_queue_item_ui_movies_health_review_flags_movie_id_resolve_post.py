from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    movie_id: int,
    *,
    flag_reason: None | str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_flag_reason: None | str | Unset
    if isinstance(flag_reason, Unset):
        json_flag_reason = UNSET
    else:
        json_flag_reason = flag_reason
    params["flag_reason"] = json_flag_reason

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/ui/movies/health/review/flags/{movie_id}/resolve".format(
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
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    flag_reason: None | str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Resolve Flagged Queue Item

    Args:
        movie_id (int):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        flag_reason=flag_reason,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    flag_reason: None | str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Resolve Flagged Queue Item

    Args:
        movie_id (int):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
        flag_reason=flag_reason,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    flag_reason: None | str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Resolve Flagged Queue Item

    Args:
        movie_id (int):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
        flag_reason=flag_reason,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
    flag_reason: None | str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Resolve Flagged Queue Item

    Args:
        movie_id (int):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
            flag_reason=flag_reason,
        )
    ).parsed
