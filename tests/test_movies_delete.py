from fastapi.testclient import TestClient

from api.models.movie import Movie
from api.models.vault_id import RetiredVaultId


def test_delete_movie_removes_detail_and_retires_vault_id(
    client: TestClient,
    db_session,
    admin_headers: dict[str, str],
) -> None:
    movie = db_session.get(Movie, 1)
    movie.vault_id = "V0001"
    db_session.commit()

    resp = client.delete("/movies/1", headers=admin_headers)
    assert resp.status_code == 204

    detail = client.get("/movies/1/detail")
    assert detail.status_code == 404
    retired = db_session.get(RetiredVaultId, "V0001")
    assert retired is not None
    assert retired.source == "movie_delete"
    assert retired.deleted_movie_id == 1


def test_delete_movie_allows_admin_profile_session(client: TestClient, login_profile) -> None:
    login_profile(1)

    missing_origin = client.delete("/movies/1")
    resp = client.delete("/movies/1", headers={"Origin": "http://testserver"})

    assert missing_origin.status_code == 403
    assert resp.status_code == 204
