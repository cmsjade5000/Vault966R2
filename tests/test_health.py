from api.config import settings


def test_health_is_public_and_omits_database_details(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app_name": settings.app_name}
