from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from xml.etree import ElementTree

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
from api.services.movie_lookup import (
    MovieLookupError,
    MovieLookupNotFound,
    MovieLookupUnavailable,
    lookup_movie_candidates,
    standardize_title_for_identity_search,
)
from api.services.movie_review import apply_title_year_authority
from core.movie_metadata import MovieMetadata
from core.genres import split_and_normalize
from core.vault_ids import next_vault_id

MAX_SOURCE_BYTES = 5 * 1024 * 1024
MAX_SOURCE_ROWS = 5000
REQUIRED_FIELDS = ("title", "time", "director", "year")
FIELD_ALIASES = {
    "title": ("Title", "Name", "Movie", "Movie Title", "Film", "Film Title"),
    "time": ("Time", "Total Time", "Runtime", "Run Time", "Duration", "Minutes", "Runtime Min"),
    "director": ("Director", "Directors", "Director(s)", "Artist"),
    "year": ("Year", "Release Year", "Movie Year"),
    "genre": ("Genre", "Genres"),
    "content_rating": ("Content Rating", "Rating", "Rated", "Certificate"),
    "release_date": ("Release Date", "Released", "Date"),
    "hd": ("HD", "High Definition", "Quality"),
}
IDENTITY_FIELDS = ("title", "year", "runtime", "director")
SPACE_RE = re.compile(r"\s+")
DIRECTOR_SPLIT_RE = re.compile(r"\s*(?:,|&|;|\band\b)\s*", re.IGNORECASE)
IMDB_ID_RE = re.compile(r"^tt[0-9]{7,10}$")
TRAILING_YEAR_RE = re.compile(r"\s*\((?:18|19|20)\d{2}\)\s*$")
EDITION_SUFFIX_RE = re.compile(
    r"\s*(?:\(|[-:])\s*(?:unrated|extended(?: edition| cut)?|director'?s cut|"
    r"special edition|theatrical cut|restored edition)\)?\s*$",
    re.IGNORECASE,
)
EDITION_PAREN_RE = re.compile(
    r"\s*\((?=[^)]*(?:unrated|extended|director'?s cut|special edition|"
    r"theatrical cut|restored edition))[^)]*\)\s*$",
    re.IGNORECASE,
)
UNDO_WINDOW = timedelta(minutes=10)


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
class ResearchLink:
    label: str
    url: str
    provider: str
    link_type: str


@dataclass(frozen=True)
class ResearchLinkSet:
    current: tuple[ResearchLink, ...]
    searches: tuple[ResearchLink, ...]
    search_title: str


@dataclass(frozen=True)
class SourceReviewItem:
    source_row: SourceMovieRow
    match: SourceReconciliationMatch
    movie: Movie | None
    conflicts: tuple[SourceFieldConflict, ...]
    candidate_movies: tuple[Movie, ...] = ()
    research_links: ResearchLinkSet | None = None
    candidate_research_links: dict[int, ResearchLinkSet] | None = None


@dataclass(frozen=True)
class BulkSourceDecisionResult:
    snapshot_id: int
    movie_count: int
    field_count: int
    skipped_field_count: int


@dataclass(frozen=True)
class FirstImportDecision:
    row: SourceMovieRow
    bucket: str
    reason: str
    candidate: dict | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class FirstImportAnalysis:
    snapshot_id: int
    auto_create: tuple[FirstImportDecision, ...]
    needs_review: tuple[FirstImportDecision, ...]
    duplicate_conflict: tuple[FirstImportDecision, ...]
    failed_lookup: tuple[FirstImportDecision, ...]

    @property
    def total_rows(self) -> int:
        return (
            len(self.auto_create)
            + len(self.needs_review)
            + len(self.duplicate_conflict)
            + len(self.failed_lookup)
        )


@dataclass(frozen=True)
class FirstImportApplyResult:
    snapshot_id: int
    created_count: int
    review_count: int
    duplicate_conflict_count: int
    failed_lookup_count: int
    created_movie_ids: tuple[int, ...]


@dataclass(frozen=True)
class FirstImportReport:
    snapshot: SourceSnapshot
    created_count: int
    review_count: int
    duplicate_conflict_count: int
    source_only_count: int

    @property
    def remaining_count(self) -> int:
        return self.review_count + self.duplicate_conflict_count + self.source_only_count


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


def clean_research_title(value: object) -> str:
    title = clean_text(value) or ""
    title = TRAILING_YEAR_RE.sub("", title)
    title = EDITION_PAREN_RE.sub("", title)
    title = EDITION_SUFFIX_RE.sub("", title)
    return SPACE_RE.sub(" ", title).strip()[:200]


def _valid_imdb_id(value: object) -> str | None:
    text = clean_text(value)
    if text and IMDB_ID_RE.fullmatch(text):
        return text
    return None


