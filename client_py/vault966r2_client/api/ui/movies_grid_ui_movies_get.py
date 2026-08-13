from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    q: None | str | Unset = UNSET,
    genres: None | str | Unset = UNSET,
    moods: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
    page: int | Unset = 1,
    order_by: str | Unset = "title_asc",
    view: str | Unset = "grid",
    preset: None | str | Unset = UNSET,
    semantic: None | str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_q: None | str | Unset
    if isinstance(q, Unset):
        json_q = UNSET
    else:
        json_q = q
    params["q"] = json_q

    json_genres: None | str | Unset
    if isinstance(genres, Unset):
        json_genres = UNSET
    else:
        json_genres = genres
    params["genres"] = json_genres

    json_moods: None | str | Unset
    if isinstance(moods, Unset):
        json_moods = UNSET
    else:
        json_moods = moods
    params["moods"] = json_moods

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

    params["page"] = page

    params["order_by"] = order_by

    params["view"] = view

    json_preset: None | str | Unset
    if isinstance(preset, Unset):
        json_preset = UNSET
    else:
        json_preset = preset
    params["preset"] = json_preset

    json_semantic: None | str | Unset
    if isinstance(semantic, Unset):
        json_semantic = UNSET
    else:
        json_semantic = semantic
    params["semantic"] = json_semantic

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/ui/movies",
        "params": params,
    }

    return _kwargs


def _parse_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> ErrorResponse | str | None:
    if response.status_code == 200:
        response_200 = response.text
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


def _build_response(*, client: AuthenticatedClient | Client, response: httpx.Response) -> Response[ErrorResponse | str]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    genres: None | str | Unset = UNSET,
    moods: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
    page: int | Unset = 1,
    order_by: str | Unset = "title_asc",
    view: str | Unset = "grid",
    preset: None | str | Unset = UNSET,
    semantic: None | str | Unset = UNSET,
) -> Response[ErrorResponse | str]:
    """Movies Grid

    Args:
        q (None | str | Unset):
        genres (None | str | Unset):
        moods (None | str | Unset):
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):
        page (int | Unset):  Default: 1.
        order_by (str | Unset):  Default: 'title_asc'.
        view (str | Unset):  Default: 'grid'.
        preset (None | str | Unset):
        semantic (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | str]
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
        view=view,
        preset=preset,
        semantic=semantic,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    genres: None | str | Unset = UNSET,
    moods: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
    page: int | Unset = 1,
    order_by: str | Unset = "title_asc",
    view: str | Unset = "grid",
    preset: None | str | Unset = UNSET,
    semantic: None | str | Unset = UNSET,
) -> ErrorResponse | str | None:
    """Movies Grid

    Args:
        q (None | str | Unset):
        genres (None | str | Unset):
        moods (None | str | Unset):
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):
        page (int | Unset):  Default: 1.
        order_by (str | Unset):  Default: 'title_asc'.
        view (str | Unset):  Default: 'grid'.
        preset (None | str | Unset):
        semantic (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | str
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
        view=view,
        preset=preset,
        semantic=semantic,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    genres: None | str | Unset = UNSET,
    moods: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
    page: int | Unset = 1,
    order_by: str | Unset = "title_asc",
    view: str | Unset = "grid",
    preset: None | str | Unset = UNSET,
    semantic: None | str | Unset = UNSET,
) -> Response[ErrorResponse | str]:
    """Movies Grid

    Args:
        q (None | str | Unset):
        genres (None | str | Unset):
        moods (None | str | Unset):
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):
        page (int | Unset):  Default: 1.
        order_by (str | Unset):  Default: 'title_asc'.
        view (str | Unset):  Default: 'grid'.
        preset (None | str | Unset):
        semantic (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | str]
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
        view=view,
        preset=preset,
        semantic=semantic,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    q: None | str | Unset = UNSET,
    genres: None | str | Unset = UNSET,
    moods: None | str | Unset = UNSET,
    year_min: None | str | Unset = UNSET,
    year_max: None | str | Unset = UNSET,
    runtime_max: None | str | Unset = UNSET,
    page: int | Unset = 1,
    order_by: str | Unset = "title_asc",
    view: str | Unset = "grid",
    preset: None | str | Unset = UNSET,
    semantic: None | str | Unset = UNSET,
) -> ErrorResponse | str | None:
    """Movies Grid

    Args:
        q (None | str | Unset):
        genres (None | str | Unset):
        moods (None | str | Unset):
        year_min (None | str | Unset):
        year_max (None | str | Unset):
        runtime_max (None | str | Unset):
        page (int | Unset):  Default: 1.
        order_by (str | Unset):  Default: 'title_asc'.
        view (str | Unset):  Default: 'grid'.
        preset (None | str | Unset):
        semantic (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | str
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
            view=view,
            preset=preset,
            semantic=semantic,
        )
    ).parsed
