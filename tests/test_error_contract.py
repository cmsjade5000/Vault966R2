import json
import re
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import ObservabilityMiddleware
from api.schemas.common import ErrorResponse
from client_py.vault966r2_client.api.collection_health import (
    update_report_api_collection_health_update_reports_task_get,
)
from client_py.vault966r2_client.api.movies import create_movie_movies_post
from client_py.vault966r2_client.api.ui import (
    download_new_additions_csv_ui_source_sync_snapshot_id_new_additions_csv_get,
    first_import_sample_csv_ui_first_import_sample_csv_get,
    first_import_sample_csv_ui_onboarding_import_sample_csv_get,
)
from client_py.vault966r2_client.client import Client as GeneratedClient
from client_py.vault966r2_client.models.error_response import (
    ErrorResponse as GeneratedErrorResponse,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
ERROR_KEYS = {"error_code", "message", "request_id"}
CSV_PATHS = (
    "/api/collection-health/update/reports/{task}",
    "/ui/first-import/sample.csv",
    "/ui/onboarding/import/sample.csv",
    "/ui/source-sync/{snapshot_id}/new-additions.csv",
)
CSV_OPERATION_IDS = (
    "update_report_api_collection_health_update_reports__task__get",
    "first_import_sample_csv_ui_first_import_sample_csv_get",
    "first_import_sample_csv_ui_onboarding_import_sample_csv_get",
    "download_new_additions_csv_ui_source_sync__snapshot_id__new_additions_csv_get",
)
CSV_CLIENT_OPERATIONS = (
    update_report_api_collection_health_update_reports_task_get,
    first_import_sample_csv_ui_first_import_sample_csv_get,
    first_import_sample_csv_ui_onboarding_import_sample_csv_get,
    download_new_additions_csv_ui_source_sync_snapshot_id_new_additions_csv_get,
)


def _assert_error_response(response, *, status_code: int, error_code: str) -> None:
    assert response.status_code == status_code
    assert set(response.json()) == ERROR_KEYS
    parsed = ErrorResponse.model_validate(response.json())
    assert parsed.error_code == error_code
    assert parsed.request_id == response.headers["X-Request-ID"]


def test_runtime_error_envelope_is_stable(client: TestClient) -> None:
    _assert_error_response(
        client.get("/movies/picks", params={"year_min": 2020, "year_max": 2000}),
        status_code=400,
        error_code="http_error",
    )
    _assert_error_response(
        client.get("/does-not-exist"),
        status_code=404,
        error_code="http_error",
    )
    _assert_error_response(
        client.get("/movies/picks", params={"runtime_max": "invalid"}),
        status_code=422,
        error_code="validation_error",
    )


def test_unhandled_error_uses_the_same_envelope() -> None:
    error_app = FastAPI()
    error_app.add_middleware(ObservabilityMiddleware)

    @error_app.get("/explode")
    def explode() -> None:
        raise RuntimeError("private diagnostic")

    with TestClient(error_app) as client:
        response = client.get("/explode")

    _assert_error_response(response, status_code=500, error_code="internal_error")
    assert response.json()["message"] == "Internal server error"
    assert "private diagnostic" not in response.text


def test_openapi_uses_error_response_for_documented_failures(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    error_schema = {"$ref": "#/components/schemas/ErrorResponse"}

    create_responses = schema["paths"]["/movies/"]["post"]["responses"]
    for status_code in (400, 401, 403, 404, 422, 429, 500, 502, 503):
        assert create_responses[str(status_code)]["content"]["application/json"]["schema"] == (
            error_schema
        )

    manual_add_responses = schema["paths"]["/ui/movies/manual-add"]["post"]["responses"]
    assert manual_add_responses["409"]["content"]["application/json"]["schema"] == error_schema
    assert manual_add_responses["422"]["content"]["application/json"]["schema"] == error_schema
    assert manual_add_responses["500"]["content"]["application/json"]["schema"] == error_schema

    readiness_responses = schema["paths"]["/readyz"]["get"]["responses"]
    assert readiness_responses["503"]["content"]["application/json"]["schema"] == error_schema
    assert "422" not in readiness_responses
    assert schema["paths"]["/login"]["post"]["responses"]["422"]["content"] == {
        "application/json": {"schema": error_schema}
    }
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_openapi_documents_csv_success_responses(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()

    for path in CSV_PATHS:
        success_response = schema["paths"][path]["get"]["responses"]["200"]
        assert success_response["content"] == {"text/csv": {"schema": {"type": "string"}}}


def test_python_client_parses_documented_error_responses() -> None:
    generated_client = GeneratedClient(base_url="https://vault.invalid")
    body = {
        "error_code": "example_error",
        "message": "Example failure",
        "request_id": "request-123",
    }

    for status_code in (400, 401, 403, 404, 422, 429, 500, 502, 503):
        response = httpx.Response(
            status_code,
            json=body,
            request=httpx.Request("POST", "https://vault.invalid/movies/"),
        )
        parsed = create_movie_movies_post._parse_response(
            client=generated_client,
            response=response,
        )
        assert isinstance(parsed, GeneratedErrorResponse)
        assert parsed.to_dict() == body


def test_python_client_preserves_csv_success_responses() -> None:
    generated_client = GeneratedClient(base_url="https://vault.invalid")
    csv_body = "Title,Year\nAlien,1979\n"

    for operation in CSV_CLIENT_OPERATIONS:
        response = httpx.Response(
            200,
            text=csv_body,
            headers={"content-type": "text/csv; charset=utf-8"},
            request=httpx.Request("GET", "https://vault.invalid/example.csv"),
        )
        generated_response = operation._build_response(
            client=generated_client,
            response=response,
        )

        assert generated_response.parsed == csv_body
        assert generated_response.content == csv_body.encode()


def test_typescript_client_types_documented_error_responses() -> None:
    declarations = (ROOT_DIR / "client_ts" / "index.d.ts").read_text(encoding="utf-8")
    operation = declarations.split("create_movie_movies__post: {", maxsplit=1)[1].split(
        "get_double_feature_movies_double_feature_get: {",
        maxsplit=1,
    )[0]

    for status_code in (400, 401, 403, 404, 422, 429, 500, 502, 503):
        assert f"{status_code}: {{" in operation
    assert operation.count('"application/json": components["schemas"]["ErrorResponse"];') >= 9


def test_typescript_client_types_csv_success_responses() -> None:
    declarations = (ROOT_DIR / "client_ts" / "index.d.ts").read_text(encoding="utf-8")

    for operation_id in CSV_OPERATION_IDS:
        operation = re.search(
            rf"^    {re.escape(operation_id)}: \{{(?P<body>.*?)"
            rf"(?=^    [A-Za-z0-9_]+: \{{|^\}})",
            declarations,
            re.MULTILINE | re.DOTALL,
        )
        assert operation is not None, operation_id
        assert '"text/csv": string;' in operation.group("body")


def test_generated_clients_type_every_documented_json_error() -> None:
    schema = json.loads((ROOT_DIR / "openapi" / "openapi.json").read_text(encoding="utf-8"))
    python_api_root = ROOT_DIR / "client_py" / "vault966r2_client" / "api"
    declarations = (ROOT_DIR / "client_ts" / "index.d.ts").read_text(encoding="utf-8")

    documented_error_count = 0
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            error_statuses = []
            for status_code, response in operation.get("responses", {}).items():
                response_schema = (
                    response.get("content", {}).get("application/json", {}).get("schema", {})
                )
                if response_schema.get("$ref") == "#/components/schemas/ErrorResponse":
                    error_statuses.append(status_code)
            if not error_statuses:
                continue

            operation_id = operation["operationId"]
            python_filename = re.sub(r"_+", "_", operation_id) + ".py"
            python_matches = list(python_api_root.rglob(python_filename))
            assert len(python_matches) == 1, operation_id
            python_source = python_matches[0].read_text(encoding="utf-8")

            typescript_match = re.search(
                rf"^    {re.escape(operation_id)}: \{{(?P<body>.*?)(?=^    [A-Za-z0-9_]+: \{{|^\}})",
                declarations,
                re.MULTILINE | re.DOTALL,
            )
            assert typescript_match is not None, operation_id
            typescript_operation = typescript_match.group("body")

            for status_code in error_statuses:
                documented_error_count += 1
                python_branch = re.search(
                    rf"if response\.status_code == {status_code}:\s+"
                    rf"response_{status_code} = ErrorResponse\.from_dict\(response\.json\(\)\)\s+"
                    rf"return response_{status_code}",
                    python_source,
                )
                assert python_branch is not None, (operation_id, status_code)

                typescript_branch = re.search(
                    rf"^            {status_code}: \{{(?P<body>.*?)"
                    rf"(?=^            [1-5][0-9]{{2}}: \{{|^        \}};)",
                    typescript_operation,
                    re.MULTILINE | re.DOTALL,
                )
                assert typescript_branch is not None, (operation_id, status_code)
                typescript_body = typescript_branch.group("body")
                assert 'components["schemas"]["ErrorResponse"]' in typescript_body
                assert "never" not in typescript_body

    assert documented_error_count > 100
