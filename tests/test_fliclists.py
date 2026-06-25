from fastapi.testclient import TestClient


def test_fliclists_crud(client: TestClient, admin_headers: dict[str, str]):
    create_payload = {
        "name": "Sci-Fi Night",
        "filters": {
            "q": "",
            "genres": ["Sci-Fi"],
            "moods": [],
            "year_min": 1990,
            "year_max": None,
            "runtime_max": 150,
        },
    }

    create_resp = client.post("/fliclists/", json=create_payload, headers=admin_headers)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Sci-Fi Night"
    assert created["filters"]["genres"] == ["Sci-Fi"]

    list_resp = client.get("/fliclists/")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["name"] == "Sci-Fi Night" for item in items)

    preset_id = created["id"]
    delete_resp = client.delete(f"/fliclists/{preset_id}", headers=admin_headers)
    assert delete_resp.status_code == 204


def test_fliclist_name_is_trimmed(client: TestClient, admin_headers: dict[str, str]):
    create_payload = {
        "name": "  Cozy Evening  ",
        "filters": {"q": "", "genres": [], "moods": [], "year_min": None},
    }

    create_resp = client.post("/fliclists/", json=create_payload, headers=admin_headers)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Cozy Evening"

    # cleanup
    client.delete(f"/fliclists/{created['id']}", headers=admin_headers)


def test_fliclist_blank_name_rejected(client: TestClient, admin_headers: dict[str, str]):
    create_payload = {
        "name": "   ",
        "filters": {"q": "", "genres": [], "moods": []},
    }

    create_resp = client.post("/fliclists/", json=create_payload, headers=admin_headers)
    assert create_resp.status_code == 422
