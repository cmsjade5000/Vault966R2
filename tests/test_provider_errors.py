import httpx

from api.utils.provider_errors import run_provider_cli, sanitize_provider_diagnostic


def test_sanitizer_redacts_provider_query_and_header_aliases() -> None:
    sentinel = "SENTINEL_ALTERNATE_PROVIDER_SECRET"
    diagnostic = (
        f"GET https://provider.test/items?TMDB_API_KEY={sentinel}&query=Alien; "
        f"headers={{'X-Api-Key': '{sentinel}', 'Authorization': 'Basic {sentinel}'}}"
    )

    sanitized = sanitize_provider_diagnostic(diagnostic)

    assert sentinel not in sanitized
    assert sanitized.count("[REDACTED]") == 3
    assert "query=Alien" in sanitized
    assert "GET https://provider.test/items" in sanitized


def test_provider_cli_reports_sanitized_useful_http_error(capsys) -> None:
    sentinel = "SENTINEL_SCRIPT_PROVIDER_SECRET"
    request = httpx.Request(
        "GET",
        "https://provider.test/items",
        params={"api_key": sentinel, "movie_id": "42"},
    )
    response = httpx.Response(503, request=request)

    def fail() -> int:
        response.raise_for_status()
        return 0

    exit_code = run_provider_cli(fail)
    stderr = capsys.readouterr().err

    assert exit_code == 1
    assert sentinel not in stderr
    assert "[REDACTED]" in stderr
    assert "503 Service Unavailable" in stderr
    assert "movie_id=42" in stderr
