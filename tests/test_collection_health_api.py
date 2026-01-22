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
