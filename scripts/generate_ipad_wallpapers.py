from __future__ import annotations

import argparse
import random
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


WIDTH = 2048
HEIGHT = 1536
SLOTS = [
    {"top": 0.08, "left": 0.06, "rotate": -5},
    {"top": 0.31, "left": 0.15, "rotate": 3},
    {"top": 0.10, "left": 0.82, "rotate": 4},
    {"top": 0.40, "left": 0.76, "rotate": -3},
    {"top": 0.69, "left": 0.05, "rotate": 4},
    {"top": 0.76, "left": 0.25, "rotate": -2},
    {"top": 0.73, "left": 0.68, "rotate": 3},
    {"top": 0.63, "left": 0.88, "rotate": -5},
    {"top": -0.03, "left": 0.29, "rotate": 2},
    {"top": 0.04, "left": 0.65, "rotate": -2},
    {"top": 0.84, "left": 0.47, "rotate": 4},
    {"top": 0.30, "left": 0.91, "rotate": 2},
]


def poster_urls(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT poster_url
            FROM movies
            WHERE poster_url IS NOT NULL
              AND TRIM(poster_url) != ''
            """
        ).fetchall()
    return [row[0] for row in rows]


def poster_request_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme == "https" and parsed.hostname in {
        "image.tmdb.org",
        "media.themoviedb.org",
    }:
        parts = parsed.path.split("/")
        if len(parts) >= 5 and parts[1:3] == ["t", "p"]:
            parts[3] = "w500"
            return urllib.parse.urlunsplit(
                ("https", "image.tmdb.org", "/".join(parts), parsed.query, "")
            )
    return url


def fetch_poster(url: str, *, timeout: float = 15) -> Image.Image | None:
    request = urllib.request.Request(
        poster_request_url(url),
        headers={"User-Agent": "Vault966WallpaperGenerator/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError):
        return None

    try:
        return Image.open(BytesIO(data)).convert("RGB")
    except OSError:
        return None


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = image.resize(
        (round(src_w * scale), round(src_h * scale)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def paste_poster(
    canvas: Image.Image,
    poster: Image.Image,
    *,
    top: float,
    left: float,
    rotate: int,
) -> None:
    poster_w = round(WIDTH * 0.10)
    poster_h = round(poster_w * 1.48)
    radius = round(poster_w * 0.08)
    border = max(2, round(WIDTH * 0.0012))

    image = cover_resize(poster, (poster_w, poster_h))
    image = Image.blend(image, Image.new("RGB", image.size, (5, 12, 24)), 0.08)
    image = Image.eval(image, lambda value: min(255, round(value * 0.92)))

    poster_rgba = Image.new("RGBA", (poster_w, poster_h), (0, 0, 0, 0))
    poster_rgba.paste(image, (0, 0), rounded_mask((poster_w, poster_h), radius))

    border_layer = Image.new("RGBA", (poster_w, poster_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(border_layer)
    draw.rounded_rectangle(
        (border // 2, border // 2, poster_w - border, poster_h - border),
        radius=radius,
        outline=(183, 236, 255, 82),
        width=border,
    )
    poster_rgba = Image.alpha_composite(poster_rgba, border_layer)

    shadow = Image.new("RGBA", poster_rgba.size, (0, 0, 0, 0))
    shadow_mask = rounded_mask(poster_rgba.size, radius).filter(ImageFilter.GaussianBlur(22))
    shadow.paste((0, 0, 0, 130), (0, 0), shadow_mask)

    rotated_shadow = shadow.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)
    rotated = poster_rgba.rotate(rotate, expand=True, resample=Image.Resampling.BICUBIC)

    x = round(WIDTH * left)
    y = round(HEIGHT * top)
    canvas.alpha_composite(rotated_shadow, (x + 10, y + 22))
    canvas.alpha_composite(rotated, (x, y))


def add_overlays(canvas: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for y in range(HEIGHT):
        top_alpha = int(max(0, 95 * (1 - y / (HEIGHT * 0.42))))
        bottom_alpha = int(max(0, 145 * ((y - HEIGHT * 0.58) / (HEIGHT * 0.42))))
        side_alpha = 0
        draw.line((0, y, WIDTH, y), fill=(3, 7, 18, max(top_alpha, bottom_alpha, side_alpha)))

    for x in range(WIDTH):
        edge = min(x, WIDTH - x) / (WIDTH * 0.24)
        alpha = int(135 * max(0, 1 - edge))
        if alpha:
            draw.line((x, 0, x, HEIGHT), fill=(3, 7, 18, alpha))

    vignette = Image.new("L", (WIDTH, HEIGHT), 0)
    vignette_draw = ImageDraw.Draw(vignette)
    vignette_draw.ellipse(
        (-round(WIDTH * 0.12), -round(HEIGHT * 0.08), round(WIDTH * 1.12), round(HEIGHT * 1.12)),
        fill=185,
    )
    vignette = Image.eval(
        vignette.filter(ImageFilter.GaussianBlur(80)), lambda value: 150 - min(150, value)
    )
    overlay.alpha_composite(
        Image.merge(
            "RGBA",
            [
                Image.new("L", (WIDTH, HEIGHT), 3),
                Image.new("L", (WIDTH, HEIGHT), 7),
                Image.new("L", (WIDTH, HEIGHT), 18),
                vignette,
            ],
        )
    )

    center_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(center_glow)
    glow_draw.ellipse(
        (round(WIDTH * 0.18), round(HEIGHT * 0.08), round(WIDTH * 0.82), round(HEIGHT * 0.72)),
        fill=(50, 139, 192, 30),
    )
    center_glow = center_glow.filter(ImageFilter.GaussianBlur(90))

    return Image.alpha_composite(Image.alpha_composite(canvas, center_glow), overlay)


def build_wallpaper(posters: list[Image.Image], rng: random.Random) -> Image.Image:
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (3, 7, 18, 255))
    for slot, poster in zip(SLOTS, posters):
        paste_poster(canvas, poster, **slot)
    return add_overlays(canvas).convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--db",
        type=Path,
        default=Path.home() / "Library/Application Support/Vault966/data/vault.db",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path.home()
        / "Library/Application Support/Vault966/wallpapers/ipad-air-2-landscape",
    )
    parser.add_argument("--count", type=int, default=48)
    parser.add_argument("--seed", type=int, default=int(time.time()))
    args = parser.parse_args()

    urls = poster_urls(args.db)
    if len(urls) < len(SLOTS):
        raise SystemExit(f"Need at least {len(SLOTS)} poster URLs; found {len(urls)}")

    args.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    cache: dict[str, Image.Image] = {}
    generated = 0
    attempts = 0
    max_attempts = args.count * 8

    while generated < args.count and attempts < max_attempts:
        attempts += 1
        selected_urls = rng.sample(urls, len(SLOTS))
        posters: list[Image.Image] = []
        for url in selected_urls:
            if url not in cache:
                image = fetch_poster(url)
                if image is not None:
                    cache[url] = image
            if url in cache:
                posters.append(cache[url])
        if len(posters) != len(SLOTS):
            continue

        generated += 1
        image = build_wallpaper(posters, rng)
        filename = args.out / f"vault966-ipad-air-2-landscape-{generated:02d}.png"
        image.save(filename, optimize=True)
        print(f"wrote {filename}")

    if generated != args.count:
        raise SystemExit(f"Generated {generated} wallpapers after {attempts} attempts")
    print(f"Generated {generated} wallpapers at {WIDTH}x{HEIGHT} in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
