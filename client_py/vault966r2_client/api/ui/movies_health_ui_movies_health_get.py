from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    view: None | str | Unset = UNSET,
    row: int | None | Unset = UNSET,
    movie: int | None | Unset = UNSET,
    undo_decision: int | None | Unset = UNSET,
    flag_reason: None | str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_view: None | str | Unset
    if isinstance(view, Unset):
        json_view = UNSET
    else:
        json_view = view
    params["view"] = json_view

    json_row: int | None | Unset
    if isinstance(row, Unset):
        json_row = UNSET
    else:
        json_row = row
    params["row"] = json_row

    json_movie: int | None | Unset
    if isinstance(movie, Unset):
        json_movie = UNSET
    else:
        json_movie = movie
    params["movie"] = json_movie

    json_undo_decision: int | None | Unset
    if isinstance(undo_decision, Unset):
        json_undo_decision = UNSET
    else:
        json_undo_decision = undo_decision
    params["undo_decision"] = json_undo_decision

    json_flag_reason: None | str | Unset
    if isinstance(flag_reason, Unset):
        json_flag_reason = UNSET
    else:
        json_flag_reason = flag_reason
    params["flag_reason"] = json_flag_reason

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/ui/movies/health",
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
    *,
    client: AuthenticatedClient | Client,
    view: None | str | Unset = UNSET,
    row: int | None | Unset = UNSET,
    movie: int | None | Unset = UNSET,
    undo_decision: int | None | Unset = UNSET,
    flag_reason: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | str]:
    """Movies Health

    Args:
        view (None | str | Unset):
        row (int | None | Unset):
        movie (int | None | Unset):
        undo_decision (int | None | Unset):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | str]
    """

    kwargs = _get_kwargs(
        view=view,
        row=row,
        movie=movie,
        undo_decision=undo_decision,
        flag_reason=flag_reason,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    view: None | str | Unset = UNSET,
    row: int | None | Unset = UNSET,
    movie: int | None | Unset = UNSET,
    undo_decision: int | None | Unset = UNSET,
    flag_reason: None | str | Unset = UNSET,
) -> HTTPValidationError | str | None:
    """Movies Health

    Args:
        view (None | str | Unset):
        row (int | None | Unset):
        movie (int | None | Unset):
        undo_decision (int | None | Unset):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | str
    """

    return sync_detailed(
        client=client,
        view=view,
        row=row,
        movie=movie,
        undo_decision=undo_decision,
        flag_reason=flag_reason,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    view: None | str | Unset = UNSET,
    row: int | None | Unset = UNSET,
    movie: int | None | Unset = UNSET,
    undo_decision: int | None | Unset = UNSET,
    flag_reason: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | str]:
    """Movies Health

    Args:
        view (None | str | Unset):
        row (int | None | Unset):
        movie (int | None | Unset):
        undo_decision (int | None | Unset):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | str]
    """

    kwargs = _get_kwargs(
        view=view,
        row=row,
        movie=movie,
        undo_decision=undo_decision,
        flag_reason=flag_reason,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    view: None | str | Unset = UNSET,
    row: int | None | Unset = UNSET,
    movie: int | None | Unset = UNSET,
    undo_decision: int | None | Unset = UNSET,
    flag_reason: None | str | Unset = UNSET,
) -> HTTPValidationError | str | None:
    """Movies Health

    Args:
        view (None | str | Unset):
        row (int | None | Unset):
        movie (int | None | Unset):
        undo_decision (int | None | Unset):
        flag_reason (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | str
    """

    return (
        await asyncio_detailed(
            client=client,
            view=view,
            row=row,
            movie=movie,
            undo_decision=undo_decision,
            flag_reason=flag_reason,
        )
    ).parsed
