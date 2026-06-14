import re

import pytest

from api.services.ui.templates import _asset_version


def test_static_asset_versions_are_content_fingerprints() -> None:
    version = _asset_version("css/base.css")

    assert re.fullmatch(r"[0-9a-f]{12}", version)
    assert version == _asset_version("css/base.css")


@pytest.mark.parametrize(
    "path",
    ["../pyproject.toml", "img/apple-touch-icon.png", "/etc/passwd"],
)
def test_static_asset_versions_reject_unsupported_paths(path: str) -> None:
    with pytest.raises(ValueError):
        _asset_version(path)
