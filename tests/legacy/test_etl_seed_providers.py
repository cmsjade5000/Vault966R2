from legacy.etl.etl_seed import _split_providers, merge_where_to_watch


def test_split_providers_with_dict_payload():
    payload = {
        "US": {
            "flatrate": [
                {"provider_name": "Netflix"},
                {"provider_name": "Hulu"},
            ],
            "rent": [
                {"provider_name": "Vudu"},
            ],
        }
    }

    assert _split_providers(payload) == ["Netflix", "Hulu", "Vudu"]


def test_merge_where_to_watch_with_dict_payload():
    existing_value = "Amazon Prime"
    new_value = {
        "flatrate": [
            {"provider_name": "Amazon Prime"},
            {"provider_name": "Peacock"},
        ],
        "rent": [
            {"provider_name": "Hulu"},
        ],
    }

    merged = merge_where_to_watch(existing_value, new_value)

    assert merged == "Amazon Prime; Peacock; Hulu"
