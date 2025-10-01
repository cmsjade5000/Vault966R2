"""Tests for provider normalization helpers in legacy.etl.etl_seed."""

from legacy.etl.etl_seed import _split_providers, merge_where_to_watch


def test_merge_where_to_watch_with_dict_payloads():
    existing_payload = {
        "us": {
            "stream": ["Netflix", "Hulu"],
        },
        "providers": {"Disney+": None},
    }
    new_payload = {
        "ca": {
            "rent": {"apple": "Apple TV"},
        },
        "other": "HBO Max",
    }

    existing_providers = _split_providers(existing_payload)
    new_providers = _split_providers(new_payload)

    assert existing_providers == ["Netflix", "Hulu", "Disney+"]
    assert new_providers == ["Apple TV", "HBO Max"]

    merged = merge_where_to_watch(existing_payload, new_payload)

    assert merged == "Netflix; Hulu; Disney+; Apple TV; HBO Max"
