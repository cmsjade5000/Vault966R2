from api.models.movie import Movie, MovieIngestProvenance
from api.models.movie_flag import MovieFlag
from api.models.movie_repair import MovieIdentityRepair
from api.routers.ui import review


def _candidate(*, tmdb_id: int = 9001, imdb_id: str = "tt9001001") -> dict:
    return {
        "title": "Blade Runner",
        "year": 1982,
        "runtime": 118,
        "synopsis": "A selected provider synopsis.",
        "overview": "A selected provider synopsis.",
        "tmdb_id": tmdb_id,
        "imdb_id": imdb_id,
        "poster_url": "https://image.tmdb.org/t/p/w342/poster.jpg",
        "backdrop_url": "https://image.tmdb.org/t/p/w780/backdrop.jpg",
        "genres": ["Science Fiction", "Thriller"],
        "source": "tmdb",
        "where_to_watch": ["Max"],
        "keywords": ["replicant"],
        "certificate": "R",
        "match_confidence": 1.0,
        "imdb_rating": 8.1,
        "imdb_votes": 1000,
        "rt_score": 89,
        "tmdb_payload_sha": "tmdb-sha",
        "omdb_payload_sha": "omdb-sha",
    }


def test_flag_match_search_returns_manual_options(
    client,
    db_session,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.flag = MovieFlag(reason="Human review", notes="No source IDs")
    db_session.commit()
    tmdb_calls = []
    omdb_calls = []

    def fake_tmdb_lookup(title, year, limit):
        tmdb_calls.append((title, year, limit))
        return [_candidate()]

    def fake_omdb_lookup(title, year, limit):
        omdb_calls.append((title, year, limit))
        return [
            {
                **_candidate(imdb_id="tt9001002"),
                "source": "omdb",
                "tmdb_id": None,
            }
        ]

    monkeypatch.setattr(
        review,
        "lookup_movie_candidates",
        fake_tmdb_lookup,
    )
    monkeypatch.setattr(
        review,
        "lookup_omdb_candidates",
        fake_omdb_lookup,
    )

    response = client.get(
        f"/ui/movies/health/review/{movie.id}/matches",
        params={"title": "Blade Runner (1982)", "year": 1982},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["tmdb_id"] == 9001
    assert payload["items"][0]["imdb_id"] == "tt9001001"
    assert any(item["source"] == "omdb" for item in payload["items"])
    assert tmdb_calls == [("Blade Runner", None, 12)]
    assert omdb_calls == [("Blade Runner", None, 10)]
    assert payload["items"][0]["standardized_title"] == "Blade Runner"


def test_apply_flag_match_updates_metadata_and_resolves_flag(
    client,
    db_session,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.imdb_id = None
    movie.tmdb_id = None
    movie.flag = MovieFlag(reason="Human review", notes="No source IDs")
    original_title = movie.title
    original_vault_id = movie.vault_id
    db_session.commit()
    monkeypatch.setattr(
        review,
        "lookup_movie_candidates",
        lambda title, year, limit: [_candidate()],
    )
    monkeypatch.setattr(
        review,
        "lookup_omdb_candidates",
        lambda title, year, limit: [],
    )

    response = client.post(
        f"/ui/movies/health/review/{movie.id}/matches/apply",
        json={
            "title": "Blade Runner (1982)",
            "year": 1982,
            "source": "tmdb",
            "tmdb_id": 9001,
        },
    )

    assert response.status_code == 200
    assert response.json()["flag_resolved"] is True
    db_session.expire_all()
    updated = db_session.get(Movie, movie.id)
    assert updated.vault_id == original_vault_id
    assert updated.title == original_title
    assert updated.year == 1982
    assert updated.runtime == 118
    assert updated.imdb_id == "tt9001001"
    assert updated.tmdb_id == 9001
    assert updated.poster_url.endswith("/poster.jpg")
    assert updated.flag is None
    assert {genre.name for genre in updated.genres} == {
        "Science Fiction",
        "Thriller",
    }
    provenance = (
        db_session.query(MovieIngestProvenance)
        .filter(MovieIngestProvenance.movie_id == movie.id)
        .all()
    )
    assert {item.provider for item in provenance} == {"tmdb", "omdb"}
    repair = db_session.query(MovieIdentityRepair).one()
    assert repair.movie_id == movie.id
    assert repair.search_title == "Blade Runner (1982)"
    assert repair.standardized_title == "Blade Runner"
    assert repair.selected_title == "Blade Runner"
    assert repair.selected_tmdb_id == 9001
    assert repair.before_values["vault_id"] == original_vault_id
    assert repair.before_values["imdb_id"] is None
    assert repair.after_values["imdb_id"] == "tt9001001"
    assert repair.after_values["vault_id"] == original_vault_id


def test_apply_flag_match_rejects_duplicate_external_id(
    client,
    db_session,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.imdb_id = None
    movie.tmdb_id = None
    movie.flag = MovieFlag(reason="Human review", notes="No source IDs")
    duplicate = db_session.get(Movie, 2)
    duplicate_tmdb_id = duplicate.tmdb_id
    duplicate_imdb_id = duplicate.imdb_id
    db_session.commit()
    monkeypatch.setattr(
        review,
        "lookup_movie_candidates",
        lambda title, year, limit: [
            _candidate(
                tmdb_id=duplicate_tmdb_id,
                imdb_id=duplicate_imdb_id,
            )
        ],
    )
    monkeypatch.setattr(
        review,
        "lookup_omdb_candidates",
        lambda title, year, limit: [],
    )

    response = client.post(
        f"/ui/movies/health/review/{movie.id}/matches/apply",
        json={
            "title": "Blade Runner",
            "year": 1982,
            "source": "tmdb",
            "tmdb_id": duplicate_tmdb_id,
        },
    )

    assert response.status_code == 409
    assert "already assigned" in response.json()["message"]
    db_session.expire_all()
    assert db_session.get(Movie, movie.id).flag is not None


def test_apply_omdb_only_match_resolves_flag(
    client,
    db_session,
    monkeypatch,
) -> None:
    movie = db_session.get(Movie, 1)
    movie.imdb_id = None
    movie.tmdb_id = None
    movie.flag = MovieFlag(reason="Human review", notes="No source IDs")
    db_session.commit()
    omdb_candidate = {
        **_candidate(imdb_id="tt9001002"),
        "source": "omdb",
        "tmdb_id": None,
    }
    monkeypatch.setattr(
        review,
        "lookup_movie_candidates",
        lambda title, year, limit: [],
    )
    monkeypatch.setattr(
        review,
        "lookup_omdb_candidates",
        lambda title, year, limit: [omdb_candidate],
    )

    response = client.post(
        f"/ui/movies/health/review/{movie.id}/matches/apply",
        json={
            "title": "Blade Runner",
            "year": 1982,
            "source": "omdb",
            "imdb_id": "tt9001002",
        },
    )

    assert response.status_code == 200
    db_session.expire_all()
    updated = db_session.get(Movie, movie.id)
    assert updated.imdb_id == "tt9001002"
    assert updated.tmdb_id is None
    assert updated.flag is None


def test_apply_flag_match_rejects_unexpected_input(client, db_session) -> None:
    movie = db_session.get(Movie, 1)
    movie.flag = MovieFlag(reason="Human review", notes="No source IDs")
    db_session.commit()

    response = client.post(
        f"/ui/movies/health/review/{movie.id}/matches/apply",
        json={
            "title": "Blade Runner",
            "year": 1982,
            "source": "tmdb",
            "tmdb_id": 9001,
            "unexpected": "value",
        },
    )

    assert response.status_code == 422
