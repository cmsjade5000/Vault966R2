from scripts.cache_posters import _selected_sizes, build_jobs


def test_selected_sizes_are_whitelisted_and_deduplicated() -> None:
    assert _selected_sizes("w185,w342,w185") == ["w185", "w342"]

    try:
        _selected_sizes("original")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected unsupported size rejection")


def test_build_jobs_skips_cached_and_unsupported(tmp_path) -> None:
    rows = [
        (1, "https://image.tmdb.org/t/p/w500/one.jpg"),
        (2, "https://example.com/two.jpg"),
    ]
    first_jobs, cached, unsupported = build_jobs(rows, ["w185"], tmp_path)
    assert len(first_jobs) == 1
    assert cached == 0
    assert unsupported == 1

    _source_url, stem = first_jobs[0]
    (tmp_path / f"{stem}.jpg").write_bytes(b"cached")
    second_jobs, cached, unsupported = build_jobs(rows, ["w185"], tmp_path)
    assert second_jobs == []
    assert cached == 1
    assert unsupported == 1
