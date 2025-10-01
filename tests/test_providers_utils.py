from api.utils.providers import merge_providers, split_providers


def test_merge_providers_handles_nested_mappings():
    data = {
        "results": {
            "US": {
                "flatrate": [
                    {"provider_name": "Netflix"},
                    {"provider_name": "Hulu"},
                ],
                "buy": [
                    {"provider_name": "Amazon Video"},
                    {"provider_name": "Apple TV"},
                ],
            },
            "CA": {
                "flatrate": [
                    {"provider_name": "Crave"},
                ]
            },
        }
    }

    merged = merge_providers(data)

    assert merged == ["Netflix", "Hulu", "Amazon Video", "Apple TV", "Crave"]


def test_split_providers_handles_mapping_values():
    value = {
        "flatrate": [
            {"provider_name": "Peacock"},
            {"provider_name": "Paramount+"},
        ],
        "rent": [
            {"provider_name": "Amazon Video"},
            {"provider_name": "Apple TV"},
        ],
    }

    assert split_providers(value) == [
        "Peacock",
        "Paramount+",
        "Amazon Video",
        "Apple TV",
    ]
