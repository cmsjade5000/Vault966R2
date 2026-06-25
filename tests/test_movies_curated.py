from api.services.movies_curated import get_collection_health, get_curated_collections


def test_curated_collections_populate(db_session) -> None:
    collections = get_curated_collections(db_session, items_per_collection=4)
    assert isinstance(collections, list)
    assert all(section.movies for section in collections)


def test_collection_health_metrics(db_session) -> None:
    health = get_collection_health(db_session)
    assert health.missing_runtime >= 0
    assert health.missing_plot >= 0
    assert health.missing_poster >= 0


def test_collection_health_recommendation_fallback(db_session) -> None:
    health = get_collection_health(db_session)
    assert isinstance(health.recommendation, str)
    assert health.recommendation.strip()
