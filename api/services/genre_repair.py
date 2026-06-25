from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models.movie import Genre, Movie, MovieIngestProvenance
from api.models.source_sync import SourceMovieRow
from core.genres import split_and_normalize


@dataclass(frozen=True)
class GenreRepairResult:
    movies_scanned: int
    movies_repaired: int
    assignments_removed: int
    assignments_added: int
    orphan_genres_deleted: int


def repair_source_created_genres(db: Session) -> GenreRepairResult:
    provenance_rows = (
        db.query(MovieIngestProvenance)
        .filter(MovieIngestProvenance.provider == "collection_source")
        .all()
    )
    repaired = 0
    removed = 0
    added = 0

    for provenance in provenance_rows:
        if not provenance.provider_id or not provenance.provider_id.isdigit():
            continue
        source_row = db.get(SourceMovieRow, int(provenance.provider_id))
        movie = db.get(Movie, provenance.movie_id)
        if source_row is None or movie is None or not source_row.genre:
            continue

        expected_names = split_and_normalize(source_row.genre)
        current_names = [genre.name for genre in movie.genres]
        if current_names == expected_names:
            continue
        if current_names and not all(len(name.strip()) == 1 for name in current_names):
            continue

        genres: list[Genre] = []
        for name in expected_names:
            genre = db.query(Genre).filter(func.lower(Genre.name) == name.casefold()).one_or_none()
            if genre is None:
                genre = Genre(name=name)
                db.add(genre)
                db.flush()
            genres.append(genre)
        removed += len(movie.genres)
        added += len(genres)
        movie.genres = genres
        repaired += 1

    db.flush()
    orphan_genres = [
        genre
        for genre in db.query(Genre).all()
        if len((genre.name or "").strip()) == 1 and not genre.movies
    ]
    for genre in orphan_genres:
        db.delete(genre)
    db.commit()

    return GenreRepairResult(
        movies_scanned=len(provenance_rows),
        movies_repaired=repaired,
        assignments_removed=removed,
        assignments_added=added,
        orphan_genres_deleted=len(orphan_genres),
    )


__all__ = ["GenreRepairResult", "repair_source_created_genres"]
