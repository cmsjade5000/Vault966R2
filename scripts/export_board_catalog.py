"""Export a sanitized Vault 966 catalog for the no-device Board companion.

The exporter is deliberately independent of the application ORM. It opens the
SQLite source in URI read-only mode and enables SQLite's query-only guard before
reading the smallest set of fields needed by the companion. The default CLI
mode is a summary-only dry run; writing a local snapshot requires ``--write``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = (
    Path.home() / "Library" / "Application Support" / "Vault966" / "data" / "vault.db"
)
DEFAULT_OUTPUT = ROOT / "board-companion" / "public" / "catalog.snapshot.json"
CATALOG_SCHEMA_VERSION = "board-companion.catalog.v1"
NULL_STRINGS = {"", "n/a", "na", "none", "null", "unknown", "nan"}
VAULT_ID_PATTERN = re.compile(r"^V\d+$", re.IGNORECASE)


class ExportError(RuntimeError):
    """Raised when the source cannot produce a safe stable catalog."""


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in NULL_STRINGS:
        return None
    return text


def _clean_vault_id(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    if not VAULT_ID_PATTERN.fullmatch(text):
        return None
    return text.upper()


def _coerce_int(value: Any, *, positive: bool = False) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    if positive and number <= 0:
        return None
    return number


def _coerce_number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not number.is_integer():
        return number
    return int(number)


def _tokens(value: Any) -> list[str]:
    """Normalize JSON/list/text fields without leaking raw provider payloads."""

    if value is None:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    candidates: list[Any]
    if isinstance(value, Mapping):
        candidates = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        raw = str(value).strip()
        if not raw:
            return []
        try:
            decoded = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, (list, tuple, set, dict)):
            return _tokens(decoded)
        candidates = re.split(r"[|;,]", raw)

    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if isinstance(item, Mapping):
            nested = _tokens(item)
            for token in nested:
                key = token.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(token)
            continue
        text = _clean_text(item)
        if text is None:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _sorted_tokens(values: Iterable[str]) -> list[str]:
    return sorted(_tokens(list(values)), key=lambda value: (value.casefold(), value))


def _safe_https_url(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    parsed = urlsplit(text)
    if parsed.scheme.casefold() != "https" or not parsed.netloc:
        return None
    if parsed.username or parsed.password:
        return None
    # Drop query strings and fragments: signed URLs can contain credentials or
    # expire unpredictably, and the companion does not need them in v0.
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def _utc_iso(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _connect_read_only(database: Path) -> sqlite3.Connection:
    if not database.is_file():
        raise ExportError(f"SQLite database not found: {database}")
    encoded = quote(str(database.resolve()), safe="/")
    try:
        connection = sqlite3.connect(f"file:{encoded}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise ExportError(f"Could not open SQLite database read-only: {exc}") from exc
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
    except sqlite3.Error as exc:
        connection.close()
        raise ExportError(f"Could not enable SQLite query-only mode: {exc}") from exc
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    if table not in _table_names(connection):
        return set()
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _column(columns: set[str], name: str, alias: str | None = None) -> str:
    expression = f'"{name}"' if name in columns else "NULL"
    return f'{expression} AS "{alias or name}"'


def _load_movie_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    columns = _table_columns(connection, "movies")
    required = {"id", "title"}
    if not required.issubset(columns):
        raise ExportError("SQLite movies table is missing required columns")

    selected = [
        _column(columns, name)
        for name in (
            "id",
            "vault_id",
            "title",
            "year",
            "runtime",
            "plot",
            "imdb_rating",
            "imdb_votes",
            "metascore",
            "tomato_meter",
            "tomato_audience",
            "poster_url",
            "backdrop_url",
            "where_to_watch",
            "keywords",
        )
    ]
    rows = connection.execute(
        f'SELECT {", ".join(selected)} FROM "movies" ORDER BY "id"'
    ).fetchall()
    return [dict(row) for row in rows]


def _load_taxonomy(
    connection: sqlite3.Connection,
    *,
    association: str,
    taxonomy: str,
) -> dict[int, list[str]]:
    required_tables = {association, taxonomy}
    if not required_tables.issubset(_table_names(connection)):
        return {}
    rows = connection.execute(
        f"""
        SELECT association.movie_id, taxonomy.name
        FROM "{association}" AS association
        JOIN "{taxonomy}" AS taxonomy ON taxonomy.id = association.{taxonomy[:-1]}_id
        WHERE taxonomy.name IS NOT NULL AND trim(taxonomy.name) <> ''
        ORDER BY association.movie_id, lower(taxonomy.name), taxonomy.name
        """
    ).fetchall()
    result: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        movie_id = int(row[0])
        name = _clean_text(row[1])
        if name:
            result[movie_id].append(name)
    return {movie_id: _sorted_tokens(names) for movie_id, names in result.items()}


def _load_roles(connection: sqlite3.Connection) -> dict[int, list[dict[str, Any]]]:
    required_tables = {"roles", "people"}
    if not required_tables.issubset(_table_names(connection)):
        return {}
    role_columns = _table_columns(connection, "roles")
    required_columns = {"id", "movie_id", "person_id", "role_type"}
    if not required_columns.issubset(role_columns):
        return {}
    billing = 'roles."billing_order"' if "billing_order" in role_columns else "NULL"
    rows = connection.execute(
        f"""
        SELECT roles.movie_id, roles.role_type, people.name, {billing} AS billing_order, roles.id
        FROM "roles" AS roles
        JOIN "people" AS people ON people.id = roles.person_id
        WHERE upper(roles.role_type) IN ('ACTOR', 'DIRECTOR', 'WRITER')
          AND people.name IS NOT NULL AND trim(people.name) <> ''
        ORDER BY roles.movie_id, billing_order IS NULL, billing_order, roles.id
        """
    ).fetchall()
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[int(row[0])].append(
            {
                "role_type": str(row[1]).upper(),
                "name": str(row[2]).strip(),
                "billing_order": row[3],
            }
        )
    return dict(result)


def _load_preferences(
    connection: sqlite3.Connection,
    profile_id: int | None,
) -> dict[int, dict[str, bool]]:
    if profile_id is None or "movie_preferences" not in _table_names(connection):
        return {}
    columns = _table_columns(connection, "movie_preferences")
    if not {"profile_id", "movie_id", "liked", "watchlist"}.issubset(columns):
        return {}
    rows = connection.execute(
        """
        SELECT movie_id, liked, watchlist
        FROM movie_preferences
        WHERE profile_id = ?
        """,
        (profile_id,),
    ).fetchall()
    return {int(row[0]): {"liked": bool(row[1]), "watchlist": bool(row[2])} for row in rows}


def _ratings(row: Mapping[str, Any]) -> dict[str, int | float]:
    fields = (
        ("imdb", row.get("imdb_rating")),
        ("votes", row.get("imdb_votes")),
        ("metascore", row.get("metascore")),
        ("tomato", row.get("tomato_meter")),
        ("audience", row.get("tomato_audience")),
    )
    return {name: number for name, value in fields if (number := _coerce_number(value)) is not None}


def _project_movie(
    row: Mapping[str, Any],
    *,
    genres: Mapping[int, list[str]],
    moods: Mapping[int, list[str]],
    roles: Mapping[int, list[dict[str, Any]]],
    preferences: Mapping[int, Mapping[str, bool]],
    include_preferences: bool,
) -> dict[str, Any]:
    movie_id = int(row["id"])
    movie_roles = list(roles.get(movie_id, []))
    actors = [item["name"] for item in movie_roles if item["role_type"] == "ACTOR"]
    directors = [item["name"] for item in movie_roles if item["role_type"] == "DIRECTOR"]
    crew = [
        {"job": item["role_type"].title(), "name": item["name"]}
        for item in movie_roles
        if item["role_type"] in {"DIRECTOR", "WRITER"}
    ]
    artwork = {
        label: url
        for label, url in (
            ("poster", _safe_https_url(row.get("poster_url"))),
            ("backdrop", _safe_https_url(row.get("backdrop_url"))),
        )
        if url
    }

    movie: dict[str, Any] = {
        "key": _clean_vault_id(row.get("vault_id")),
        "title": _clean_text(row.get("title")) or "",
        "year": (
            year
            if (year := _coerce_int(row.get("year"))) is not None and 1870 <= year <= 2100
            else None
        ),
        "runtime": _coerce_int(row.get("runtime"), positive=True),
        "genres": list(genres.get(movie_id, [])),
        "moods": list(moods.get(movie_id, [])),
        "synopsis": _clean_text(row.get("plot")),
        "cast": actors[:12],
        "directors": directors[:4],
        "crew": crew[:8],
        "keywords": _sorted_tokens(_tokens(row.get("keywords")))[:24],
        "ratings": _ratings(row),
        "artwork": artwork,
        "source": "owned",
        "where_to_watch": _sorted_tokens(_tokens(row.get("where_to_watch"))),
    }
    if include_preferences:
        preference = preferences.get(movie_id, {})
        movie["liked"] = bool(preference.get("liked", False))
        movie["watchlist"] = bool(preference.get("watchlist", False))

    return {key: value for key, value in movie.items() if value not in (None, "", [], {})}


def build_catalog(
    movie_rows: Iterable[Mapping[str, Any]],
    *,
    genres: Mapping[int, list[str]] | None = None,
    moods: Mapping[int, list[str]] | None = None,
    roles: Mapping[int, list[dict[str, Any]]] | None = None,
    preferences: Mapping[int, Mapping[str, bool]] | None = None,
    profile_id: int | None = None,
    generated_at: datetime | None = None,
    allow_missing_vault_id: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    genres = genres or {}
    moods = moods or {}
    roles = roles or {}
    preferences = preferences or {}
    rows = list(movie_rows)
    missing_id_count = sum(_clean_vault_id(row.get("vault_id")) is None for row in rows)
    if missing_id_count and not allow_missing_vault_id:
        raise ExportError(
            f"{missing_id_count} movie records lack a valid persisted Vault ID; refusing to derive keys"
        )

    movies: list[dict[str, Any]] = []
    skipped_missing_title = 0
    for row in rows:
        key = _clean_vault_id(row.get("vault_id"))
        title = _clean_text(row.get("title"))
        if key is None:
            continue
        if title is None:
            skipped_missing_title += 1
            continue
        movies.append(
            _project_movie(
                row,
                genres=genres,
                moods=moods,
                roles=roles,
                preferences=preferences,
                include_preferences=profile_id is not None,
            )
        )

    movies.sort(key=lambda movie: (movie["key"].casefold(), movie["key"]))
    if len({movie["key"] for movie in movies}) != len(movies):
        raise ExportError("duplicate Vault IDs would make the Board catalog ambiguous")

    canonical = json.dumps(movies, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    revision = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    catalog = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "generated_at": _utc_iso(generated_at),
        "catalog_revision": revision,
        "movies": movies,
        "discovery": {
            "rails": [
                {"name": "library", "movie_keys": [movie["key"] for movie in movies]},
                {"name": "tonight", "movie_keys": [movie["key"] for movie in movies]},
            ]
        },
        "capabilities": {
            "read_only": True,
            "preference_writeback": False,
        },
    }
    summary = {
        "source_records": len(rows),
        "exported_records": len(movies),
        "skipped_missing_vault_id": missing_id_count,
        "skipped_missing_title": skipped_missing_title,
        "preferences_included": int(profile_id is not None),
    }
    return catalog, summary


def export_catalog(
    database: Path,
    *,
    profile_id: int | None = None,
    generated_at: datetime | None = None,
    allow_missing_vault_id: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    connection = _connect_read_only(database)
    try:
        catalog, summary = build_catalog(
            _load_movie_rows(connection),
            genres=_load_taxonomy(connection, association="movie_genres", taxonomy="genres"),
            moods=_load_taxonomy(connection, association="movie_moods", taxonomy="moods"),
            roles=_load_roles(connection),
            preferences=_load_preferences(connection, profile_id),
            profile_id=profile_id,
            generated_at=generated_at,
            allow_missing_vault_id=allow_missing_vault_id,
        )
        return catalog, summary
    finally:
        connection.close()


def write_catalog(path: Path, catalog: Mapping[str, Any], *, replace: bool = False) -> None:
    path = path.expanduser().resolve()
    if path.exists() and not replace:
        raise ExportError(f"output exists; pass --replace to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(catalog, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only export of the Vault 966 movie catalog for the Board companion"
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile-id", type=int, default=None)
    parser.add_argument("--allow-missing-vault-id", action="store_true")
    parser.add_argument(
        "--write", action="store_true", help="write a local snapshot; default is summary-only"
    )
    parser.add_argument(
        "--replace", action="store_true", help="allow replacing an existing output snapshot"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.profile_id is not None and args.profile_id <= 0:
        print("export failed: --profile-id must be positive", file=sys.stderr)
        return 2
    database = args.database.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output == database:
        print("export failed: output path must not be the source database", file=sys.stderr)
        return 2

    try:
        catalog, summary = export_catalog(
            database,
            profile_id=args.profile_id,
            allow_missing_vault_id=args.allow_missing_vault_id,
        )
        if args.write:
            write_catalog(output, catalog, replace=args.replace)
    except ExportError as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        return 2

    result: dict[str, Any] = {
        **summary,
        "catalog_revision": catalog["catalog_revision"],
        "mode": "write" if args.write else "dry-run",
    }
    if args.write:
        result["output"] = str(output)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
