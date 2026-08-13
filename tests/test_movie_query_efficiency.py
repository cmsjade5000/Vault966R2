from collections.abc import Callable
from typing import TypeVar

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from api.models.movie import Movie


T = TypeVar("T")


def _count_selects(db: Session, action: Callable[[], T]) -> tuple[T, int]:
    engine = db.get_bind()
    select_count = 0

    def count_selects(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        nonlocal select_count
        if statement.lstrip().lower().startswith("select"):
            select_count += 1

    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        result = action()
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)
    return result, select_count


def test_movie_list_query_count_stays_bounded_as_results_grow(
    client: TestClient,
    db_session: Session,
) -> None:
    baseline, baseline_selects = _count_selects(db_session, lambda: client.get("/movies/"))
    assert baseline.status_code == 200
    baseline_size = len(baseline.json())

    added_count = 12
    db_session.add_all(
        Movie(title=f"Query Growth Movie {index:02d}") for index in range(added_count)
    )
    db_session.commit()

    expanded, expanded_selects = _count_selects(db_session, lambda: client.get("/movies/"))
    assert expanded.status_code == 200
    assert len(expanded.json()) == baseline_size + added_count
    assert expanded_selects <= baseline_selects + 2


def test_watchlist_query_count_stays_bounded_as_results_grow(
    client: TestClient,
    db_session: Session,
) -> None:
    movie_ids = [
        movie_id for (movie_id,) in db_session.query(Movie.id).order_by(Movie.id).limit(11).all()
    ]
    assert len(movie_ids) == 11

    response = client.post(f"/movies/{movie_ids[0]}/watchlist")
    assert response.status_code == 200
    baseline, baseline_selects = _count_selects(db_session, lambda: client.get("/ui/watchlist"))
    assert baseline.status_code == 200
    assert "<strong data-watchlist-total>1</strong> saved" in baseline.text

    for movie_id in movie_ids[1:]:
        response = client.post(f"/movies/{movie_id}/watchlist")
        assert response.status_code == 200

    expanded, expanded_selects = _count_selects(
        db_session,
        lambda: client.get("/ui/watchlist"),
    )
    assert expanded.status_code == 200
    assert "<strong data-watchlist-total>11</strong> saved" in expanded.text
    assert expanded_selects <= baseline_selects + 2
