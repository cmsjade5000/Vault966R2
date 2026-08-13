from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Stable JSON error envelope returned by the application middleware."""

    error_code: str
    message: str
    request_id: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


def _error_response(description: str) -> dict[str, object]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ErrorResponse"},
            }
        },
    }


# Unhandled exceptions can occur on every path operation and are normalized by
# the outer observability middleware, including for server-rendered UI routes.
GLOBAL_SERVER_ERROR_RESPONSES = {
    500: _error_response("An unexpected server error occurred."),
}


def apply_error_response_openapi_contract(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace FastAPI's default 422 body with the runtime error envelope."""

    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components.setdefault("ErrorResponse", ErrorResponse.model_json_schema())

    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            validation_response = responses.get("422")
            if not isinstance(validation_response, dict):
                continue
            validation_schema = (
                validation_response.get("content", {}).get("application/json", {}).get("schema", {})
            )
            if validation_schema.get("$ref") != "#/components/schemas/HTTPValidationError":
                continue
            responses["422"] = _error_response("Request validation failed.")

    for (path, method), error_responses in UI_JSON_ERROR_RESPONSES.items():
        operation = schema.get("paths", {}).get(path, {}).get(method)
        if not isinstance(operation, dict):
            continue
        responses = operation.setdefault("responses", {})
        for status_code, response in error_responses.items():
            responses[str(status_code)] = response

    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)
    components.pop("ValidationErrorContext", None)
    return schema


# API routes are protected by authentication middleware and normalize their
# raised HTTP errors to the same JSON envelope. The middleware can reject any
# protected API operation before route dispatch with 401; route-specific maps
# below add only the other statuses each router actually emits.
API_AUTH_ERROR_RESPONSES = {
    401: _error_response("Authentication is required or invalid."),
}

ASSISTANT_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    400: _error_response("The request was rejected."),
}

MOVIE_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    400: _error_response("The request was rejected."),
    403: _error_response("The authenticated caller is not allowed to perform this action."),
    404: _error_response("The requested resource was not found."),
    429: _error_response("The request budget was exceeded."),
    502: _error_response("An upstream provider request failed."),
    503: _error_response("The requested capability is temporarily unavailable."),
}

PEOPLE_API_ERROR_RESPONSES = API_AUTH_ERROR_RESPONSES

FLICLIST_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    400: _error_response("The request was rejected."),
    404: _error_response("The requested resource was not found."),
}

PROFILE_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    400: _error_response("The request was rejected."),
    403: _error_response("The authenticated caller is not allowed to perform this action."),
}

AI_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    502: _error_response("An upstream provider request failed."),
    503: _error_response("The requested capability is temporarily unavailable."),
}

SEARCH_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    400: _error_response("The request was rejected."),
}

COLLECTION_HEALTH_API_ERROR_RESPONSES = {
    **API_AUTH_ERROR_RESPONSES,
    400: _error_response("The request was rejected."),
    403: _error_response("The authenticated caller is not allowed to perform this action."),
    404: _error_response("The requested resource was not found."),
    429: _error_response("The request budget was exceeded."),
}

CONFLICT_ERROR_RESPONSES = {
    409: _error_response("The request conflicts with the current resource state."),
}

UI_JSON_ERROR_RESPONSES = {
    ("/ui/movies/manual-add/preview", "post"): {
        404: _error_response("The requested movie could not be found."),
        409: CONFLICT_ERROR_RESPONSES[409],
        503: _error_response("Movie lookup is temporarily unavailable."),
    },
    ("/ui/movies/manual-add", "post"): CONFLICT_ERROR_RESPONSES,
    ("/ui/movies/health/review/{movie_id}/matches", "get"): {
        404: _error_response("No provider matches were found."),
        409: CONFLICT_ERROR_RESPONSES[409],
        502: _error_response("The upstream provider request failed."),
    },
    ("/ui/movies/health/review/{movie_id}/matches/apply", "post"): (CONFLICT_ERROR_RESPONSES),
}
