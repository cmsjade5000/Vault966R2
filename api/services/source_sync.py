from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.models.movie import Genre, Movie, MovieIngestProvenance
from api.models.person import Person, Role, RoleType
from api.models.source_sync import (
    OwnedMovieCopy,
    SourceFieldDecision,
    SourceMovieRow,
    SourceReconciliationMatch,
    SourceSnapshot,
)
from core.genres import split_and_normalize
from core.vault_ids import next_vault_id

MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_SOURCE_ROWS = 5000
REQUIRED_FIELDS = ("title", "time", "director", "year")
FIELD_ALIASES = {
    "title": ("Title", "Name"),
    "time": ("Time", "Total Time"),
    "director": ("Director", "Artist"),
    "year": ("Year",),
    "genre": ("Genre",),
    "content_rating": ("Content Rating",),
    "release_date": ("Release Date",),
    "hd": ("HD",),
}
IDENTITY_FIELDS = ("title", "year", "runtime", "director")
SPACE_RE = re.compile(r"\s+")
DIRECTOR_SPLIT_RE = re.compile(r"\s*(?:&|;|\band\b)\s*", re.IGNORECASE)


class SourceSyncError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSourceRow:
    row_number: int
    title: str
    normalized_title: str
    runtime: int | None
    director: str | None
    normalized_directors: tuple[str, ...]
    year: int | None
    genre: str | None
    content_rating: str | None
    release_date: str | None
    hd: bool | None
    duplicate_group: str | None
    raw_data: dict[str, str]


@dataclass(frozen=True)
class SourceFieldConflict:
    field_name: str
    label: str
    source_value: str
    vault_value: str
    research: bool = False


@dataclass(frozen=True)
class SourceReviewItem:
    source_row: SourceMovieRow
    match: SourceReconciliationMatch
    movie: Movie | None
    conflicts: tuple[SourceFieldConflict, ...]
    candidate_movies: tuple[Movie, ...] = ()


def clean_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def limited_text(
    value: object,
    *,
    field_name: str,
    max_length: int,
    row_number: int,
) -> str | None:
    text = clean_text(value)
    if text is not None and len(text) > max_length:
        raise SourceSyncError(f"Row {row_number} {field_name} exceeds {max_length} characters")
    return text


