#!/usr/bin/env python3
"""Create a bounded, offline-safe Board catalog using Vault's cached posters."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "board-companion" / "public" / "catalog.snapshot.json"
OUTPUT = ROOT / "board-companion" / "public" / "catalog.board.json"
ART = ROOT / "board-companion" / "public" / "board-art"
DATABASE = Path.home() / "Library/Application Support/Vault966/data/vault.db"
CACHE = Path.home() / "Library/Application Support/Vault966/cache/posters"
VISIBLE_KEYS = ("V0775", "V0522", "V0317", "V0315", "V0233", "V0415")
LIMIT = 48


def cache_path(movie_id: int, source_url: str) -> Path | None:
    parsed = urlsplit(source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    parts = parsed.path.split("/")
    if len(parts) > 3 and parts[1:3] == ["t", "p"]:
        parts[3] = "w185"
        source_url = urlunsplit(("https", "image.tmdb.org", "/".join(parts), parsed.query, ""))
    digest = hashlib.sha256(source_url.encode()).hexdigest()[:16]
    stem = f"{movie_id}-w185-{digest}"
    for suffix in (".jpg", ".png", ".webp"):
        candidate = CACHE / f"{stem}{suffix}"
        if candidate.is_file():
            return candidate
    # Older Vault cache entries can preserve an upstream URL variant that is
    # no longer present in the sanitized catalog. A single same-movie w185
    # cache entry is still a safe local match; ambiguous entries stay absent.
    matches = [
        path
        for path in CACHE.glob(f"{movie_id}-w185-*")
        if path.suffix.lower() in {".jpg", ".png", ".webp"}
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def main() -> int:
    catalog = json.loads(SOURCE.read_text())
    movies = {movie["key"]: movie for movie in catalog["movies"]}
    selected = [movies[key] for key in VISIBLE_KEYS if key in movies]
    selected_keys = {movie["key"] for movie in selected}
    selected.extend(movie for movie in catalog["movies"] if movie["key"] not in selected_keys)
    selected = selected[:LIMIT]

    connection = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    rows = connection.execute("SELECT id, vault_id, poster_url FROM movies").fetchall()
    connection.close()
    poster_rows = {
        str(vault_id): (int(movie_id), str(url or "")) for movie_id, vault_id, url in rows
    }
    ART.mkdir(parents=True, exist_ok=True)
    copied = 0
    missing = 0
    for movie in selected:
        entry = poster_rows.get(movie["key"])
        source = cache_path(*entry) if entry else None
        if source is None:
            existing = list(ART.glob(f"{movie['key'].lower()}.*"))
            if len(existing) == 1:
                movie["artwork"] = {"poster": f"./board-art/{existing[0].name}"}
                copied += 1
                continue
            missing += 1
            movie["artwork"] = {}
            continue
        destination = ART / f"{movie['key'].lower()}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        movie["artwork"] = {"poster": f"./board-art/{destination.name}"}
        copied += 1

    catalog["movies"] = selected
    catalog["catalog_revision"] = f"{catalog.get('catalog_revision', 'vault')}-board-offline-v1"
    catalog["capabilities"] = {
        "read_only": True,
        "preference_writeback": False,
        "offline_posters": True,
    }
    OUTPUT.write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"movies={len(selected)} posters_copied={copied} posters_missing={missing}")
    return 0 if copied else 1


if __name__ == "__main__":
    raise SystemExit(main())
