from fastapi.testclient import TestClient


def test_client_request_id_is_preserved(client: TestClient) -> None:
    request_id = "client-req_123.abc:trace"
    response = client.get("/does-not-exist", headers={"X-Request-ID": request_id})
    data = response.json()
    assert response.headers["X-Request-ID"] == request_id
    assert data["request_id"] == request_id


def test_invalid_client_request_id_is_replaced(client: TestClient) -> None:
    request_id = "bad request id"
    response = client.get("/does-not-exist", headers={"X-Request-ID": request_id})
    data = response.json()
    assert response.headers["X-Request-ID"] != request_id
    assert data["request_id"] == response.headers["X-Request-ID"]


def test_too_long_client_request_id_is_replaced(client: TestClient) -> None:
    request_id = "a" * 129
    response = client.get("/does-not-exist", headers={"X-Request-ID": request_id})
    data = response.json()
    assert response.headers["X-Request-ID"] != request_id
    assert data["request_id"] == response.headers["X-Request-ID"]


def test_error_response_includes_request_id_and_shape(client: TestClient) -> None:
    response = client.get("/movies/picks", params={"year_min": 2020, "year_max": 2000})
    assert response.status_code == 400
    data = response.json()
    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert data["request_id"] == request_id
    assert data["error_code"] == "http_error"
    assert isinstance(data["message"], str) and data["message"]


def test_not_found_has_structured_error(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    data = response.json()
    assert response.headers.get("X-Request-ID")
    assert data.get("error_code") == "http_error"
    assert isinstance(data.get("message"), str)
    assert data.get("request_id") == response.headers["X-Request-ID"]


def test_validation_error_shape(client: TestClient) -> None:
    response = client.get("/movies/picks", params={"runtime_max": "abc"})
    assert response.status_code == 422
    data = response.json()
    assert data.get("error_code") == "validation_error"
    assert data.get("request_id") == response.headers["X-Request-ID"]
    assert isinstance(data.get("message"), str) and data.get("message")
