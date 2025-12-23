from http import HTTPStatus
from typing import Any, Optional, Union

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.movie_read import MovieRead
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    mood: Union[None, Unset, str] = UNSET,
    genre: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_mood: Union[None, Unset, str]
    if isinstance(mood, Unset):
        json_mood = UNSET
    else:
        json_mood = mood
    params["mood"] = json_mood

    json_genre: Union[None, Unset, str]
    if isinstance(genre, Unset):
        json_genre = UNSET
    else:
        json_genre = genre
    params["genre"] = json_genre

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

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/movies/picks",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: Union[AuthenticatedClient, Client], response: httpx.Response
) -> Optional[Union[HTTPValidationError, MovieRead]]:
    if response.status_code == 200:
        response_200 = MovieRead.from_dict(response.json())

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
) -> Response[Union[HTTPValidationError, MovieRead]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    mood: Union[None, Unset, str] = UNSET,
    genre: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
) -> Response[Union[HTTPValidationError, MovieRead]]:
    """Get Pick

    Args:
        mood (Union[None, Unset, str]): Desired mood name
        genre (Union[None, Unset, str]): Restrict to this genre
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, MovieRead]]
    """

    kwargs = _get_kwargs(
        mood=mood,
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: Union[AuthenticatedClient, Client],
    mood: Union[None, Unset, str] = UNSET,
    genre: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
) -> Optional[Union[HTTPValidationError, MovieRead]]:
    """Get Pick

    Args:
        mood (Union[None, Unset, str]): Desired mood name
        genre (Union[None, Unset, str]): Restrict to this genre
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, MovieRead]
    """

    return sync_detailed(
        client=client,
        mood=mood,
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
    ).parsed


async def asyncio_detailed(
    *,
    client: Union[AuthenticatedClient, Client],
    mood: Union[None, Unset, str] = UNSET,
    genre: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
) -> Response[Union[HTTPValidationError, MovieRead]]:
    """Get Pick

    Args:
        mood (Union[None, Unset, str]): Desired mood name
        genre (Union[None, Unset, str]): Restrict to this genre
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Union[HTTPValidationError, MovieRead]]
    """

    kwargs = _get_kwargs(
        mood=mood,
        genre=genre,
        year_min=year_min,
        year_max=year_max,
        runtime_max=runtime_max,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: Union[AuthenticatedClient, Client],
    mood: Union[None, Unset, str] = UNSET,
    genre: Union[None, Unset, str] = UNSET,
    year_min: Union[None, Unset, str] = UNSET,
    year_max: Union[None, Unset, str] = UNSET,
    runtime_max: Union[None, Unset, str] = UNSET,
) -> Optional[Union[HTTPValidationError, MovieRead]]:
    """Get Pick

    Args:
        mood (Union[None, Unset, str]): Desired mood name
        genre (Union[None, Unset, str]): Restrict to this genre
        year_min (Union[None, Unset, str]):
        year_max (Union[None, Unset, str]):
        runtime_max (Union[None, Unset, str]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Union[HTTPValidationError, MovieRead]
    """

    return (
        await asyncio_detailed(
            client=client,
            mood=mood,
            genre=genre,
            year_min=year_min,
            year_max=year_max,
            runtime_max=runtime_max,
        )
    ).parsed
