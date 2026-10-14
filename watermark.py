#!/usr/bin/env python3
"""Add a text watermark to JPEG photos.

Examples
  watermark photo.jpg --text "FOR AIRBNB ONLY"
  watermark ~/Desktop/passport.jpg --text "FOR AIRBNB ONLY 14 OCT 2026" --density 10
  watermark ~/Pictures/flat/ --text "MY FLAT" --style corner
  watermark photo.jpg --text "FOR AIRBNB ONLY" --width 1600          # height keeps the ratio
  watermark photo.jpg --text "FOR AIRBNB ONLY" -W 1080 -H 1080       # both: stretched to exactly 1080x1080

Originals are never touched. Output goes to a "watermarked" folder beside
each input, with metadata (GPS, camera details) stripped.
"""
import argparse
import math
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    sys.exit("Pillow is missing. Run:  python3 -m pip install pillow")

EXTENSIONS = {".jpg", ".jpeg", ".png"}
# Japanese, Chinese and other non-Latin text needs a font that has those characters.
WIDE_FONTS = [
    ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", 0),  # macOS Hiragino Sans
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 0),
    ("C:/Windows/Fonts/YuGothB.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
]
FONTS = [
    ("/System/Library/Fonts/Helvetica.ttc", 1),      # macOS, bold face
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
    ("C:/Windows/Fonts/arialbd.ttf", 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
]


def load_font(px):
    wide = any(ord(c) > 0x2FF for c in TEXT)       # beyond Latin: Japanese, Chinese, etc.
    for path, index in (WIDE_FONTS + FONTS) if wide else FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, px, index=index)
    return ImageFont.load_default(size=px)


TEXT = ""                                          # set in main(), read by load_font()


def colour(name, opacity):
    rgb = {"white": (255, 255, 255), "black": (0, 0, 0), "red": (220, 30, 30)}[name]
    return rgb + (round(255 * opacity),)


