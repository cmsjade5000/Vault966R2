import hashlib
import json

import pytest

from api.services import login_posters as artwork


@pytest.mark.parametrize("change", ["path", "hash", "metadata", "duplicate"])
def test_login_artwork_manifest_rejects_unsafe_or_changed_assets(tmp_path, monkeypatch, change):
    data = b"synthetic poster bytes"
    (tmp_path / "poster-01.jpg").write_bytes(data)
    entry = {
        "file": "poster-01.jpg",
        "sha256": hashlib.sha256(data).hexdigest(),
        "width": 342,
        "height": 513,
    }
    entries = [entry]
    if change == "path":
        entry["file"] = "../private.jpg"
    elif change == "hash":
        entry["sha256"] = "0" * 64
    elif change == "metadata":
        entry["movie_id"] = 1
    else:
        entries.append(entry.copy())
    (tmp_path / "manifest.json").write_text(json.dumps({"format": 1, "posters": entries}))
    monkeypatch.setattr(artwork, "POSTER_ROOT", tmp_path)
    artwork.login_posters.cache_clear()
    try:
        with pytest.raises(ValueError):
            artwork.login_posters()
    finally:
        artwork.login_posters.cache_clear()
