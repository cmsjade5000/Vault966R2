"""Fill missing IMDb/TMDb IDs and posters only for exact, corroborated matches."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import or_, select

ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config import settings  # noqa: E402
from api.db import SessionLocal  # noqa: E402
from api.models.movie import Movie, MovieIngestProvenance  # noqa: E402
from api.services.source_sync import get_source_review_queue  # noqa: E402
from scripts.backfill_db_backup import backup_active_sqlite_database  # noqa: E402
from scripts.backfill_posters import normalize_title  # noqa: E402

TMDB_API_BASE = "https://api.themoviedb.org/3"
OMDB_API_BASE = "https://www.omdbapi.com/"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill only exact, cross-verified external movie matches"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--flags-only",
        action="store_true",
        help="Process only movies currently in the manual flag queue.",
    )
    parser.add_argument(
        "--report",
        default=str(ROOT_DIR / "reports" / "clear_external_matches.csv"),
    )
    return parser.parse_args()


def payload_sha(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def release_year(value: object) -> int | None:
    text = str(value or "").strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


def exact_title_year(
    requested_title: str,
    requested_year: int | None,
    candidate_title: object,
    candidate_year: object,
) -> bool:
    if requested_year is None:
        return False
    return (
        normalize_title(str(candidate_title or "")) == normalize_title(requested_title)
        and release_year(candidate_year) == requested_year
    )


def tmdb_detail(client: httpx.Client, api_key: str, tmdb_id: int) -> dict[str, Any]:
    response = client.get(
        f"{TMDB_API_BASE}/movie/{tmdb_id}",
        params={"api_key": api_key, "append_to_response": "external_ids"},
        timeout=12.0,
    )
    response.raise_for_status()
    return response.json()


def unique_exact_tmdb_match(
    client: httpx.Client,
    api_key: str,
    title: str,
    year: int,
) -> dict[str, Any] | None:
    response = client.get(
        f"{TMDB_API_BASE}/search/movie",
        params={
            "api_key": api_key,
            "query": normalize_title(title),
            "year": year,
            "include_adult": "false",
        },
        timeout=12.0,
    )
    response.raise_for_status()
    matches = {
        int(item["id"]): item
        for item in response.json().get("results", [])
        if item.get("id")
        and exact_title_year(title, year, item.get("title"), item.get("release_date"))
    }
    if len(matches) != 1:
        return None
    return tmdb_detail(client, api_key, next(iter(matches)))


def omdb_by_id(client: httpx.Client, api_key: str, imdb_id: str) -> dict[str, Any] | None:
    response = client.get(
        OMDB_API_BASE,
        params={"apikey": api_key, "i": imdb_id, "type": "movie"},
        timeout=12.0,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if payload.get("Response") == "True" else None


def omdb_by_title(
    client: httpx.Client,
    api_key: str,
    title: str,
    year: int,
) -> dict[str, Any] | None:
    response = client.get(
        OMDB_API_BASE,
        params={
            "apikey": api_key,
            "t": normalize_title(title),
            "y": year,
            "type": "movie",
        },
        timeout=12.0,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("Response") != "True":
        return None
    if not exact_title_year(title, year, payload.get("Title"), payload.get("Year")):
        return None
    return payload


def poster_from_tmdb(payload: dict[str, Any] | None) -> str | None:
    path = (payload or {}).get("poster_path")
    return f"https://image.tmdb.org/t/p/w500{path}" if path else None


def poster_from_omdb(payload: dict[str, Any] | None) -> str | None:
    value = str((payload or {}).get("Poster") or "").strip()
    return value if value and value != "N/A" and value.startswith("https://") else None


def _upsert_provenance(
    session,
    movie: Movie,
    *,
    provider: str,
    provider_id: str,
    payload: dict[str, Any],
    source_url: str,
) -> None:
    record = session.execute(
        select(MovieIngestProvenance)
        .where(MovieIngestProvenance.movie_id == movie.id)
        .where(MovieIngestProvenance.provider == provider)
    ).scalar_one_or_none()
    if record is None:
        record = MovieIngestProvenance(movie_id=movie.id, provider=provider)
        session.add(record)
    record.provider_id = provider_id
    record.payload_sha = payload_sha(payload)
    record.source_url = source_url
    record.notes = "Exact normalized title and exact year; external IDs cross-checked."


def _clear_missing_id_flag(session, movie: Movie) -> None:
    flag = movie.flag
    if flag is None or flag.reason != "Human review":
        return
    resolved_notes = {"No source IDs"}
    if movie.year is not None:
        resolved_notes.add("Year is missing")
    remaining = [
        note.strip()
        for note in (flag.notes or "").split(";")
        if note.strip() and note.strip() not in resolved_notes
    ]
    if remaining:
        flag.notes = "; ".join(remaining)
    else:
        session.delete(flag)


def write_report(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    if not settings.tmdb_api_key or not settings.omdb_api_key:
        raise SystemExit("TMDB_API_KEY and OMDB_API_KEY are both required.")

    report_rows: list[dict[str, Any]] = []
    updated = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    if not args.dry_run:
        backup = backup_active_sqlite_database("external-match sweep", now=now)
        print(f"backup: {backup.backup}")

    with SessionLocal() as session, httpx.Client() as client:
        source_review_ids = {
            item.movie.id for item in get_source_review_queue(session) if item.movie is not None
        }
        movies = session.execute(
            select(Movie)
            .where(
                or_(
                    Movie.imdb_id.is_(None),
                    Movie.tmdb_id.is_(None),
                    Movie.poster_url.is_(None),
                    Movie.poster_url == "",
                )
            )
            .order_by(Movie.vault_id.asc(), Movie.id.asc())
        ).scalars()

        for movie in movies:
            if args.limit and len(report_rows) >= args.limit:
                break
            if args.flags_only and movie.flag is None:
                continue
            if movie.year is None or movie.id in source_review_ids:
                continue
            if movie.flag is not None and movie.flag.reason != "Human review":
                continue
            if (
                movie.flag is not None
                and "No source IDs" not in (movie.flag.notes or "")
                and movie.imdb_id
                and movie.tmdb_id
            ):
                continue

            original_imdb = movie.imdb_id
            original_tmdb = movie.tmdb_id
            original_poster = movie.poster_url
            tmdb_payload = None
            omdb_payload = None
            reason = ""

            try:
                if movie.tmdb_id:
                    tmdb_payload = tmdb_detail(client, settings.tmdb_api_key, movie.tmdb_id)
                    if not exact_title_year(
                        movie.title,
                        movie.year,
                        tmdb_payload.get("title"),
                        tmdb_payload.get("release_date"),
                    ):
                        reason = "existing_tmdb_identity_disagrees"
                else:
                    tmdb_payload = unique_exact_tmdb_match(
                        client,
                        settings.tmdb_api_key,
                        movie.title,
                        movie.year,
                    )
                    if tmdb_payload is None:
                        reason = "no_unique_exact_tmdb_match"

                if not reason:
                    tmdb_imdb = str(
                        (tmdb_payload.get("external_ids") or {}).get("imdb_id") or ""
                    ).strip()
                    if movie.imdb_id:
                        omdb_payload = omdb_by_id(client, settings.omdb_api_key, movie.imdb_id)
                        if not omdb_payload or not exact_title_year(
                            movie.title,
                            movie.year,
                            omdb_payload.get("Title"),
                            omdb_payload.get("Year"),
                        ):
                            reason = "existing_imdb_identity_disagrees"
                        elif tmdb_imdb and tmdb_imdb != movie.imdb_id:
                            reason = "provider_ids_disagree"
                    else:
                        omdb_payload = omdb_by_title(
                            client,
                            settings.omdb_api_key,
                            movie.title,
                            movie.year,
                        )
                        omdb_imdb = str((omdb_payload or {}).get("imdbID") or "").strip()
                        if not omdb_imdb or not tmdb_imdb or omdb_imdb != tmdb_imdb:
                            reason = "providers_did_not_corroborate"
            except (httpx.HTTPError, ValueError):
                reason = "provider_request_failed"

            if reason:
                skipped += 1
                report_rows.append(
                    {
                        "vault_id": movie.vault_id or "",
                        "title": movie.title,
                        "year": movie.year,
                        "status": "skipped",
                        "reason": reason,
                        "imdb_before": original_imdb or "",
                        "imdb_after": original_imdb or "",
                        "tmdb_before": original_tmdb or "",
                        "tmdb_after": original_tmdb or "",
                        "poster_added": False,
                    }
                )
                continue

            tmdb_id = int(tmdb_payload["id"])
            imdb_id = str(
                (tmdb_payload.get("external_ids") or {}).get("imdb_id")
                or (omdb_payload or {}).get("imdbID")
                or ""
            ).strip()
            duplicate_tmdb = session.execute(
                select(Movie.id).where(Movie.tmdb_id == tmdb_id, Movie.id != movie.id)
            ).scalar_one_or_none()
            duplicate_imdb = (
                session.execute(
                    select(Movie.id).where(Movie.imdb_id == imdb_id, Movie.id != movie.id)
                ).scalar_one_or_none()
                if imdb_id
                else None
            )
            if duplicate_tmdb or duplicate_imdb:
                skipped += 1
                reason = "external_id_already_used"
            else:
                movie.tmdb_id = movie.tmdb_id or tmdb_id
                movie.imdb_id = movie.imdb_id or imdb_id or None
                movie.poster_url = (
                    movie.poster_url
                    or poster_from_tmdb(tmdb_payload)
                    or poster_from_omdb(omdb_payload)
                )
                movie.last_tmdb_fetch_at = now
                movie.tmdb_payload_sha = payload_sha(tmdb_payload)
                if omdb_payload:
                    movie.last_omdb_fetch_at = now
                    movie.omdb_payload_sha = payload_sha(omdb_payload)
                if movie.imdb_id and movie.tmdb_id:
                    _clear_missing_id_flag(session, movie)
                _upsert_provenance(
                    session,
                    movie,
                    provider="tmdb",
                    provider_id=str(movie.tmdb_id),
                    payload=tmdb_payload,
                    source_url=f"https://www.themoviedb.org/movie/{movie.tmdb_id}",
                )
                if omdb_payload and movie.imdb_id:
                    _upsert_provenance(
                        session,
                        movie,
                        provider="omdb",
                        provider_id=movie.imdb_id,
                        payload=omdb_payload,
                        source_url=f"https://www.imdb.com/title/{movie.imdb_id}/",
                    )
                updated += 1
                reason = "exact_cross_verified"

            report_rows.append(
                {
                    "vault_id": movie.vault_id or "",
                    "title": movie.title,
                    "year": movie.year,
                    "status": "updated" if reason == "exact_cross_verified" else "skipped",
                    "reason": reason,
                    "imdb_before": original_imdb or "",
                    "imdb_after": movie.imdb_id or "",
                    "tmdb_before": original_tmdb or "",
                    "tmdb_after": movie.tmdb_id or "",
                    "poster_added": bool(not original_poster and movie.poster_url),
                }
            )

        if args.dry_run:
            session.rollback()
        else:
            session.commit()

    write_report(pathlib.Path(args.report), report_rows)
    print(
        f"Clear-match sweep complete. checked={len(report_rows)} "
        f"updated={updated} skipped={skipped} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
