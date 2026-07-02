from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "reports" / "demo-screenshots"


def test_demo_screenshots_are_public_safe_artifacts() -> None:
    expected = {
        "library-grid.png",
        "review-flags.png",
        "flic-ranked-list.png",
    }

    for filename in expected:
        path = SCREENSHOT_DIR / filename
        assert path.exists(), f"missing demo screenshot: {filename}"
        with Image.open(path) as image:
            width, height = image.size
        assert width >= 1200
        assert height >= 900

    readme = (SCREENSHOT_DIR / "README.md").read_text(encoding="utf-8")
    assert "temporary SQLite database" in readme
    assert "fictional demo titles" in readme
    assert "personal profile names" in readme
