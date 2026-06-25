from api.models.movie import Movie
from api.services.collection_integrity import (
    count_structural_issues,
    get_structural_issues,
)
from api.services.movies_curated import get_collection_health


def test_collection_health_uses_shared_structural_integrity(db_session) -> None:
    movie = db_session.query(Movie).order_by(Movie.id).first()
    movie.runtime = 0
    movie.year = 1800
    db_session.commit()

    issues = get_structural_issues(db_session)
    health = get_collection_health(db_session)

    assert movie.id in issues["invalid_runtimes"]
    assert movie.id in issues["invalid_years"]
    assert health.structural_issues == count_structural_issues(issues)
