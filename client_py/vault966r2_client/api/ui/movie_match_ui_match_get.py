from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    answers: None | str | Unset = UNSET,
    reroll: int | Unset = 0,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_answers: None | str | Unset
    if isinstance(answers, Unset):
        json_answers = UNSET
    else:
        json_answers = answers
    params["answers"] = json_answers

    params["reroll"] = reroll

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/ui/match",
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
    answers: None | str | Unset = UNSET,
    reroll: int | Unset = 0,
) -> Response[ErrorResponse | str]:
    """Movie Match

    Args:
        answers (None | str | Unset):
        reroll (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | str]
    """

    kwargs = _get_kwargs(
        answers=answers,
        reroll=reroll,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    answers: None | str | Unset = UNSET,
    reroll: int | Unset = 0,
) -> ErrorResponse | str | None:
    """Movie Match

    Args:
        answers (None | str | Unset):
        reroll (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | str
    """

    return sync_detailed(
        client=client,
        answers=answers,
        reroll=reroll,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    answers: None | str | Unset = UNSET,
    reroll: int | Unset = 0,
) -> Response[ErrorResponse | str]:
    """Movie Match

    Args:
        answers (None | str | Unset):
        reroll (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | str]
    """

    kwargs = _get_kwargs(
        answers=answers,
        reroll=reroll,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    answers: None | str | Unset = UNSET,
    reroll: int | Unset = 0,
) -> ErrorResponse | str | None:
    """Movie Match

    Args:
        answers (None | str | Unset):
        reroll (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | str
    """

    return (
        await asyncio_detailed(
            client=client,
            answers=answers,
            reroll=reroll,
        )
    ).parsed