def _valid_tmdb_id(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if 0 < number <= 2_147_483_647:
        return number
    return None


def build_research_links(
    *,
    source_title: str,
    source_year: int | None,
    source_director: str | None = None,
    movie: Movie | None = None,
) -> ResearchLinkSet:
    search_title = clean_research_title(source_title) or source_title[:200]
    query_parts = [search_title]
    if source_year:
        query_parts.append(str(source_year))
    director_names = parse_directors(source_director)
    if director_names:
        query_parts.append(" and ".join(director_names)[:100])
    query = " ".join(query_parts)[:320]

    current: list[ResearchLink] = []
    tmdb_id = _valid_tmdb_id(movie.tmdb_id if movie else None)
    if tmdb_id is not None:
        current.append(
            ResearchLink(
                label="Open current TMDB",
                url=f"https://www.themoviedb.org/movie/{tmdb_id}",
                provider="tmdb",
                link_type="current",
            )
        )
    imdb_id = _valid_imdb_id(movie.imdb_id if movie else None)
    if imdb_id is not None:
        current.append(
            ResearchLink(
                label="Open current IMDb",
                url=f"https://www.imdb.com/title/{imdb_id}/",
                provider="imdb",
                link_type="current",
            )
        )

    searches = (
        ResearchLink(
            label="Search TMDB",
            url="https://www.themoviedb.org/search/movie?" + urlencode({"query": query}),
            provider="tmdb",
            link_type="search",
        ),
        ResearchLink(
            label="Search IMDb",
            url="https://www.imdb.com/find/?" + urlencode({"q": query, "s": "tt", "ttype": "ft"}),
            provider="imdb",
            link_type="search",
        ),
    )
    return ResearchLinkSet(
        current=tuple(current),
        searches=searches,
        search_title=search_title,
    )


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


def _metadata_genres(db: Session, names: list[str]) -> list[Genre]:
    genres: list[Genre] = []
    for name in split_and_normalize(names):
        genre = db.query(Genre).filter(func.lower(Genre.name) == name.casefold()).one_or_none()
        if genre is None:
            genre = Genre(name=name)
            db.add(genre)
        genres.append(genre)
    return genres


def _standard_title_key(value: object) -> str:
    return normalize_title(standardize_title_for_identity_search(str(value or "")))


def _existing_title_year(db: Session, title: str, year: int | None) -> Movie | None:
    candidates = db.query(Movie).filter(Movie.year == year).all()
    title_key = normalize_title(title)
    return next((movie for movie in candidates if normalize_title(movie.title) == title_key), None)


def _external_id_owner(
    db: Session,
    *,
    tmdb_id: int | None,
    imdb_id: str | None,
) -> Movie | None:
    if tmdb_id is not None:
        owner = db.query(Movie).filter(Movie.tmdb_id == tmdb_id).one_or_none()
        if owner is not None:
            return owner
    if imdb_id:
        owner = db.query(Movie).filter(Movie.imdb_id == imdb_id).one_or_none()
        if owner is not None:
            return owner
    return None


def parse_runtime(value: object) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    lowered = text.casefold()
    minute_match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:m|min|mins|minute|minutes)", lowered)
    hour_minute_match = re.fullmatch(
        r"(?:(\d+(?:\.\d+)?)\s*h(?:ours?)?)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in(?:ute)?s?)?)?",
        lowered,
    )
    if minute_match:
        runtime = round(float(minute_match.group(1)))
    elif hour_minute_match and any(hour_minute_match.groups()):
        hours = float(hour_minute_match.group(1) or 0)
        minutes = float(hour_minute_match.group(2) or 0)
        runtime = round(hours * 60 + minutes)
    if text.isdigit():
        runtime = int(text)
    elif "runtime" not in locals():
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
    if re.fullmatch(r"\d{4}\.0+", text):
        text = text.split(".", 1)[0]
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


def _header_key(value: object) -> str:
    text = str(value or "").replace("\ufeff", "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return SPACE_RE.sub(" ", text).strip()


def _find_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    alias_lookup = {
        field: {_header_key(alias) for alias in aliases} for field, aliases in FIELD_ALIASES.items()
    }
    for index, row in enumerate(rows):
        names = {
            _header_key(value): position for position, value in enumerate(row) if _header_key(value)
        }
        resolved: dict[str, int] = {}
        for field, aliases in alias_lookup.items():
            for alias in aliases:
                if alias and alias in names:
                    resolved[field] = names[alias]
                    break
        if all(field in resolved for field in REQUIRED_FIELDS):
            return index, resolved
    raise SourceSyncError(
        "Upload must contain title, runtime, director, and year columns. "
        "Common headers such as Name, Movie Title, Total Time, Runtime, Artist, "
        "Director, Release Year, and Year are accepted."
    )


def _parse_source_rows(raw_rows: list[list[str]]) -> list[ParsedSourceRow]:
    header_index, columns = _find_header(raw_rows)
    data_rows = [row for row in raw_rows[header_index + 1 :] if any(cell.strip() for cell in row)]
    if not data_rows:
        raise SourceSyncError("The upload contains no movie rows")
    if len(data_rows) > MAX_SOURCE_ROWS:
        raise SourceSyncError(f"The upload contains more than {MAX_SOURCE_ROWS} rows")

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
    return parsed


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
    return text, _parse_source_rows(raw_rows)


def _xlsx_column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha())
    if not letters:
        return 0
    index = 0
    for char in letters.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _xlsx_text(element: ElementTree.Element) -> str:
    return "".join(element.itertext())