def normalize_title(value: object) -> str:
    text = str(value or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return SPACE_RE.sub(" ", text).strip()


def parse_directors(value: object) -> tuple[str, ...]:
    text = clean_text(value)
    if text is None or text.casefold() in {"unknown", "not found", "n/a"}:
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for part in DIRECTOR_SPLIT_RE.split(text):
        name = SPACE_RE.sub(" ", part).strip()
        key = normalize_title(name)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return tuple(names)


def normalized_directors(value: object) -> tuple[str, ...]:
    return tuple(sorted(normalize_title(name) for name in parse_directors(value)))


def parse_runtime(value: object) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    if text.isdigit():
        runtime = int(text)
    else:
        parts = text.split(":")
        if len(parts) not in {2, 3}:
            raise SourceSyncError(f"Invalid runtime '{text}'")
        try:
            numbers = [float(part) for part in parts]
        except ValueError as exc:
            raise SourceSyncError(f"Invalid runtime '{text}'") from exc
        if len(numbers) == 3:
            hours, minutes, seconds = numbers
        else:
            hours = 0
            minutes, seconds = numbers
        runtime = round(hours * 60 + minutes + seconds / 60)
    if runtime <= 0 or runtime > 1000:
        raise SourceSyncError(f"Runtime '{text}' is outside the accepted range")
    return runtime


def parse_year(value: object) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    if not text.isdigit():
        raise SourceSyncError(f"Invalid year '{text}'")
    year = int(text)
    if year < 1888 or year > 2100:
        raise SourceSyncError(f"Year '{text}' is outside the accepted range")
    return year


def parse_hd(value: object) -> bool | None:
    text = clean_text(value)
    if text is None:
        return None
    lowered = text.casefold()
    if lowered in {"1", "true", "yes", "y", "hd"}:
        return True
    if lowered in {"0", "false", "no", "n", "sd"}:
        return False
    raise SourceSyncError(f"Invalid HD value '{text}'")


def _find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    for index, row in enumerate(rows):
        names = {str(value or "").strip(): position for position, value in enumerate(row)}
        resolved: dict[str, int] = {}
        for field, aliases in FIELD_ALIASES.items():
            for alias in aliases:
                if alias in names:
                    resolved[field] = names[alias]
                    break
        if all(field in resolved for field in REQUIRED_FIELDS):
            return index, resolved
    raise SourceSyncError(
        "CSV must contain Title, Time, Director, and Year columns "
        "(Numbers exports using Name, Total Time, and Artist are also accepted)."
    )


def parse_source_csv(content: bytes) -> tuple[str, list[ParsedSourceRow]]:
    if not content:
        raise SourceSyncError("The uploaded CSV is empty")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceSyncError("The uploaded CSV is larger than 5 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceSyncError("The CSV must use UTF-8 encoding") from exc

    try:
        raw_rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise SourceSyncError(f"CSV parsing failed: {exc}") from exc
    header_index, columns = _find_header(raw_rows)
    data_rows = [row for row in raw_rows[header_index + 1 :] if any(cell.strip() for cell in row)]
    if not data_rows:
        raise SourceSyncError("The CSV contains no movie rows")
    if len(data_rows) > MAX_SOURCE_ROWS:
        raise SourceSyncError(f"The CSV contains more than {MAX_SOURCE_ROWS} rows")

    parsed: list[ParsedSourceRow] = []
    duplicate_keys: list[str] = []
    provisional: list[dict] = []
    for offset, row in enumerate(data_rows, start=header_index + 2):

        def value(field: str) -> str:
            column = columns.get(field)
            if column is None or column >= len(row):
                return ""
            return row[column].strip()

        title = limited_text(
            value("title"),
            field_name="title",
            max_length=300,
            row_number=offset,
        )
        if title is None:
            raise SourceSyncError(f"Row {offset} has no title")
        runtime = parse_runtime(value("time"))
        year = parse_year(value("year"))
        director = limited_text(
            value("director"),
            field_name="director",
            max_length=500,
            row_number=offset,
        )
        directors = normalized_directors(director)
        raw_data = {
            label: value(field)
            for field, label in (
                ("title", "Title"),
                ("time", "Time"),
                ("director", "Director"),
                ("year", "Year"),
                ("genre", "Genre"),
                ("content_rating", "Content Rating"),
                ("release_date", "Release Date"),
                ("hd", "HD"),
            )
        }
        duplicate_key = hashlib.sha256(
            "\x1f".join(
                [
                    normalize_title(title),
                    str(year or ""),
                    str(runtime or ""),
                    "|".join(directors),
                ]
            ).encode("utf-8")
        ).hexdigest()
        duplicate_keys.append(duplicate_key)
        provisional.append(
            {
                "row_number": offset,
                "title": title,
                "normalized_title": normalize_title(title),
                "runtime": runtime,
                "director": director,
                "normalized_directors": directors,
                "year": year,
                "genre": limited_text(
                    value("genre"),
                    field_name="genre",
                    max_length=200,
                    row_number=offset,
                ),
                "content_rating": limited_text(
                    value("content_rating"),
                    field_name="content rating",
                    max_length=100,
                    row_number=offset,
                ),
                "release_date": limited_text(
                    value("release_date"),
                    field_name="release date",
                    max_length=80,
                    row_number=offset,
                ),
                "hd": parse_hd(value("hd")),
                "raw_data": raw_data,
                "duplicate_key": duplicate_key,
            }
        )

    duplicate_counts = Counter(duplicate_keys)
    for row in provisional:
        parsed.append(
            ParsedSourceRow(
                row_number=row["row_number"],
                title=row["title"],
                normalized_title=row["normalized_title"],
                runtime=row["runtime"],
                director=row["director"],
                normalized_directors=row["normalized_directors"],
                year=row["year"],
                genre=row["genre"],
                content_rating=row["content_rating"],
                release_date=row["release_date"],
                hd=row["hd"],
                duplicate_group=(
                    row["duplicate_key"] if duplicate_counts[row["duplicate_key"]] > 1 else None
                ),
                raw_data=row["raw_data"],
            )
        )
    return text, parsed


def create_draft_snapshot(
    db: Session,
    *,
    filename: str,
    content: bytes,
    profile_id: int | None,
) -> SourceSnapshot:
    file_sha = hashlib.sha256(content).hexdigest()
    existing = db.query(SourceSnapshot).filter(SourceSnapshot.file_sha256 == file_sha).one_or_none()
    if existing is not None:
        raise SourceSyncError(
            f"This exact source file was already uploaded as snapshot #{existing.id}."
        )
    raw_csv, rows = parse_source_csv(content)
    snapshot = SourceSnapshot(
        filename=filename or "collection.csv",
        file_sha256=file_sha,
        raw_csv=raw_csv,
        row_count=len(rows),
        status="draft",
        uploaded_by_profile_id=profile_id,
    )
    db.add(snapshot)
    db.flush()
    db.add_all(
        [
            SourceMovieRow(
                snapshot_id=snapshot.id,
                row_number=row.row_number,
                title=row.title,
                normalized_title=row.normalized_title,
                runtime=row.runtime,
                director=row.director,
                normalized_directors=list(row.normalized_directors) or None,
                year=row.year,
                genre=row.genre,
                content_rating=row.content_rating,
                release_date=row.release_date,
                hd=row.hd,
                duplicate_group=row.duplicate_group,
                raw_data=row.raw_data,
            )
            for row in rows
        ]
    )
    db.commit()
    db.refresh(snapshot)
    return snapshot


def _movie_directors(movie: Movie) -> tuple[str, ...]:
    names = [
        role.person.name
        for role in movie.roles
        if role.role_type == RoleType.DIRECTOR and role.person is not None
    ]
    return tuple(sorted(normalize_title(name) for name in names if normalize_title(name)))


def _create_owned_copy(db: Session, row: SourceMovieRow, movie_id: int) -> None:
    existing = db.query(OwnedMovieCopy).filter(OwnedMovieCopy.source_row_id == row.id).one_or_none()
    if existing is None:
        db.add(
            OwnedMovieCopy(
                movie_id=movie_id,
                snapshot_id=row.snapshot_id,
                source_row_id=row.id,
                hd=row.hd,
                source_title=row.title,
                source_year=row.year,
            )
        )


def reconcile_snapshot(db: Session, snapshot: SourceSnapshot) -> dict[str, int]:
    if snapshot.status == "active":
        return snapshot_summary(db, snapshot)
    if snapshot.status != "draft":
        raise SourceSyncError("Only draft snapshots can be confirmed")

    db.query(SourceSnapshot).filter(SourceSnapshot.status == "active").filter(
        SourceSnapshot.id != snapshot.id
    ).update({"status": "superseded"}, synchronize_session=False)

    movies = (
        db.query(Movie)
        .options(selectinload(Movie.roles).selectinload(Role.person))
        .order_by(Movie.id.asc())
        .all()
    )
    by_title: dict[str, list[Movie]] = defaultdict(list)
    by_title_year: dict[tuple[str, int | None], list[Movie]] = defaultdict(list)
    for movie in movies:
        title_key = normalize_title(movie.title)
        by_title[title_key].append(movie)
        by_title_year[(title_key, movie.year)].append(movie)

    seen_duplicate_groups: set[str] = set()
    for row in snapshot.rows:
        exact = by_title_year.get((row.normalized_title, row.year), [])
        title_matches = by_title.get(row.normalized_title, [])
        match_type = "source_only"
        movie_id = None
        confidence = 0.0
        candidate_ids: list[int] = []

        if row.duplicate_group and row.duplicate_group in seen_duplicate_groups:
            candidate_ids = [movie.id for movie in exact or title_matches]
            movie_id = candidate_ids[0] if len(candidate_ids) == 1 else None
            match_type = "duplicate"
            confidence = 0.5
        elif len(exact) == 1:
            movie_id = exact[0].id
            candidate_ids = [movie_id]
            match_type = "exact"
            confidence = 1.0
        elif len(title_matches) == 1:
            candidate = title_matches[0]
            director_match = bool(row.normalized_directors) and bool(
                set(row.normalized_directors) & set(_movie_directors(candidate))
            )
            runtime_match = (
                row.runtime is not None
                and candidate.runtime is not None
                and abs(row.runtime - candidate.runtime) <= 3
            )
            candidate_ids = [candidate.id]
            if director_match or runtime_match:
                movie_id = candidate.id
                match_type = "likely"
                confidence = 0.8 if director_match and runtime_match else 0.65
            else:
                match_type = "ambiguous"
                confidence = 0.4
        elif title_matches:
            candidate_ids = [movie.id for movie in title_matches]
            match_type = "ambiguous"
            confidence = 0.25

        if row.duplicate_group:
            seen_duplicate_groups.add(row.duplicate_group)
        match = SourceReconciliationMatch(
            source_row_id=row.id,
            movie_id=movie_id,
            match_type=match_type,
            confidence=confidence,
            candidate_movie_ids=candidate_ids or None,
        )
        db.add(match)
        if match_type in {"exact", "likely"} and movie_id is not None:
            _create_owned_copy(db, row, movie_id)

    snapshot.status = "active"
    snapshot.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return snapshot_summary(db, snapshot)


def latest_active_snapshot(db: Session) -> SourceSnapshot | None:
    return (
        db.query(SourceSnapshot)
        .filter(SourceSnapshot.status == "active")
        .order_by(SourceSnapshot.confirmed_at.desc(), SourceSnapshot.id.desc())
        .first()
    )


def snapshot_summary(db: Session, snapshot: SourceSnapshot | None) -> dict[str, int]:
    if snapshot is None:
        return {
            "rows": 0,
            "matched": 0,
            "conflicts": 0,
            "ambiguous": 0,
            "duplicates": 0,
            "source_only": 0,
        }
    counts = dict(
        db.query(SourceReconciliationMatch.match_type, func.count())
        .join(SourceMovieRow, SourceMovieRow.id == SourceReconciliationMatch.source_row_id)
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .group_by(SourceReconciliationMatch.match_type)
        .all()
    )
    conflicts = len(get_source_review_queue(db, snapshot=snapshot, include_unmatched=False))
    return {
        "rows": snapshot.row_count,
        "matched": counts.get("exact", 0) + counts.get("likely", 0),
        "conflicts": conflicts,
        "ambiguous": counts.get("ambiguous", 0),
        "duplicates": counts.get("duplicate", 0),
        "source_only": counts.get("source_only", 0),
    }


def _display_value(value: object) -> str:
    if value is None or value == "":
        return "Missing"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) or "Missing"
    return str(value)


def _field_values(row: SourceMovieRow, movie: Movie) -> dict[str, tuple[object, object]]:
    source_directors = tuple(parse_directors(row.director))
    vault_directors = tuple(
        role.person.name
        for role in movie.roles
        if role.role_type == RoleType.DIRECTOR and role.person is not None
    )
    return {
        "title": (row.title, movie.title),
        "year": (row.year, movie.year),
        "runtime": (row.runtime, movie.runtime),
        "director": (source_directors, vault_directors),
    }


def _values_differ(field_name: str, source_value: object, vault_value: object) -> bool:
    if field_name == "title":
        return normalize_title(source_value) != normalize_title(vault_value)
    if field_name == "director":

        def director_set(value: object) -> set[str]:
            if isinstance(value, (list, tuple, set)):
                return {
                    normalize_title(item)
                    for item in value
                    if normalize_title(item)
                    and normalize_title(item) not in {"unknown", "not found", "n a"}
                }
            return set(normalized_directors(value))

        source_set = director_set(source_value)
        vault_set = director_set(vault_value)
        if not source_set:
            return False
        return source_set != vault_set
    if field_name == "runtime":
        if source_value is None:
            return False
        if vault_value is None:
            return True
        return abs(int(source_value) - int(vault_value)) > 3
    return source_value is not None and source_value != vault_value


def source_row_conflicts(
    db: Session, row: SourceMovieRow, movie: Movie
) -> tuple[SourceFieldConflict, ...]:
    decisions: dict[str, SourceFieldDecision] = {}
    for decision in (
        db.query(SourceFieldDecision)
        .filter(SourceFieldDecision.source_row_id == row.id)
        .order_by(SourceFieldDecision.decided_at.desc(), SourceFieldDecision.id.desc())
        .all()
    ):
        decisions.setdefault(decision.field_name, decision)
    labels = {
        "title": "Title",
        "year": "Year",
        "runtime": "Runtime",
        "director": "Director",
    }
    conflicts: list[SourceFieldConflict] = []
    for field_name, (source_value, vault_value) in _field_values(row, movie).items():
        if not _values_differ(field_name, source_value, vault_value):
            continue
        decision = decisions.get(field_name)
        if decision is not None and decision.decision in {"use_source", "keep_vault"}:
            continue
        conflicts.append(
            SourceFieldConflict(
                field_name=field_name,
                label=labels[field_name],
                source_value=_display_value(source_value),
                vault_value=_display_value(vault_value),
                research=decision is not None and decision.decision == "needs_research",
            )
        )
    return tuple(conflicts)


def get_source_review_queue(
    db: Session,
    *,
    snapshot: SourceSnapshot | None = None,
    include_unmatched: bool = True,
) -> list[SourceReviewItem]:
    snapshot = snapshot or latest_active_snapshot(db)
    if snapshot is None:
        return []
    rows = (
        db.query(SourceMovieRow)
        .options(
            selectinload(SourceMovieRow.match)
            .selectinload(SourceReconciliationMatch.movie)
            .selectinload(Movie.roles)
            .selectinload(Role.person)
        )
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .order_by(SourceMovieRow.row_number.asc())
        .all()
    )
    movie_by_id = {
        movie.id: movie
        for movie in db.query(Movie)
        .options(selectinload(Movie.roles).selectinload(Role.person))
        .all()
    }
    items: list[SourceReviewItem] = []
    for row in rows:
        match = row.match
        if match is None:
            continue
        candidate_movies = tuple(
            movie_by_id[movie_id]
            for movie_id in (match.candidate_movie_ids or [])
            if movie_id in movie_by_id
        )
        if match.match_type in {"exact", "likely", "manual"} and match.movie is not None:
            conflicts = source_row_conflicts(db, row, match.movie)
            if conflicts:
                items.append(
                    SourceReviewItem(
                        source_row=row,
                        match=match,
                        movie=match.movie,
                        conflicts=conflicts,
                    )
                )
        elif include_unmatched and match.match_type in {
            "ambiguous",
            "duplicate",
            "source_only",
        }:
            items.append(
                SourceReviewItem(
                    source_row=row,
                    match=match,
                    movie=match.movie,
                    conflicts=(),
                    candidate_movies=candidate_movies,
                )
            )
    priority = {"ambiguous": 0, "duplicate": 1, "source_only": 2}
    items.sort(
        key=lambda item: (
            0 if item.conflicts else 1,
            priority.get(item.match.match_type, 9),
            item.source_row.row_number,
        )
    )
    return items


def _set_directors(db: Session, movie: Movie, director_value: str | None) -> None:
    db.query(Role).filter(Role.movie_id == movie.id).filter(
        Role.role_type == RoleType.DIRECTOR
    ).delete(synchronize_session=False)
    for index, name in enumerate(parse_directors(director_value)):
        person = (
            db.query(Person)
            .filter(func.lower(Person.name) == name.casefold())
            .order_by(Person.id.asc())
            .first()
        )
        if person is None:
            person = Person(name=name)
            db.add(person)
            db.flush()
        db.add(
            Role(
                movie_id=movie.id,
                person_id=person.id,
                role_type=RoleType.DIRECTOR,
                billing_order=index,
            )
        )


def decide_source_field(
    db: Session,
    *,
    row_id: int,
    field_name: str,
    decision: str,
    profile_id: int | None,
) -> SourceFieldDecision:
    if field_name not in IDENTITY_FIELDS:
        raise SourceSyncError("Unsupported source field")
    if decision not in {"use_source", "keep_vault", "needs_research"}:
        raise SourceSyncError("Unsupported review decision")
    row = db.get(SourceMovieRow, row_id)
    if row is None or row.match is None or row.match.movie_id is None:
        raise SourceSyncError("Source row is not matched to a Vault entry")
    movie = db.get(Movie, row.match.movie_id)
    if movie is None:
        raise SourceSyncError("Matched Vault entry no longer exists")

    source_value, vault_value = _field_values(row, movie)[field_name]
    selected_value = vault_value
    if decision == "use_source":
        selected_value = source_value
        if field_name == "title":
            movie.title = row.title
        elif field_name == "year":
            movie.year = row.year
        elif field_name == "runtime":
            movie.runtime = row.runtime
        elif field_name == "director":
            _set_directors(db, movie, row.director)

    record = SourceFieldDecision(
        source_row_id=row.id,
        movie_id=movie.id,
        field_name=field_name,
    )
    db.add(record)
    record.previous_value = _display_value(vault_value)
    record.source_value = _display_value(source_value)
    record.selected_value = _display_value(selected_value)
    record.decision = decision
    record.decided_by_profile_id = profile_id
    record.decided_at = datetime.now(timezone.utc)
    record.resolved_at = None if decision == "needs_research" else datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


def assign_source_row_match(
    db: Session, *, row_id: int, movie_id: int, profile_id: int | None
) -> None:
    row = db.get(SourceMovieRow, row_id)
    movie = db.get(Movie, movie_id)
    if row is None or row.match is None or movie is None:
        raise SourceSyncError("Source row or Vault entry was not found")
    row.match.movie_id = movie.id
    row.match.match_type = "manual"
    row.match.confidence = 1.0
    row.match.candidate_movie_ids = [movie.id]
    row.match.resolved_at = datetime.now(timezone.utc)
    _create_owned_copy(db, row, movie.id)
    db.commit()


def create_movie_from_source_row(db: Session, *, row_id: int, profile_id: int | None) -> Movie:
    row = db.get(SourceMovieRow, row_id)
    if row is None or row.match is None:
        raise SourceSyncError("Source row was not found")
    if row.match.match_type not in {"source_only", "duplicate"}:
        raise SourceSyncError("Only source-only or duplicate rows can create a movie")
    movie = Movie(
        vault_id=next_vault_id(db),
        title=row.title,
        year=row.year,
        runtime=row.runtime,
    )
    if row.genre:
        genres = []
        for name in split_and_normalize(row.genre):
            genre = db.query(Genre).filter(func.lower(Genre.name) == name.casefold()).one_or_none()
            if genre is None:
                genre = Genre(name=name)
                db.add(genre)
            genres.append(genre)
        movie.genres = genres
    db.add(movie)
    db.flush()
    _set_directors(db, movie, row.director)
    db.add(
        MovieIngestProvenance(
            movie_id=movie.id,
            provider="collection_source",
            provider_id=str(row.id),
            payload_sha=row.snapshot.file_sha256,
            notes=f"Created from source snapshot #{row.snapshot_id}, row {row.row_number}",
        )
    )
    row.match.movie_id = movie.id
    row.match.match_type = "manual"
    row.match.confidence = 1.0
    row.match.candidate_movie_ids = [movie.id]
    row.match.resolved_at = datetime.now(timezone.utc)
    _create_owned_copy(db, row, movie.id)
    db.commit()
    db.refresh(movie)
    return movie


def dismiss_duplicate(db: Session, *, row_id: int) -> None:
    row = db.get(SourceMovieRow, row_id)
    if row is None or row.match is None or row.match.match_type != "duplicate":
        raise SourceSyncError("Duplicate source row was not found")
    row.match.match_type = "duplicate_ignored"
    row.match.resolved_at = datetime.now(timezone.utc)
    db.commit()


def source_provenance_for_movie(db: Session, movie_id: int) -> dict:
    latest_copy = (
        db.query(OwnedMovieCopy)
        .join(SourceSnapshot, SourceSnapshot.id == OwnedMovieCopy.snapshot_id)
        .filter(OwnedMovieCopy.movie_id == movie_id)
        .filter(SourceSnapshot.status == "active")
        .order_by(SourceSnapshot.confirmed_at.desc(), OwnedMovieCopy.id.desc())
        .first()
    )
    decisions = (
        db.query(SourceFieldDecision)
        .filter(SourceFieldDecision.movie_id == movie_id)
        .order_by(SourceFieldDecision.decided_at.desc())
        .limit(8)
        .all()
    )
    return {
        "latest_copy": latest_copy,
        "decisions": decisions,
    }


__all__ = [
    "SourceFieldConflict",
    "SourceReviewItem",
    "SourceSyncError",
    "assign_source_row_match",
    "create_draft_snapshot",
    "create_movie_from_source_row",
    "decide_source_field",
    "dismiss_duplicate",
    "get_source_review_queue",
    "latest_active_snapshot",
    "parse_source_csv",
    "reconcile_snapshot",
    "snapshot_summary",
    "source_provenance_for_movie",
]
