import json
from pathlib import Path

from scripts.generate_brand_assets import ICON_TARGETS, SPLASH_TARGETS


ROOT = Path(__file__).resolve().parents[1]
GENERATED_ICON_FILES = {filename for filename, _ in ICON_TARGETS}
GENERATED_SPLASH_FILES = {filename for filename, _ in SPLASH_TARGETS}
PWA_SOURCE_FILES = {"app-icon.png", "splash-1024.png"}
PROFILE_IMAGE_FILES = {"profile-user-a.png", "profile-user-b.png"}


def test_manifest_targets_landscape_standalone_mode() -> None:
    manifest = json.loads((ROOT / "static/site.webmanifest").read_text(encoding="utf-8"))

    assert manifest["display"] == "standalone"
    assert manifest["orientation"] == "landscape"
    assert manifest["start_url"] == "/ui/movies"


def test_ipad_air_2_landscape_startup_image_is_available() -> None:
    template = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    image = ROOT / "static/img/splash-2048x1536.png"

    assert image.is_file()
    assert "splash-2048x1536.png" in template
    assert "(device-width: 1024px) and (device-height: 768px)" in template


def test_generated_pwa_asset_set_matches_policy() -> None:
    image_files = {path.name for path in (ROOT / "static/img").glob("*.png")}

    assert image_files == (
        GENERATED_ICON_FILES | GENERATED_SPLASH_FILES | PWA_SOURCE_FILES | PROFILE_IMAGE_FILES
    )


def test_manifest_icons_match_generated_policy() -> None:
    manifest = json.loads((ROOT / "static/site.webmanifest").read_text(encoding="utf-8"))

    assert {Path(icon["src"]).name for icon in manifest["icons"]} == {
        "android-chrome-192x192.png",
        "android-chrome-512x512.png",
    }


def test_ipad_startup_images_match_generated_policy() -> None:
    template = (ROOT / "templates/base.html").read_text(encoding="utf-8")

    for filename in GENERATED_SPLASH_FILES:
        assert filename in template


def test_library_script_keeps_filter_handlers_inside_initializer() -> None:
    script = (ROOT / "static/js/library_page.js").read_text(encoding="utf-8")

    assert 'document.addEventListener("DOMContentLoaded", () => {' in script
    assert '.querySelector("[data-filters-open]")' in script
    assert '?.addEventListener("click", openFilters);' in script
    assert script.rstrip().endswith("})();")


def test_coarse_pointer_controls_include_filter_and_preference_targets() -> None:
    movies_css = (ROOT / "static/css/movies.css").read_text(encoding="utf-8")
    detail_css = (ROOT / "static/css/movie_detail.css").read_text(encoding="utf-8")

    coarse_rules = movies_css.split("@media (pointer: coarse)", 1)[1]
    assert '.custom-range input[type="number"]' in coarse_rules
    assert ".preference-icon" in coarse_rules
    assert "min-height: 44px" in coarse_rules

    detail_coarse_rules = detail_css.split("@media (pointer: coarse)", 1)[1]
    assert ".back-link" in detail_coarse_rules
    assert ".badge-link" in detail_coarse_rules
    assert "min-height: 44px" in detail_coarse_rules


def test_movie_detail_does_not_break_sticky_navigation_with_root_overflow() -> None:
    detail_css = (ROOT / "static/css/movie_detail.css").read_text(encoding="utf-8")

    assert "html, body" not in detail_css


def test_movie_detail_provenance_is_a_collapsed_vault_history_section() -> None:
    template = (ROOT / "templates/movie_detail.html").read_text(encoding="utf-8")

    assert '<details class="section-card section-card--wide provenance-section">' in template
    assert "<span>Vault History</span>" in template
    assert "<h2>Vault provenance</h2>" not in template
    assert (
        '<details class="section-card section-card--wide provenance-section" open>' not in template
    )


def test_ipad_filter_apply_button_does_not_use_cyclic_percentage_height() -> None:
    movies_css = (ROOT / "static/css/movies.css").read_text(encoding="utf-8")
    ipad_rules = movies_css.split("@media (min-width: 761px) and (max-width: 1100px)", 1)[1]
    apply_rule = ipad_rules.split(".library-page .filters-apply", 1)[1].split("}", 1)[0]

    assert "align-self: start" in apply_rule
    assert "height: 44px" in apply_rule
    assert "max-height: 44px" in apply_rule
    assert "min-height: 44px" in apply_rule
    assert "min-height: 100%" not in apply_rule
