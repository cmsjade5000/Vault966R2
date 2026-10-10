"""Fixed public login artwork, isolated from catalog rows and provider URLs."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re

POSTER_ROOT = Path(__file__).resolve().parents[2] / "static/img/login-posters"


@lru_cache(maxsize=1)
def login_posters() -> tuple[dict, ...]:
    manifest = json.loads((POSTER_ROOT / "manifest.json").read_text())
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"format", "posters"}
        or manifest["format"] != 1
        or not isinstance(manifest["posters"], list)
        or not 1 <= len(manifest["posters"]) <= 36
    ):
        raise ValueError("Invalid public login poster manifest")
    posters = []
    seen = set()
    for entry in manifest["posters"]:
        if not isinstance(entry, dict) or set(entry) != {"file", "sha256", "width", "height"}:
            raise ValueError("Unexpected login poster metadata")
        name = entry["file"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"poster-\d{2}\.jpg", name)
            or name in seen
        ):
            raise ValueError("Invalid public login poster filename")
        asset = POSTER_ROOT / name
        if asset.is_symlink() or hashlib.sha256(asset.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Public login poster differs from its manifest")
        if not (
            isinstance(entry["width"], int)
            and isinstance(entry["height"], int)
            and 1 <= entry["width"] <= 512
            and entry["width"] < entry["height"] <= 1024
        ):
            raise ValueError("Invalid public login poster dimensions")
        seen.add(name)
        posters.append({**entry, "path": f"img/login-posters/{name}"})
    return tuple(posters)
