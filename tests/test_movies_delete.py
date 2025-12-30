from fastapi.testclient import TestClient


def test_delete_movie_removes_detail(client: TestClient, admin_headers: dict[str, str]) -> None:
    resp = client.delete("/movies/1", headers=admin_headers)
    assert resp.status_code == 204

    detail = client.get("/movies/1/detail")
    assert detail.status_code == 404
