"""
A square grid of the most played album covers of a period, shown in the statistics. Needs Pillow.
"""

from __future__ import annotations

from pathlib import Path

import artwork

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

COLUMNS = 3
# Pixels per cover before the grid is scaled to the screen; covers are stored at 300px
CELL = 300
# Covers whose 8x8 fingerprints differ in at most this many of 64 points count as the same picture
SAME_COVER_DISTANCE = 6
EMPTY = "#262a31"
MUTED = "#9aa1ab"
BOLD_FONTS = ("seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf")


def _font(size: int):
    for name in BOLD_FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _cover(path: Path | None, title: str, size: int):
    if path and path.exists():
        try:
            image = Image.open(path).convert("RGB")
            side = min(image.size)
            left, top = (image.width - side) // 2, (image.height - side) // 2
            return image.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
        except OSError:
            pass
    # No cover yet: a neutral tile with the album's first letter
    tile = Image.new("RGB", (size, size), EMPTY)
    draw = ImageDraw.Draw(tile)
    draw.text((size / 2, size / 2), (title.strip()[:1] or "♪").upper(), fill=MUTED,
              font=_font(size // 3), anchor="mm")
    return tile


def _fingerprint(path: Path | None) -> int | None:
    """An average hash: which of 8x8 gray squares are lighter than the mean."""
    if not path or not path.exists():
        return None
    try:
        pixels = list(Image.open(path).convert("L").resize((8, 8), Image.LANCZOS).getdata())
    except OSError:
        return None
    mean = sum(pixels) / len(pixels)
    return sum(1 << index for index, value in enumerate(pixels) if value > mean)


def distinct(albums: list[dict], count: int) -> list[dict]:
    """Keep the first count albums, skipping ones with the same cover as one of the same artist kept before
    (a single and the album it is from often share their cover). Different artists are never compared:
    at 8x8 two unrelated covers can look alike."""
    kept, prints = [], []
    for album in albums:
        fingerprint = _fingerprint(album["cover"])
        if fingerprint is not None and any(artist == album["artist_key"]
                                           and bin(fingerprint ^ other).count("1") <= SAME_COVER_DISTANCE
                                           for artist, other in prints):
            continue
        if fingerprint is not None:
            prints.append((album["artist_key"], fingerprint))
        kept.append(album)
        if len(kept) == count:
            break
    return kept


def build(albums: list[dict], columns: int, side: int):
    """A side x side picture; albums: dicts with cover (a path or None) and album, missing places stay empty."""
    width = CELL * columns
    image = Image.new("RGB", (width, width), EMPTY)
    for index, album in enumerate(albums[:columns * columns]):
        image.paste(_cover(album["cover"], album["album"], CELL), (index % columns * CELL, index // columns * CELL))
    return image.resize((side, side), Image.LANCZOS)


available = Image is not None and artwork.available
