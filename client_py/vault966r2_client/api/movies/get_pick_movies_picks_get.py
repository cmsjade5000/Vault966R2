from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.movie_read import MovieRead
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    mood: None | str | Unset = UNSET,
    genre: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_mood: None | str | Unset
    if isinstance(mood, Unset):
        json_mood = UNSET
    else:
        json_mood = mood
    params["mood"] = json_mood

    json_genre: None | str | Unset
    if isinstance(genre, Unset):
        json_genre = UNSET
    else:
        json_genre = genre
    params["genre"] = json_genre

    json_year_min: None | str | Unset
    if isinstance(year_min, Unset):
        json_year_min = UNSET
    else:
        json_year_min = year_min
    params["year_min"] = json_year_min

    json_year_max: None | str | Unset
    if isinstance(year_max, Unset):
        json_year_max = UNSET
    else:
        json_year_max = year_max
    params["year_max"] = json_year_max

    json_runtime_max: None | str | Unset
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
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | MovieRead | None:
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
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | MovieRead]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    mood: None | str | Unset = UNSET,
    genre: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | MovieRead]:
    """Get Pick

    Args:
        mood (None | str | Unset): Desired mood name
        genre (None | str | Unset): Restrict to this genre
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MovieRead]
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
    client: AuthenticatedClient | Client,
    mood: None | str | Unset = UNSET,
    genre: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
) -> HTTPValidationError | MovieRead | None:
    """Get Pick

    Args:
        mood (None | str | Unset): Desired mood name
        genre (None | str | Unset): Restrict to this genre
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MovieRead
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
    client: AuthenticatedClient | Client,
    mood: None | str | Unset = UNSET,
    genre: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | MovieRead]:
    """Get Pick

    Args:
        mood (None | str | Unset): Desired mood name
        genre (None | str | Unset): Restrict to this genre
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MovieRead]
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
    client: AuthenticatedClient | Client,
    mood: None | str | Unset = UNSET,
    genre: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
) -> HTTPValidationError | MovieRead | None:
    """Get Pick

    Args:
        mood (None | str | Unset): Desired mood name
        genre (None | str | Unset): Restrict to this genre
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MovieRead
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
