"""
A square grid of the most played album covers of a period, with a caption strip below,
to look at in the statistics and save as a picture. Needs Pillow.
"""

from __future__ import annotations

from pathlib import Path

import artwork

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

SIZES = (3, 4, 5)
# Pixels per cover in the saved picture; covers are stored at 300px
CELL = 300
CAPTION_HEIGHT = 120
# Covers whose 8x8 fingerprints differ in at most this many of 64 points count as the same picture
SAME_COVER_DISTANCE = 6
BACKGROUND = "#121417"
EMPTY = "#262a31"
TEXT = "#e6e8eb"
MUTED = "#9aa1ab"
FONT_FILES = {"regular": ("segoeui.ttf", "DejaVuSans.ttf", "Arial.ttf"),
              "bold": ("seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf")}


def _font(kind: str, size: int):
    for name in FONT_FILES[kind]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit(draw, text: str, font, width: int) -> str:
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text + "…"


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
              font=_font("bold", size // 3), anchor="mm")
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


def build(albums: list[dict], columns: int, title: str, subtitle: str):
    """albums: dicts with cover (a path or None) and album; missing places stay empty."""
    width = CELL * columns
    image = Image.new("RGB", (width, width + CAPTION_HEIGHT), BACKGROUND)
    for index in range(columns * columns):
        x, y = index % columns * CELL, index // columns * CELL
        if index < len(albums):
            image.paste(_cover(albums[index]["cover"], albums[index]["album"], CELL), (x, y))
        else:
            ImageDraw.Draw(image).rectangle((x, y, x + CELL - 1, y + CELL - 1), fill=EMPTY)
    draw = ImageDraw.Draw(image)
    margin = CELL // 8
    title_font, subtitle_font = _font("bold", 40), _font("regular", 28)
    draw.text((margin, width + 28), _fit(draw, title, title_font, width - 2 * margin), fill=TEXT, font=title_font)
    draw.text((margin, width + 76), _fit(draw, subtitle, subtitle_font, width - 2 * margin), fill=MUTED,
              font=subtitle_font)
    return image


available = Image is not None and artwork.available
