def test_refresh_collection_health_recommendation(client, admin_headers) -> None:
    response = client.post(
        "/api/collection-health/recommendation/refresh",
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert "recommendation" in payload
    assert isinstance(payload["recommendation"], str)
    assert payload["recommendation"].strip()


def test_refresh_collection_health_allows_admin_profile_session(
    client, monkeypatch, login_profile
) -> None:
    monkeypatch.setattr(
        "api.routers.collection_health.get_collection_recommendation",
        lambda db, force=False: "session recommendation",
    )
    login_profile(1)

    missing_origin = client.post("/api/collection-health/recommendation/refresh")
    response = client.post(
        "/api/collection-health/recommendation/refresh",
        headers={"Origin": "http://testserver"},
    )

    assert missing_origin.status_code == 403
    assert response.status_code == 200
    assert response.json() == {"recommendation": "session recommendation"}
