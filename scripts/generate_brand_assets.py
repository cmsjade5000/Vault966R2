"""Regenerate favicon/icon/splash assets from a single source image.

Usage:
    python scripts/generate_brand_assets.py \
        --icon-source static/img/app-icon.png \
        --splash-source static/img/splash-1024.png \
        --output-dir static/img

Requires Pillow. Install with ``pip install Pillow``.
"""

from __future__ import annotations

import argparse
import pathlib
from typing import Tuple

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit("Pillow is required. Install with `pip install Pillow`. ") from exc

ICON_TARGETS = [
    ("android-chrome-192x192.png", (192, 192)),
    ("android-chrome-512x512.png", (512, 512)),
    ("app-icon.png", (1024, 1024)),
    ("app-icon-76.png", (76, 76)),
    ("app-icon-120.png", (120, 120)),
    ("app-icon-152.png", (152, 152)),
    ("app-icon-167.png", (167, 167)),
    ("app-icon-180.png", (180, 180)),
    ("app-icon-512.png", (512, 512)),
    ("apple-touch-icon.png", (180, 180)),
    ("apple-touch-icon-precomposed.png", (180, 180)),
    ("logo-48.png", (48, 48)),
    ("logo-72.png", (72, 72)),
    ("logo-180.png", (180, 180)),
]

SPLASH_TARGETS = [
    ("splash-512.png", (512, 512)),
    ("splash-640x640.png", (640, 640)),
    ("splash-1024.png", (1024, 1024)),
    ("splash-1024x1024.png", (1024, 1024)),
    ("splash-1125x2436.png", (1125, 2436)),
    ("splash-1136x640.png", (1136, 640)),
    ("splash-1170x2532.png", (1170, 2532)),
    ("splash-1242x2688.png", (1242, 2688)),
    ("splash-1280x1920.png", (1280, 1920)),
    ("splash-1284x2778.png", (1284, 2778)),
    ("splash-1334x750.png", (1334, 750)),
    ("splash-1536x2048.png", (1536, 2048)),
    ("splash-1600x960.png", (1600, 960)),
    ("splash-1620x2160.png", (1620, 2160)),
    ("splash-1668x2224.png", (1668, 2224)),
    ("splash-1668x2388.png", (1668, 2388)),
    ("splash-1792x828.png", (1792, 828)),
    ("splash-1920x1280.png", (1920, 1280)),
    ("splash-2048x1536.png", (2048, 1536)),
    ("splash-2048x2732.png", (2048, 2732)),
    ("splash-2160x1620.png", (2160, 1620)),
    ("splash-2224x1668.png", (2224, 1668)),
    ("splash-2388x1668.png", (2388, 1668)),
    ("splash-2436x1125.png", (2436, 1125)),
    ("splash-2532x1170.png", (2532, 1170)),
    ("splash-2688x1242.png", (2688, 1242)),
    ("splash-2732x2048.png", (2732, 2048)),
    ("splash-2778x1284.png", (2778, 1284)),
    ("splash-640x1136.png", (640, 1136)),
    ("splash-750x1334.png", (750, 1334)),
    ("splash-828x828.png", (828, 828)),
    ("splash-828x1792.png", (828, 1792)),
    ("splash-960x1600.png", (960, 1600)),
]


def parse_color(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) not in (6, 8):
        raise ValueError("Color must be a hex string like #RRGGBB or #RRGGBBAA")
    if len(value) == 8:
        value = value[:6]
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return r, g, b


def ensure_dir(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def resize_icon(source: Image.Image, size: Tuple[int, int]) -> Image.Image:
    return source.resize(size, Image.LANCZOS)


def render_splash(
    source: Image.Image, size: Tuple[int, int], background: Tuple[int, int, int]
) -> Image.Image:
    canvas = Image.new("RGBA", size, background + (255,))
    scale = min(size[0] / source.width, size[1] / source.height)
    scaled_size = (max(1, int(source.width * scale)), max(1, int(source.height * scale)))
    content = source.resize(scaled_size, Image.LANCZOS)
    offset = ((size[0] - scaled_size[0]) // 2, (size[1] - scaled_size[1]) // 2)
    canvas.paste(content, offset, mask=content if content.mode == "RGBA" else None)
    return canvas.convert("RGB")


def generate_assets(
    *,
    icon_source: pathlib.Path,
    splash_source: pathlib.Path,
    output_dir: pathlib.Path,
    background: Tuple[int, int, int],
    include_splash: bool,
) -> None:
    icon_base = Image.open(icon_source).convert("RGBA")
    splash_base = Image.open(splash_source).convert("RGBA")

    for filename, size in ICON_TARGETS:
        target_path = output_dir / filename
        ensure_dir(target_path)
        resize_icon(icon_base, size).save(target_path)
        print(f"wrote {target_path}")

    if include_splash:
        for filename, size in SPLASH_TARGETS:
            target_path = output_dir / filename
            ensure_dir(target_path)
            render_splash(splash_base, size, background).save(target_path)
            print(f"wrote {target_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate icon and splash assets")
    parser.add_argument("--icon-source", required=True, type=pathlib.Path)
    parser.add_argument("--splash-source", required=True, type=pathlib.Path)
    parser.add_argument(
        "--output-dir",
        default=pathlib.Path("static/img"),
        type=pathlib.Path,
        help="Directory to write generated assets",
    )
    parser.add_argument(
        "--background",
        default="#050505",
        help="Background color for splash screens (hex)",
    )
    parser.add_argument(
        "--skip-splash",
        action="store_true",
        help="Only generate icons",
    )
    args = parser.parse_args()

    background = parse_color(args.background)
    generate_assets(
        icon_source=args.icon_source,
        splash_source=args.splash_source,
        output_dir=args.output_dir,
        background=background,
        include_splash=not args.skip_splash,
    )


if __name__ == "__main__":
    main()
