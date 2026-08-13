from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.flag_movie_for_review_ui_movies_movie_id_review_flag_post_response_flag_movie_for_review_ui_movies_movie_id_review_flag_post import (
    FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost,
)
from ...types import Response


def _get_kwargs(
    movie_id: int,
) -> dict[str, Any]:
    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/ui/movies/{movie_id}/review-flag".format(
            movie_id=quote(str(movie_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    ErrorResponse
    | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
    | None
):
    if response.status_code == 200:
        response_200 = FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost.from_dict(
            response.json()
        )

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


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[
    ErrorResponse
    | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
]:
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
) -> Response[
    ErrorResponse
    | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
]:
    """Flag Movie For Review

    Args:
        movie_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ErrorResponse
    | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
    | None
):
    """Flag Movie For Review

    Args:
        movie_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
    """

    return sync_detailed(
        movie_id=movie_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[
    ErrorResponse
    | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
]:
    """Flag Movie For Review

    Args:
        movie_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost]
    """

    kwargs = _get_kwargs(
        movie_id=movie_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    movie_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> (
    ErrorResponse
    | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
    | None
):
    """Flag Movie For Review

    Args:
        movie_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | FlagMovieForReviewUiMoviesMovieIdReviewFlagPostResponseFlagMovieForReviewUiMoviesMovieIdReviewFlagPost
    """

    return (
        await asyncio_detailed(
            movie_id=movie_id,
            client=client,
        )
    ).parsed