def _xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    except ElementTree.ParseError as exc:
        raise SourceSyncError("XLSX shared strings could not be read") from exc
    return [_xlsx_text(item) for item in root.findall(".//{*}si")]


def _xlsx_first_sheet_path(workbook: zipfile.ZipFile) -> str:
    try:
        workbook_root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
        rels_root = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    except (KeyError, ElementTree.ParseError) as exc:
        raise SourceSyncError("XLSX workbook metadata could not be read") from exc

    first_sheet = workbook_root.find(".//{*}sheet")
    relationship_id = (
        first_sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if first_sheet is not None
        else None
    )
    if relationship_id is None:
        raise SourceSyncError("XLSX workbook has no worksheets")

    for relationship in rels_root.findall(".//{*}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return "xl/" + target.lstrip("/")
    raise SourceSyncError("XLSX first worksheet could not be resolved")


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(".//{*}t")
        return _xlsx_text(inline) if inline is not None else ""
    value = cell.find("{*}v")
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (ValueError, IndexError) as exc:
            raise SourceSyncError("XLSX shared string reference is invalid") from exc
    if cell_type == "b":
        return "true" if value.text == "1" else "false"
    return value.text


def _xlsx_rows(content: bytes) -> list[list[str]]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as workbook:
            shared_strings = _xlsx_shared_strings(workbook)
            sheet_path = _xlsx_first_sheet_path(workbook)
            sheet_root = ElementTree.fromstring(workbook.read(sheet_path))
    except zipfile.BadZipFile as exc:
        raise SourceSyncError("The XLSX file could not be opened") from exc
    except KeyError as exc:
        raise SourceSyncError("The XLSX first worksheet could not be read") from exc
    except ElementTree.ParseError as exc:
        raise SourceSyncError("The XLSX first worksheet is malformed") from exc

    rows: list[list[str]] = []
    for row in sheet_root.findall(".//{*}sheetData/{*}row"):
        values: list[str] = []
        for cell in row.findall("{*}c"):
            column = _xlsx_column_index(cell.attrib.get("r", ""))
            while len(values) <= column:
                values.append("")
            values[column] = _xlsx_cell_value(cell, shared_strings).strip()
        rows.append(values)
    return rows


def parse_source_xlsx(content: bytes) -> tuple[str, list[ParsedSourceRow]]:
    if not content:
        raise SourceSyncError("The uploaded XLSX is empty")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceSyncError("The uploaded XLSX is larger than 5 MB")
    rows = _xlsx_rows(content)
    normalized_csv = io.StringIO()
    writer = csv.writer(normalized_csv)
    writer.writerows(rows)
    return normalized_csv.getvalue(), _parse_source_rows(rows)


def parse_source_file(filename: str, content: bytes) -> tuple[str, list[ParsedSourceRow]]:
    suffix = filename.rsplit(".", 1)[-1].casefold() if "." in filename else "csv"
    if suffix == "xlsx":
        return parse_source_xlsx(content)
    if suffix == "csv":
        return parse_source_csv(content)
    raise SourceSyncError("Upload must be a CSV or XLSX file")


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
    raw_csv, rows = parse_source_file(filename, content)
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
            "auto_created": 0,
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
    auto_created = counts.get("auto_create", 0)
    auto_matched = counts.get("exact", 0) + counts.get("likely", 0) + auto_created
    manually_matched = counts.get("manual", 0)
    return {
        "rows": snapshot.row_count,
        "matched": auto_matched,
        "auto_matched": auto_matched,
        "auto_created": auto_created,
        "manually_matched": manually_matched,
        "accepted": auto_matched + manually_matched,
        "conflicts": conflicts,
        "ambiguous": counts.get("ambiguous", 0),
        "duplicates": counts.get("duplicate", 0),
        "source_only": counts.get("source_only", 0),
    }


def source_new_addition_rows(db: Session, *, snapshot: SourceSnapshot) -> list[SourceMovieRow]:
    return (
        db.query(SourceMovieRow)
        .options(selectinload(SourceMovieRow.match).selectinload(SourceReconciliationMatch.movie))
        .join(
            SourceReconciliationMatch,
            SourceReconciliationMatch.source_row_id == SourceMovieRow.id,
        )
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .filter(SourceReconciliationMatch.match_type == "auto_create")
        .order_by(SourceMovieRow.row_number.asc())
        .all()
    )


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
    db: Session,
    row: SourceMovieRow,
    movie: Movie,
    *,
    decisions: dict[str, SourceFieldDecision] | None = None,
) -> tuple[SourceFieldConflict, ...]:
    if decisions is None:
        decisions = {}
        for decision in (
            db.query(SourceFieldDecision)
            .filter(SourceFieldDecision.source_row_id == row.id)
            .filter(SourceFieldDecision.undone_at.is_(None))
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
    row_ids = [row.id for row in rows]
    decisions_by_row: dict[int, dict[str, SourceFieldDecision]] = defaultdict(dict)
    if row_ids:
        active_decisions = (
            db.query(SourceFieldDecision)
            .filter(SourceFieldDecision.source_row_id.in_(row_ids))
            .filter(SourceFieldDecision.undone_at.is_(None))
            .order_by(
                SourceFieldDecision.source_row_id.asc(),
                SourceFieldDecision.decided_at.desc(),
                SourceFieldDecision.id.desc(),
            )
            .all()
        )
        for decision in active_decisions:
            decisions_by_row[decision.source_row_id].setdefault(decision.field_name, decision)
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
        research_links = build_research_links(
            source_title=row.title,
            source_year=row.year,
            source_director=row.director,
            movie=match.movie,
        )
        candidate_research_links = {
            candidate.id: build_research_links(
                source_title=row.title,
                source_year=row.year,
                source_director=row.director,
                movie=candidate,
            )
            for candidate in candidate_movies
        }
        if match.match_type in {"exact", "likely", "manual"} and match.movie is not None:
            conflicts = source_row_conflicts(
                db,
                row,
                match.movie,
                decisions=decisions_by_row.get(row.id, {}),
            )
            if conflicts:
                items.append(
                    SourceReviewItem(
                        source_row=row,
                        match=match,
                        movie=match.movie,
                        conflicts=conflicts,
                        research_links=research_links,
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
                    research_links=research_links,
                    candidate_research_links=candidate_research_links,
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


def partition_source_review_queue(
    items: list[SourceReviewItem],
) -> dict[str, list[SourceReviewItem]]:
    groups: dict[str, list[SourceReviewItem]] = {
        "differences": [],
        "research": [],
        "ambiguous": [],
        "new": [],
        "duplicates": [],
    }
    for item in items:
        if item.conflicts:
            normal = tuple(conflict for conflict in item.conflicts if not conflict.research)
            research = tuple(conflict for conflict in item.conflicts if conflict.research)
            if normal:
                groups["differences"].append(
                    SourceReviewItem(
                        source_row=item.source_row,
                        match=item.match,
                        movie=item.movie,
                        conflicts=normal,
                        candidate_movies=item.candidate_movies,
                        research_links=item.research_links,
                        candidate_research_links=item.candidate_research_links,
                    )
                )
            if research:
                groups["research"].append(
                    SourceReviewItem(
                        source_row=item.source_row,
                        match=item.match,
                        movie=item.movie,
                        conflicts=research,
                        candidate_movies=item.candidate_movies,
                        research_links=item.research_links,
                        candidate_research_links=item.candidate_research_links,
                    )
                )
        elif item.match.match_type == "ambiguous":
            groups["ambiguous"].append(item)
        elif item.match.match_type == "source_only":
            groups["new"].append(item)
        elif item.match.match_type == "duplicate":
            groups["duplicates"].append(item)
    return groups


def _set_director_names(db: Session, movie: Movie, names: tuple[str, ...]) -> None:
    db.query(Role).filter(Role.movie_id == movie.id).filter(
        Role.role_type == RoleType.DIRECTOR
    ).delete(synchronize_session=False)
    for index, name in enumerate(names):
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


def _set_directors(db: Session, movie: Movie, director_value: str | None) -> None:
    _set_director_names(db, movie, parse_directors(director_value))


def _decide_source_field(
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
        apply_title_year_authority(
            db,
            movie=movie,
            profile_id=profile_id,
        )
        selected_value = _field_values(row, movie)[field_name][1]

    now = datetime.now(timezone.utc)
    (
        db.query(SourceFieldDecision)
        .filter(SourceFieldDecision.source_row_id == row.id)
        .filter(SourceFieldDecision.field_name == field_name)
        .filter(SourceFieldDecision.decision == "needs_research")
        .filter(SourceFieldDecision.resolved_at.is_(None))
        .filter(SourceFieldDecision.undone_at.is_(None))
        .update({SourceFieldDecision.resolved_at: now}, synchronize_session=False)
    )
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
    record.decided_at = now
    record.resolved_at = None if decision == "needs_research" else now
    db.flush()
    return record


def decide_source_field(
    db: Session,
    *,
    row_id: int,
    field_name: str,
    decision: str,
    profile_id: int | None,
) -> SourceFieldDecision:
    record = _decide_source_field(
        db,
        row_id=row_id,
        field_name=field_name,
        decision=decision,
        profile_id=profile_id,
    )
    db.commit()
    db.refresh(record)
    return record


def _bulk_source_fields(
    db: Session,
    *,
    snapshot: SourceSnapshot,
) -> tuple[list[tuple[int, int, str]], int]:
    review_items = get_source_review_queue(
        db,
        snapshot=snapshot,
        include_unmatched=False,
    )
    candidate_by_movie_field: dict[tuple[int, str], tuple[int, int, str]] = {}
    for item in review_items:
        if item.movie is None:
            continue
        for conflict in item.conflicts:
            key = (item.movie.id, conflict.field_name)
            candidate_by_movie_field.setdefault(
                key,
                (item.source_row.id, item.movie.id, conflict.field_name),
            )
    candidate_fields = list(candidate_by_movie_field.values())

    source_values: dict[tuple[int, str], set[object]] = defaultdict(set)
    matched_rows = (
        db.query(SourceMovieRow, SourceReconciliationMatch)
        .join(
            SourceReconciliationMatch,
            SourceReconciliationMatch.source_row_id == SourceMovieRow.id,
        )
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .filter(SourceReconciliationMatch.movie_id.is_not(None))
        .filter(SourceReconciliationMatch.match_type.in_(("exact", "likely", "manual")))
        .all()
    )
    for row, match in matched_rows:
        values = {
            "title": normalize_title(row.title),
            "year": row.year,
            "runtime": row.runtime,
            "director": tuple(sorted(name.casefold() for name in parse_directors(row.director))),
        }
        for field_name, value in values.items():
            if value not in {None, "", ()}:
                source_values[(match.movie_id, field_name)].add(value)

    open_fields = [
        field for field in candidate_fields if len(source_values[(field[1], field[2])]) <= 1
    ]
    return open_fields, len(candidate_fields) - len(open_fields)


def source_bulk_decision_counts(
    db: Session,
    *,
    snapshot: SourceSnapshot | None = None,
) -> tuple[int, int]:
    snapshot = snapshot or latest_active_snapshot(db)
    if snapshot is None:
        return 0, 0
    open_fields, skipped_field_count = _bulk_source_fields(db, snapshot=snapshot)
    return len(open_fields), skipped_field_count


def accept_all_source_differences(
    db: Session,
    *,
    profile_id: int | None,
    snapshot: SourceSnapshot | None = None,
) -> BulkSourceDecisionResult:
    snapshot = snapshot or latest_active_snapshot(db)
    if snapshot is None:
        raise SourceSyncError("No confirmed source snapshot is available")

    open_fields, skipped_field_count = _bulk_source_fields(db, snapshot=snapshot)
    movie_ids = {movie_id for _, movie_id, _ in open_fields}

    try:
        for row_id, _, field_name in open_fields:
            _decide_source_field(
                db,
                row_id=row_id,
                field_name=field_name,
                decision="use_source",
                profile_id=profile_id,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return BulkSourceDecisionResult(
        snapshot_id=snapshot.id,
        movie_count=len(movie_ids),
        field_count=len(open_fields),
        skipped_field_count=skipped_field_count,
    )


def defer_source_row_for_research(
    db: Session,
    *,
    row_id: int,
    profile_id: int | None,
) -> list[SourceFieldDecision]:
    row = db.get(SourceMovieRow, row_id)
    if row is None or row.match is None or row.match.movie_id is None:
        raise SourceSyncError("Source row is not matched to a Vault entry")
    movie = db.get(Movie, row.match.movie_id)
    if movie is None:
        raise SourceSyncError("Matched Vault entry no longer exists")
    conflicts = source_row_conflicts(db, row, movie)
    open_conflicts = [conflict for conflict in conflicts if not conflict.research]
    if not open_conflicts:
        raise SourceSyncError("This movie is already deferred for research")

    now = datetime.now(timezone.utc)
    records: list[SourceFieldDecision] = []
    field_values = _field_values(row, movie)
    for conflict in open_conflicts:
        source_value, vault_value = field_values[conflict.field_name]
        record = SourceFieldDecision(
            source_row_id=row.id,
            movie_id=movie.id,
            field_name=conflict.field_name,
            previous_value=_display_value(vault_value),
            source_value=_display_value(source_value),
            selected_value=_display_value(vault_value),
            decision="needs_research",
            decided_by_profile_id=profile_id,
            decided_at=now,
            resolved_at=None,
        )
        db.add(record)
        records.append(record)
    db.commit()
    for record in records:
        db.refresh(record)
    return records


def undo_source_field_decision(
    db: Session,
    *,
    decision_id: int,
    profile_id: int | None,
) -> SourceFieldDecision:
    record = db.get(SourceFieldDecision, decision_id)
    if record is None or record.undone_at is not None:
        raise SourceSyncError("Review decision is no longer available to undo")
    latest = (
        db.query(SourceFieldDecision)
        .filter(SourceFieldDecision.source_row_id == record.source_row_id)
        .filter(SourceFieldDecision.field_name == record.field_name)
        .filter(SourceFieldDecision.undone_at.is_(None))
        .order_by(SourceFieldDecision.decided_at.desc(), SourceFieldDecision.id.desc())
        .first()
    )
    if latest is None or latest.id != record.id:
        raise SourceSyncError("Only the latest decision for this field can be undone")
    decided_at = record.decided_at
    if decided_at.tzinfo is None:
        decided_at = decided_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - decided_at > UNDO_WINDOW:
        raise SourceSyncError("The undo window for this decision has expired")

    movie = db.get(Movie, record.movie_id)
    if movie is None:
        raise SourceSyncError("The Vault entry no longer exists")
    if record.decision == "use_source":
        previous = None if record.previous_value in {None, "Missing"} else record.previous_value
        if record.field_name == "title":
            if previous is None:
                raise SourceSyncError("The previous title cannot be restored")
            movie.title = previous
        elif record.field_name == "year":
            movie.year = int(previous) if previous is not None else None
        elif record.field_name == "runtime":
            movie.runtime = int(previous) if previous is not None else None
        elif record.field_name == "director":
            names = tuple(name.strip() for name in (previous or "").split(",") if name.strip())
            _set_director_names(db, movie, names)

    record.undone_at = datetime.now(timezone.utc)
    record.undone_by_profile_id = profile_id
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


def classify_first_import_row(
    db: Session,
    *,
    row: SourceMovieRow,
    candidates: list[dict],
) -> FirstImportDecision:
    if row.duplicate_group:
        return FirstImportDecision(row=row, bucket="duplicate_conflict", reason="source_duplicate")
    if _existing_title_year(db, row.title, row.year) is not None:
        return FirstImportDecision(row=row, bucket="duplicate_conflict", reason="title_year_exists")
    if not candidates:
        return FirstImportDecision(row=row, bucket="failed_lookup", reason="no_candidates")

    strong_candidates = [
        candidate
        for candidate in candidates
        if float(candidate.get("match_confidence") or 0) >= 0.95
        and "title_only" not in str(candidate.get("match_strategy") or "")
    ]
    if not strong_candidates:
        return FirstImportDecision(
            row=row,
            bucket="needs_review",
            reason="low_confidence",
            candidate=candidates[0],
            confidence=float(candidates[0].get("match_confidence") or 0),
        )
    if len(strong_candidates) > 1:
        return FirstImportDecision(
            row=row,
            bucket="needs_review",
            reason="multiple_strong_candidates",
            candidate=strong_candidates[0],
            confidence=float(strong_candidates[0].get("match_confidence") or 0),
        )

    candidate = strong_candidates[0]
    confidence = float(candidate.get("match_confidence") or 0)
    metadata = MovieMetadata.from_mapping(candidate)
    if not metadata.title or metadata.year is None:
        return FirstImportDecision(
            row=row,
            bucket="needs_review",
            reason="candidate_missing_identity",
            candidate=candidate,
            confidence=confidence,
        )
    if metadata.tmdb_id is None and not metadata.imdb_id:
        return FirstImportDecision(
            row=row,
            bucket="needs_review",
            reason="candidate_missing_external_id",
            candidate=candidate,
            confidence=confidence,
        )
    if row.year is None or abs(row.year - metadata.year) > 1:
        return FirstImportDecision(
            row=row,
            bucket="needs_review",
            reason="year_mismatch",
            candidate=candidate,
            confidence=confidence,
        )
    if _standard_title_key(row.title) != _standard_title_key(metadata.title) and confidence < 0.98:
        return FirstImportDecision(
            row=row,
            bucket="needs_review",
            reason="title_mismatch",
            candidate=candidate,
            confidence=confidence,
        )
    if row.runtime is not None and metadata.runtime is not None:
        if abs(row.runtime - metadata.runtime) > 5:
            return FirstImportDecision(
                row=row,
                bucket="needs_review",
                reason="runtime_mismatch",
                candidate=candidate,
                confidence=confidence,
            )
    if _external_id_owner(db, tmdb_id=metadata.tmdb_id, imdb_id=metadata.imdb_id) is not None:
        return FirstImportDecision(
            row=row,
            bucket="duplicate_conflict",
            reason="external_id_exists",
            candidate=candidate,
            confidence=confidence,
        )
    return FirstImportDecision(
        row=row,
        bucket="auto_create",
        reason="high_confidence",
        candidate=candidate,
        confidence=confidence,
    )


def analyze_first_import_snapshot(db: Session, *, snapshot_id: int) -> FirstImportAnalysis:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise SourceSyncError("Source snapshot was not found")

    buckets: dict[str, list[FirstImportDecision]] = {
        "auto_create": [],
        "needs_review": [],
        "duplicate_conflict": [],
        "failed_lookup": [],
    }
    for row in snapshot.rows:
        candidates: list[dict] = []
        try:
            candidates = lookup_movie_candidates(row.title, row.year, limit=3)
        except (MovieLookupUnavailable, MovieLookupNotFound):
            decision = FirstImportDecision(
                row=row, bucket="failed_lookup", reason="lookup_unavailable"
            )
        except MovieLookupError:
            decision = FirstImportDecision(row=row, bucket="failed_lookup", reason="lookup_failed")
        else:
            decision = classify_first_import_row(db, row=row, candidates=candidates)
        buckets[decision.bucket].append(decision)

    return FirstImportAnalysis(
        snapshot_id=snapshot.id,
        auto_create=tuple(buckets["auto_create"]),
        needs_review=tuple(buckets["needs_review"]),
        duplicate_conflict=tuple(buckets["duplicate_conflict"]),
        failed_lookup=tuple(buckets["failed_lookup"]),
    )


def create_movie_from_source_row_metadata(
    db: Session,
    *,
    row: SourceMovieRow,
    metadata: MovieMetadata,
    profile_id: int | None,
    confidence: float,
) -> Movie:
    if _external_id_owner(db, tmdb_id=metadata.tmdb_id, imdb_id=metadata.imdb_id) is not None:
        raise SourceSyncError("External ID is already assigned to a Vault entry")

    movie = Movie(
        vault_id=next_vault_id(db),
        title=metadata.title or row.title,
        year=metadata.year if metadata.year is not None else row.year,
        runtime=metadata.runtime if metadata.runtime is not None else row.runtime,
        plot=metadata.plot,
        awards=metadata.awards,
        certificate=metadata.certificate,
        keywords=metadata.keywords or None,
        imdb_id=metadata.imdb_id,
        tmdb_id=metadata.tmdb_id,
        imdb_rating=metadata.imdb_rating,
        imdb_votes=metadata.imdb_votes,
        metascore=metadata.metascore,
        tomato_meter=metadata.tomato_meter,
        tomato_audience=metadata.tomato_audience,
        rt_score=metadata.rt_score,
        poster_url=metadata.poster_url,
        backdrop_url=metadata.backdrop_url,
        where_to_watch=metadata.where_to_watch or None,
        languages=metadata.languages or None,
        countries=metadata.countries or None,
        collection=metadata.collection,
        last_tmdb_fetch_at=metadata.last_tmdb_fetch_at,
        last_omdb_fetch_at=metadata.last_omdb_fetch_at,
        tmdb_payload_sha=metadata.tmdb_payload_sha,
        omdb_payload_sha=metadata.omdb_payload_sha,
    )
    movie.genres = _metadata_genres(db, metadata.genres)
    db.add(movie)
    db.flush()

    director_names = tuple(metadata.directors) or parse_directors(row.director)
    _set_director_names(db, movie, director_names)

    providers = []
    if metadata.tmdb_id is not None:
        providers.append(
            (
                "tmdb",
                str(metadata.tmdb_id),
                metadata.tmdb_payload_sha,
                f"https://www.themoviedb.org/movie/{metadata.tmdb_id}",
            )
        )
    if metadata.imdb_id:
        providers.append(
            (
                "omdb",
                metadata.imdb_id,
                metadata.omdb_payload_sha,
                f"https://www.imdb.com/title/{metadata.imdb_id}/",
            )
        )
    providers.append(("collection_source", str(row.id), row.snapshot.file_sha256, None))
    for provider, provider_id, payload_sha, source_url in providers:
        db.add(
            MovieIngestProvenance(
                movie_id=movie.id,
                provider=provider,
                provider_id=provider_id,
                payload_sha=payload_sha,
                source_url=source_url,
                notes=f"Created during first import from source snapshot #{row.snapshot_id}",
            )
        )

    if row.match is None:
        row.match = SourceReconciliationMatch(source_row_id=row.id, match_type="auto_create")
    row.match.movie_id = movie.id
    row.match.match_type = "auto_create"
    row.match.confidence = confidence
    row.match.candidate_movie_ids = [movie.id]
    row.match.resolved_at = datetime.now(timezone.utc)
    _create_owned_copy(db, row, movie.id)
    return movie


def apply_first_import_auto_create(
    db: Session,
    *,
    snapshot_id: int,
    profile_id: int | None,
) -> FirstImportApplyResult:
    analysis = analyze_first_import_snapshot(db, snapshot_id=snapshot_id)
    created_movie_ids: list[int] = []
    try:
        snapshot = db.get(SourceSnapshot, snapshot_id)
        if snapshot is None:
            raise SourceSyncError("Source snapshot was not found")
        if snapshot.status == "draft":
            db.query(SourceSnapshot).filter(SourceSnapshot.status == "active").filter(
                SourceSnapshot.id != snapshot.id
            ).update({"status": "superseded"}, synchronize_session=False)
            snapshot.status = "active"
            snapshot.confirmed_at = datetime.now(timezone.utc)
        for decision in analysis.auto_create:
            if decision.candidate is None:
                continue
            movie = create_movie_from_source_row_metadata(
                db,
                row=decision.row,
                metadata=MovieMetadata.from_mapping(decision.candidate),
                profile_id=profile_id,
                confidence=decision.confidence,
            )
            created_movie_ids.append(movie.id)
        for decision in analysis.needs_review:
            match = decision.row.match or SourceReconciliationMatch(source_row_id=decision.row.id)
            match.match_type = "ambiguous"
            match.confidence = decision.confidence
            match.candidate_movie_ids = None
            match.resolved_at = None
            decision.row.match = match
        for decision in analysis.duplicate_conflict:
            match = decision.row.match or SourceReconciliationMatch(source_row_id=decision.row.id)
            match.match_type = "duplicate"
            match.confidence = decision.confidence
            match.candidate_movie_ids = None
            match.resolved_at = None
            decision.row.match = match
        for decision in analysis.failed_lookup:
            match = decision.row.match or SourceReconciliationMatch(source_row_id=decision.row.id)
            match.match_type = "source_only"
            match.confidence = decision.confidence
            match.candidate_movie_ids = None
            match.resolved_at = None
            decision.row.match = match
        db.commit()
    except Exception:
        db.rollback()
        raise

    return FirstImportApplyResult(
        snapshot_id=snapshot_id,
        created_count=len(created_movie_ids),
        review_count=len(analysis.needs_review),
        duplicate_conflict_count=len(analysis.duplicate_conflict),
        failed_lookup_count=len(analysis.failed_lookup),
        created_movie_ids=tuple(created_movie_ids),
    )


def first_import_report(db: Session, *, snapshot_id: int) -> FirstImportReport:
    snapshot = db.get(SourceSnapshot, snapshot_id)
    if snapshot is None:
        raise SourceSyncError("Source snapshot was not found")
    counts = dict(
        db.query(SourceReconciliationMatch.match_type, func.count())
        .join(SourceMovieRow, SourceMovieRow.id == SourceReconciliationMatch.source_row_id)
        .filter(SourceMovieRow.snapshot_id == snapshot.id)
        .group_by(SourceReconciliationMatch.match_type)
        .all()
    )
    return FirstImportReport(
        snapshot=snapshot,
        created_count=counts.get("auto_create", 0),
        review_count=counts.get("ambiguous", 0),
        duplicate_conflict_count=counts.get("duplicate", 0),
        source_only_count=counts.get("source_only", 0),
    )


def create_movie_from_source_row(db: Session, *, row_id: int, profile_id: int | None) -> Movie:
    row = db.get(SourceMovieRow, row_id)
    if row is None or row.match is None:
        raise SourceSyncError("Source row was not found")
    if row.match.match_type not in {"ambiguous", "source_only", "duplicate"}:
        raise SourceSyncError("This source row cannot create a movie")
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
    "BulkSourceDecisionResult",
    "SourceFieldConflict",
    "ResearchLink",
    "ResearchLinkSet",
    "SourceReviewItem",
    "SourceSyncError",
    "FirstImportAnalysis",
    "FirstImportApplyResult",
    "FirstImportDecision",
    "FirstImportReport",
    "assign_source_row_match",
    "accept_all_source_differences",
    "analyze_first_import_snapshot",
    "apply_first_import_auto_create",
    "build_research_links",
    "classify_first_import_row",
    "clean_research_title",
    "create_movie_from_source_row_metadata",
    "create_draft_snapshot",
    "create_movie_from_source_row",
    "decide_source_field",
    "defer_source_row_for_research",
    "dismiss_duplicate",
    "first_import_report",
    "get_source_review_queue",
    "latest_active_snapshot",
    "parse_source_csv",
    "partition_source_review_queue",
    "reconcile_snapshot",
    "snapshot_summary",
    "source_bulk_decision_counts",
    "source_new_addition_rows",
    "source_provenance_for_movie",
    "undo_source_field_decision",
]
