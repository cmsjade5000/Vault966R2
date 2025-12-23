from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: Union[None, Unset, str] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    order_by: Union[Unset, str] = "title_asc",
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_q: Union[None, Unset, str]
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    json_genres: Union[None, Unset, str]
    if isinstance(genres, Unset):
        json_genres = UNSET
    else:
        json_genres = genres
    params["genres"] = json_genres

    json_moods: Union[None, Unset, str]
    if isinstance(moods, Unset):
        json_moods = UNSET
    else:
        json_moods = moods
    params["moods"] = json_moods

    json_year_min: Union[None, Unset, str]
    if isinstance(year_min, Unset):
        json_year_min = UNSET
    else:
        json_year_min = year_min
    params["year_min"] = json_year_min

    json_year_max: Union[None, Unset, str]
    if isinstance(year_max, Unset):
        json_year_max = UNSET
    else:
        json_year_max = year_max
    params["year_max"] = json_year_max

    json_runtime_max: Union[None, Unset, str]
    if isinstance(runtime_max, Unset):
        json_runtime_max = UNSET
    else:
        json_runtime_max = runtime_max
    params["runtime_max"] = json_runtime_max

    params["page"] = page

    params["order_by"] = order_by

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/ui/movies",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[HTTPValidationError, str]]:
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
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Response[Union[HTTPValidationError, str]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    order_by: Union[Unset, str] = "title_asc",
) -> Response[Union[HTTPValidationError, str]]:
    """Movies Grid

    Args:
        q (Union[None, Unset, str]):
        genres (Union[None, Unset, str]):
        moods (Union[None, Unset, str]):
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):
        page (Union[Unset, int]):  Default: 1.
        order_by (Union[Unset, str]):  Default: 'title_asc'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, str]]
    """

    kwargs = _get_kwargs(
        q=q,
        genres=genres,
        moods=moods,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
        page=page,
        order_by=order_by,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    order_by: Union[Unset, str] = "title_asc",
) -> Optional[Union[HTTPValidationError, str]]:
    """Movies Grid

    Args:
        q (Union[None, Unset, str]):
        genres (Union[None, Unset, str]):
        moods (Union[None, Unset, str]):
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):
        page (Union[Unset, int]):  Default: 1.
        order_by (Union[Unset, str]):  Default: 'title_asc'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, str]
    """

    return sync_detailed(
        client=client,
        q=q,
        genres=genres,
        moods=moods,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
        page=page,
        order_by=order_by,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    order_by: Union[Unset, str] = "title_asc",
) -> Response[Union[HTTPValidationError, str]]:
    """Movies Grid

    Args:
        q (Union[None, Unset, str]):
        genres (Union[None, Unset, str]):
        moods (Union[None, Unset, str]):
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):
        page (Union[Unset, int]):  Default: 1.
        order_by (Union[Unset, str]):  Default: 'title_asc'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, str]]
    """

    kwargs = _get_kwargs(
        q=q,
        genres=genres,
        moods=moods,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
        page=page,
        order_by=order_by,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    order_by: Union[Unset, str] = "title_asc",
) -> Optional[Union[HTTPValidationError, str]]:
    """Movies Grid

    Args:
        q (Union[None, Unset, str]):
        genres (Union[None, Unset, str]):
        moods (Union[None, Unset, str]):
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):
        page (Union[Unset, int]):  Default: 1.
        order_by (Union[Unset, str]):  Default: 'title_asc'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, str]
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            genres=genres,
            moods=moods,
            year_min=year_min,
            year_max=year_max,
            runtime_max=runtime_max,
            page=page,
            order_by=order_by,
        )
    ).parsed