def text_tile(text, px, fill, angle):
    """The text on a transparent background, rotated."""
    font = load_font(px)
    left, top, right, bottom = font.getbbox(text)
    pad = px // 4
    tile = Image.new("RGBA", (right - left + 2 * pad, bottom - top + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((pad - left, pad - top), text, font=font, fill=fill)
    return tile.rotate(angle, expand=True, resample=Image.BICUBIC) if angle else tile


def tiled(img, a):
    """`a.density` parallel lines of repeated text, evenly spaced across the photo."""
    w, h = img.size
    tile = text_tile(a.text, round(min(w, h) * a.size), colour(a.color, a.opacity), 0)
    # Draw the lines level on a square big enough to cover the photo at any angle,
    # then rotate it and cut out the middle.
    side = math.ceil(math.hypot(w, h)) + 2 * tile.width
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    rad = math.radians(a.angle)
    across = w * abs(math.sin(rad)) + h * abs(math.cos(rad))   # photo's depth, measured across the lines
    gap = across / a.density
    step_x = round(tile.width * 1.25)
    for i in range(a.density):
        y = round(side / 2 - across / 2 + (i + 0.5) * gap - tile.height / 2)
        shift = (i % 2) * step_x // 2            # stagger alternate lines
        for x in range(-shift, side, step_x):
            canvas.alpha_composite(tile, (x, y))
    canvas = canvas.rotate(a.angle, resample=Image.BICUBIC)
    left, top = (side - w) // 2, (side - h) // 2
    return canvas.crop((left, top, left + w, top + h))


def centre(img, a):
    w, h = img.size
    angle = a.angle if a.angle_set else math.degrees(math.atan2(h, w))
    tile = text_tile(a.text, round(min(w, h) * a.size * 2.5), colour(a.color, a.opacity), angle)
    if tile.width > w:                            # shrink long text to fit
        tile = tile.resize((w, round(tile.height * w / tile.width)), Image.LANCZOS)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.alpha_composite(tile, ((w - tile.width) // 2, (h - tile.height) // 2))
    return layer


def corner(img, a):
    w, h = img.size
    font = load_font(round(min(w, h) * a.size))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = draw.textbbox((0, 0), a.text, font=font)
    margin = round(min(w, h) * 0.03)
    x, y = w - right - margin, h - bottom - margin
    shadow = 2 + font.size // 40
    draw.text((x + shadow, y + shadow), a.text, font=font, fill=(0, 0, 0, round(255 * a.opacity * 0.7)))
    draw.text((x, y), a.text, font=font, fill=colour(a.color, a.opacity))
    return layer


def banner(img, a):
    w, h = img.size
    font = load_font(round(min(w, h) * a.size))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    left, top, right, bottom = draw.textbbox((0, 0), a.text, font=font)
    band = round((bottom - top) * 2.2)
    draw.rectangle((0, h - band, w, h), fill=(0, 0, 0, round(255 * min(1, a.opacity * 0.6))))
    draw.text(((w - (right - left)) // 2 - left, h - band + (band - (bottom - top)) // 2 - top),
              a.text, font=font, fill=colour(a.color, max(a.opacity, 0.85)))
    return layer


STYLES = {"tiled": tiled, "centre": centre, "corner": corner, "banner": banner}
# Defaults per style: (text size as a fraction of the short side, opacity)
STYLE_DEFAULTS = {"tiled": (0.05, 0.28), "centre": (0.05, 0.35),
                  "corner": (0.045, 0.8), "banner": (0.05, 0.9)}


def resize(im, width, height):
    """One of width/height keeps the aspect ratio; both stretch to exactly that size."""
    if not width and not height:
        return im
    w, h = im.size
    if width and height:
        size = (width, height)
    elif width:
        size = (width, max(1, round(h * width / w)))
    else:
        size = (max(1, round(w * height / h)), height)
    return im.resize(size, Image.LANCZOS)


def watermark(src, dest, a):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)          # respect phone rotation
        if im.mode in ("RGBA", "LA") or "transparency" in im.info:
            flat = Image.new("RGBA", im.size, (255, 255, 255, 255))   # see-through parts become white
            im = Image.alpha_composite(flat, im.convert("RGBA"))
        base = resize(im, a.width, a.height).convert("RGBA")   # resize first, so the text scales to the final size
    out = Image.alpha_composite(base, STYLES[a.style](base, a)).convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest, "JPEG", quality=a.quality, optimize=True)   # no EXIF: GPS stripped


def collect(paths):
    files = []
    for p in map(Path, paths):
        p = p.expanduser()
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in EXTENSIONS)
        elif p.is_file() and p.suffix.lower() in EXTENSIONS:
            files.append(p)
        else:
            print(f"skipped (not a JPEG/PNG or not found): {p}", file=sys.stderr)
    return files


def main():
    ap = argparse.ArgumentParser(
        description="Add a text watermark to JPEG photos. Originals are never changed.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split("Examples", 1)[1])
    ap.add_argument("inputs", nargs="+", help="photos or folders of photos")
    ap.add_argument("-t", "--text", required=True, help="watermark text (required)")
    ap.add_argument("-s", "--style", choices=STYLES, default="tiled", help="default: tiled")
    ap.add_argument("-d", "--density", type=int, default=6,
                    help="tiled only: number of lines of text across the photo, 1–30 (default 6)")
    ap.add_argument("-o", "--opacity", type=float, help="0.05–1.0 (style default if omitted)")
    ap.add_argument("--size", type=float, help="text height as a fraction of the short side, e.g. 0.05")
    ap.add_argument("--angle", type=float, help="degrees; tiled default 30, centre follows the diagonal")
    ap.add_argument("--color", choices=["white", "black", "red"], default="white")
    ap.add_argument("-W", "--width", type=int,
                    help="output width in px. Alone: height follows the aspect ratio. With --height: stretched")
    ap.add_argument("-H", "--height", type=int,
                    help="output height in px. Alone: width follows the aspect ratio. With --width: stretched")
    ap.add_argument("--out", help="output folder (default: a 'watermarked' folder beside each photo)")
    ap.add_argument("--suffix", default="_wm", help="added to each filename, default _wm")
    ap.add_argument("--quality", type=int, default=92, help="JPEG quality, default 92")
    a = ap.parse_args()

    size, opacity = STYLE_DEFAULTS[a.style]
    a.size = a.size or size
    a.opacity = min(1.0, max(0.05, a.opacity if a.opacity is not None else opacity))
    if not 1 <= a.density <= 30:
        ap.error("--density is the number of lines of text, 1 to 30")
    for name in ("width", "height"):
        if getattr(a, name) is not None and getattr(a, name) < 1:
            ap.error(f"--{name} must be a positive number of pixels")
    a.angle_set = a.angle is not None
    if a.angle is None:
        a.angle = 30 if a.style == "tiled" else 0

    global TEXT
    TEXT = a.text
    files = collect(a.inputs)
    if not files:
        sys.exit("No JPEG or PNG files found.")
    for src in files:
        folder = Path(a.out).expanduser() if a.out else src.parent / "watermarked"
        dest = folder / f"{src.stem}{a.suffix}.jpg"
        try:
            watermark(src, dest, a)
            print(f"✓ {dest}")
        except Exception as e:                    # keep going on a bad file
            print(f"✗ {src}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
