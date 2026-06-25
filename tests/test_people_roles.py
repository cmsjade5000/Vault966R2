from fastapi.testclient import TestClient


def _create_person(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    tmdb_id: int = 0,
) -> int:
    response = client.post(
        "/people/",
        json={
            "name": name,
            "tmdb_id": tmdb_id,
            "imdb_id": f"nm{tmdb_id:07d}" if tmdb_id else None,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _get_movie_id_by_title(client: TestClient, title: str) -> int:
    response = client.get("/movies/search", params={"q": title})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    for item in payload["items"]:
        if item["title"] == title:
            return item["id"]
    raise AssertionError(f"Movie titled {title} not found in search results")


def test_create_person_and_list(client: TestClient, admin_headers: dict[str, str]) -> None:
    _create_person(client, admin_headers, name="Harrison Ford", tmdb_id=3)

    list_response = client.get("/people/", params={"page": 1, "page_size": 10})
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["items"][0]["name"] == "Harrison Ford"


def test_people_pagination(client: TestClient, admin_headers: dict[str, str]) -> None:
    for idx in range(30):
        _create_person(client, admin_headers, name=f"Person {idx:02d}")

    response = client.get("/people/", params={"page": 2, "page_size": 10})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 30
    assert payload["page"] == 2
    assert len(payload["items"]) == 10


def test_attach_role_to_movie(client: TestClient, admin_headers: dict[str, str]) -> None:
    person_id = _create_person(client, admin_headers, name="Carrie-Anne Moss", tmdb_id=297)
    movie_id = _get_movie_id_by_title(client, "The Matrix")

    attach_response = client.post(
        f"/movies/{movie_id}/roles",
        json={
            "role_type": "ACTOR",
            "person_id": person_id,
            "character_name": "Trinity",
            "billing_order": 2,
        },
        headers=admin_headers,
    )
    assert attach_response.status_code == 201
    payload = attach_response.json()
    assert payload["movie_id"] == movie_id
    assert payload["person_id"] == person_id
    assert payload["role_type"] == "ACTOR"
    assert payload["character_name"] == "Trinity"
    assert payload["billing_order"] == 2

    roles_response = client.get(f"/movies/{movie_id}/roles")
    assert roles_response.status_code == 200
    roles_payload = roles_response.json()
    assert len(roles_payload) == 1
    role_entry = roles_payload[0]
    assert role_entry["role_type"] == "ACTOR"
    assert role_entry["person"]["id"] == person_id
    assert role_entry["person"]["name"] == "Carrie-Anne Moss"
