import httpx

from scripts import cache_posters as cache_posters_script
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


def test_cache_worker_does_not_print_secret_bearing_httpx_failure(
    tmp_path, monkeypatch, capsys
) -> None:
    sentinel = "SENTINEL_CACHE_POSTERS_SECRET"

    def fail_download(source_url, cache_dir, stem, *, client):
        request = httpx.Request(
            "GET",
            source_url,
            params={"api_key": sentinel, "size": "w185"},
        )
        response = httpx.Response(503, request=request)
        response.raise_for_status()

    monkeypatch.setattr(cache_posters_script, "download_poster", fail_download)

    completed, failed = cache_posters_script.cache_posters(
        [("https://image.tmdb.org/t/p/w185/example.jpg", "poster-stem")],
        tmp_path,
        workers=1,
    )
    captured = capsys.readouterr()
    output = captured.out + captured.err

    assert (completed, failed) == (0, 1)
    assert sentinel not in output
    assert "downloaded=0 failed=1" in output
