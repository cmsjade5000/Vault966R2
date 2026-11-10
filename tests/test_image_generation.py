"""Exercise image generation with synthetic inputs and temporary outputs only."""

from io import BytesIO
import random

from PIL import Image
import pytest

from scripts import generate_brand_assets as brand
from scripts import generate_ipad_wallpapers as wallpapers


def test_brand_assets_encode_every_supported_icon_and_splash(tmp_path):
    source = tmp_path / "source.png"
    Image.new("RGBA", (32, 16), (220, 40, 80, 255)).save(source)
    output = tmp_path / "assets"

    brand.generate_assets(
        icon_source=source,
        splash_source=source,
        output_dir=output,
        background=(5, 10, 15),
        include_splash=True,
    )

    assert {p.name for p in output.iterdir()} == {
        name for name, _ in brand.ICON_TARGETS + brand.SPLASH_TARGETS
    }
    for name, size in brand.ICON_TARGETS + brand.SPLASH_TARGETS:
        with Image.open(output / name) as result:
            result.load()
            assert result.format == "PNG"
            assert result.size == size
            if name.startswith("splash-"):
                assert result.mode == "RGB"
                assert result.getpixel((0, 0)) == (5, 10, 15)
                assert result.getpixel((size[0] // 2, size[1] // 2)) == (220, 40, 80)
            else:
                assert result.mode == "RGBA"
                assert result.getpixel((size[0] // 2, size[1] // 2)) == (220, 40, 80, 255)


def test_brand_icon_preserves_transparency_and_splash_composites_it():
    source = Image.new("RGBA", (4, 4), (200, 100, 50, 0))
    icon = brand.resize_icon(source, (16, 16))
    assert icon.getchannel("A").getextrema() == (0, 0)
    splash = brand.render_splash(source, (24, 16), (5, 10, 15))
    assert splash.mode == "RGB"
    assert splash.getextrema() == ((5, 5), (10, 10), (15, 15))


@pytest.mark.parametrize("image_format,mode", [("JPEG", "RGB"), ("PNG", "RGBA")])
def test_wallpaper_fetch_decodes_poster_bytes_without_network(monkeypatch, image_format, mode):
    encoded = BytesIO()
    Image.new(mode, (24, 36), "red").save(encoded, format=image_format)
    monkeypatch.setattr(
        wallpapers.urllib.request, "urlopen", lambda *args, **kwargs: BytesIO(encoded.getvalue())
    )
    result = wallpapers.fetch_poster("https://example.invalid/poster")
    assert result is not None
    assert result.mode == "RGB"
    assert result.size == (24, 36)
    red, green, blue = result.getpixel((12, 18))
    assert red >= 250 and green <= 5 and blue <= 5


def test_wallpaper_fetch_rejects_invalid_image_bytes(monkeypatch):
    monkeypatch.setattr(
        wallpapers.urllib.request, "urlopen", lambda *args, **kwargs: BytesIO(b"not an image")
    )
    assert wallpapers.fetch_poster("https://example.invalid/poster") is None


def test_wallpaper_cover_resize_keeps_center_and_rounded_mask_keeps_corners_clear():
    source = Image.new("RGB", (60, 20), "red")
    source.paste("green", (20, 0, 40, 20))
    cropped = wallpapers.cover_resize(source, (20, 20))
    assert cropped.size == (20, 20)
    assert cropped.getextrema() == ((0, 0), (128, 128), (0, 0))
    mask = wallpapers.rounded_mask((30, 40), 8)
    assert mask.getpixel((0, 0)) == 0
    assert mask.getpixel((15, 20)) == 255


def test_wallpaper_full_size_compositing_rotation_blur_and_png_round_trip(tmp_path):
    posters = [Image.new("RGB", (80, 120), (220, 30 + i * 15, 40)) for i in range(12)]
    result = wallpapers.build_wallpaper(posters, random.Random(966))
    empty = wallpapers.build_wallpaper([], random.Random(966))
    assert result.size == (2048, 1536)
    assert result.mode == "RGB"
    assert result.tobytes() != empty.tobytes()
    assert all(low < high for low, high in result.getextrema())
    output = tmp_path / "wallpaper.png"
    result.save(output, optimize=True)
    with Image.open(output) as decoded:
        decoded.load()
        assert decoded.format == "PNG"
        assert decoded.mode == "RGB"
        assert decoded.size == (2048, 1536)
        assert decoded.tobytes() == result.tobytes()
