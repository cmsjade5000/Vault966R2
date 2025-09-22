from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.movie_search_response import MovieSearchResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, int] = UNSET,
    year_max: Union[None, Unset, int] = UNSET,
    runtime_min: Union[None, Unset, int] = UNSET,
    runtime_max: Union[None, Unset, int] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    page_size: Union[Unset, int] = 24,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_q: Union[None, Unset, str]
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    json_year_min: Union[None, Unset, int]
    if isinstance(year_min, Unset):
        json_year_min = UNSET
    else:
        json_year_min = year_min
    params["year_min"] = json_year_min

    json_year_max: Union[None, Unset, int]
    if isinstance(year_max, Unset):
        json_year_max = UNSET
    else:
        json_year_max = year_max
    params["year_max"] = json_year_max

    json_runtime_min: Union[None, Unset, int]
    if isinstance(runtime_min, Unset):
        json_runtime_min = UNSET
    else:
        json_runtime_min = runtime_min
    params["runtime_min"] = json_runtime_min

    json_runtime_max: Union[None, Unset, int]
    if isinstance(runtime_max, Unset):
        json_runtime_max = UNSET
    else:
        json_runtime_max = runtime_max
    params["runtime_max"] = json_runtime_max

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

    params["page"] = page

    params["page_size"] = page_size

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/movies/search",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[HTTPValidationError, MovieSearchResponse]]:
    if response.status_code == 200:
        response_200 = MovieSearchResponse.from_dict(response.json())

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
) -> Response[Union[HTTPValidationError, MovieSearchResponse]]:
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
    year_min: Union[None, Unset, int] = UNSET,
    year_max: Union[None, Unset, int] = UNSET,
    runtime_min: Union[None, Unset, int] = UNSET,
    runtime_max: Union[None, Unset, int] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    page_size: Union[Unset, int] = 24,
) -> Response[Union[HTTPValidationError, MovieSearchResponse]]:
    """Search Movies

    Args:
        q (Union[None, Unset, str]): Case-insensitive search on movie title
        year_min (Union[None, Unset, int]):
        year_max (Union[None, Unset, int]):
        runtime_min (Union[None, Unset, int]):
        runtime_max (Union[None, Unset, int]):
        genres (Union[None, Unset, str]): Comma separated list of genre names
        moods (Union[None, Unset, str]): Comma separated list of mood names
        page (Union[Unset, int]):  Default: 1.
        page_size (Union[Unset, int]):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, MovieSearchResponse]]
    """

    kwargs = _get_kwargs(
        q=q,
        year_min=year_min,
        year_max=year_max,
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        genres=genres,
        moods=moods,
        page=page,
        page_size=page_size,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, int] = UNSET,
    year_max: Union[None, Unset, int] = UNSET,
    runtime_min: Union[None, Unset, int] = UNSET,
    runtime_max: Union[None, Unset, int] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    page_size: Union[Unset, int] = 24,
) -> Optional[Union[HTTPValidationError, MovieSearchResponse]]:
    """Search Movies

    Args:
        q (Union[None, Unset, str]): Case-insensitive search on movie title
        year_min (Union[None, Unset, int]):
        year_max (Union[None, Unset, int]):
        runtime_min (Union[None, Unset, int]):
        runtime_max (Union[None, Unset, int]):
        genres (Union[None, Unset, str]): Comma separated list of genre names
        moods (Union[None, Unset, str]): Comma separated list of mood names
        page (Union[Unset, int]):  Default: 1.
        page_size (Union[Unset, int]):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, MovieSearchResponse]
    """

    return sync_detailed(
        client=client,
        q=q,
        year_min=year_min,
        year_max=year_max,
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        genres=genres,
        moods=moods,
        page=page,
        page_size=page_size,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, int] = UNSET,
    year_max: Union[None, Unset, int] = UNSET,
    runtime_min: Union[None, Unset, int] = UNSET,
    runtime_max: Union[None, Unset, int] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    page_size: Union[Unset, int] = 24,
) -> Response[Union[HTTPValidationError, MovieSearchResponse]]:
    """Search Movies

    Args:
        q (Union[None, Unset, str]): Case-insensitive search on movie title
        year_min (Union[None, Unset, int]):
        year_max (Union[None, Unset, int]):
        runtime_min (Union[None, Unset, int]):
        runtime_max (Union[None, Unset, int]):
        genres (Union[None, Unset, str]): Comma separated list of genre names
        moods (Union[None, Unset, str]): Comma separated list of mood names
        page (Union[Unset, int]):  Default: 1.
        page_size (Union[Unset, int]):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, MovieSearchResponse]]
    """

    kwargs = _get_kwargs(
        q=q,
        year_min=year_min,
        year_max=year_max,
        runtime_min=runtime_min,
        runtime_max=runtime_max,
        genres=genres,
        moods=moods,
        page=page,
        page_size=page_size,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    q: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, int] = UNSET,
    year_max: Union[None, Unset, int] = UNSET,
    runtime_min: Union[None, Unset, int] = UNSET,
    runtime_max: Union[None, Unset, int] = UNSET,
    genres: Union[None, Unset, str] = UNSET,
    moods: Union[None, Unset, str] = UNSET,
    page: Union[Unset, int] = 1,
    page_size: Union[Unset, int] = 24,
) -> Optional[Union[HTTPValidationError, MovieSearchResponse]]:
    """Search Movies

    Args:
        q (Union[None, Unset, str]): Case-insensitive search on movie title
        year_min (Union[None, Unset, int]):
        year_max (Union[None, Unset, int]):
        runtime_min (Union[None, Unset, int]):
        runtime_max (Union[None, Unset, int]):
        genres (Union[None, Unset, str]): Comma separated list of genre names
        moods (Union[None, Unset, str]): Comma separated list of mood names
        page (Union[Unset, int]):  Default: 1.
        page_size (Union[Unset, int]):  Default: 24.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, MovieSearchResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            q=q,
            year_min=year_min,
            year_max=year_max,
            runtime_min=runtime_min,
            runtime_max=runtime_max,
            genres=genres,
            moods=moods,
            page=page,
            page_size=page_size,
        )
    ).parsed
