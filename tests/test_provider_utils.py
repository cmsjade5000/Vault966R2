import pytest

from api.utils.providers import collect_provider_tokens, split_providers


def test_collect_provider_tokens_handles_nested_mapping():
    payload = {
        "US": {
            "flatrate": [
                {"provider_name": "Netflix", "logo_path": "/netflix"},
                {"provider_name": "Hulu", "provider_id": 15},
            ],
            "link": "https://example.com",
        },
        "metadata": {"last_updated": "2024-05-01"},
    }

    tokens = collect_provider_tokens(payload)
    assert tokens == ["Netflix", "Hulu"]


def test_collect_provider_tokens_falls_back_to_mapping_keys():
    payload = {"Netflix": True, "Hulu": False}

    tokens = collect_provider_tokens(payload)
    assert tokens == ["Netflix", "Hulu"]


def test_split_providers_preserves_existing_behavior():
    payload = ["Netflix", "netflix", "Hulu"]

    result = split_providers(payload)
    assert result == ["Netflix", "netflix", "Hulu"]


def test_split_providers_handles_mapping_payload():
    payload = {
        "US": {
            "flatrate": [
                {"provider_name": "Netflix"},
                {"provider_name": "Hulu"},
            ]
        }
    }

    result = split_providers(payload)
    assert result == ["Netflix", "Hulu"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        {"link": "https://example.com"},
        {"logo_path": "/images/netflix.png"},
        {"provider_id": 8},
    ],
)
def test_collect_provider_tokens_ignores_non_provider_values(value):
    assert collect_provider_tokens(value) == []
