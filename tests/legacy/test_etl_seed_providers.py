from legacy.etl.etl_seed import _split_providers


def test_split_providers_accepts_mapping_without_type_error():
    payload = {
        "results": {
            "US": {
                "flatrate": [
                    {"provider_name": "Netflix"},
                    {"provider_name": "Hulu"},
                ]
            }
        }
    }

    result = _split_providers(payload)

    assert result == ["Netflix", "Hulu"]


def test_split_providers_skips_nullish_entries_in_nested_collections():
    payload = {"providers": ["", None, "Prime Video"]}

    result = _split_providers(payload)

    assert result == ["Prime Video"]
