"""Tests for watermark.py. Run with:  pytest

Every test makes its own images, so no sample photos are needed.
"""
import hashlib
import struct
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageCms

SCRIPT = Path(__file__).resolve().parent.parent / "watermark.py"
STYLES = ["tiled", "centre", "corner", "banner"]


def run(*args):
    """Run the CLI the way a user would."""
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8")


def photo(path, size=(600, 400), colour=(70, 120, 170)):
    """A plain JPEG with a gradient, so a watermark has something to change."""
    im = Image.new("RGB", size, colour)
    for x in range(size[0]):
        im.putpixel((x, 0), (x % 256, 0, 0))
    im.save(path, quality=95)
    return path


def phone_photo(path):
    """Like a phone shot: stored sideways with an Orientation tag, GPS, XMP and a colour profile."""
    exif = Image.Exif()
    exif[0x0112] = 6                                          # rotate 90° to display
    exif[0x010F] = "PhoneMaker"                               # camera make
    exif[0x8825] = {1: "S", 2: (37.0, 49.0, 12.0), 3: "E", 4: (144.0, 58.0, 0.0)}   # GPS
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (400, 300), (200, 80, 80)).save(path, exif=exif.tobytes(), icc_profile=icc)
    # Add an XMP packet carrying a location, the way some apps do.
    xmp = (b"http://ns.adobe.com/xap/1.0/\x00"
           b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
           b'<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="37,49.2S"/>'
           b"</rdf:RDF></x:xmpmeta>")
    data = path.read_bytes()
    segment = b"\xff\xe1" + struct.pack(">H", len(xmp) + 2) + xmp
    path.write_bytes(data[:2] + segment + data[2:])
    return path


def out_of(tmp_path, name):
    return tmp_path / "watermarked" / f"{name}_wm.jpg"


@pytest.mark.parametrize("style", STYLES)
def test_each_style_writes_a_changed_jpeg(tmp_path, style):
    src = photo(tmp_path / "p.jpg")
    r = run(src, "-t", "FOR AIRBNB ONLY", "-s", style)
    assert r.returncode == 0, r.stderr
    out = Image.open(out_of(tmp_path, "p"))
    assert out.format == "JPEG" and out.size == (600, 400)
    before = Image.open(src).convert("RGB")
    assert sum(abs(a - b) for a, b in zip(out.tobytes(), before.tobytes())) > 10_000


@pytest.mark.parametrize("lines", [1, 4, 7])
def test_density_is_the_number_of_lines(tmp_path, lines):
    src = tmp_path / "black.jpg"
    Image.new("RGB", (1200, 800), (0, 0, 0)).save(src, quality=95)
    r = run(src, "-t", "IIIIIIII", "-d", lines, "--angle", 0, "--opacity", 1)
    assert r.returncode == 0, r.stderr
    out = Image.open(out_of(tmp_path, "black")).convert("L")
    w, h = out.size
    px = out.load()
    lit = [max(px[x, y] for x in range(0, w, 2)) > 128 for y in range(h)]
    bands = sum(1 for y in range(1, h) if lit[y] and not lit[y - 1]) + lit[0]
    assert bands == lines


@pytest.mark.parametrize("args, size", [
    ([], (600, 400)),                       # neither: unchanged
    (["-W", 300], (300, 200)),              # width only: keeps ratio
    (["-H", 100], (150, 100)),              # height only: keeps ratio
    (["-W", 250, "-H", 250], (250, 250)),   # both: stretched
])
def test_resize(tmp_path, args, size):
    src = photo(tmp_path / "p.jpg")
    assert run(src, "-t", "X", *args).returncode == 0
    assert Image.open(out_of(tmp_path, "p")).size == size


def test_phone_photo_is_turned_upright(tmp_path):
    src = phone_photo(tmp_path / "phone.jpg")
    assert run(src, "-t", "X").returncode == 0
    assert Image.open(out_of(tmp_path, "phone")).size == (300, 400)


def test_location_and_camera_data_are_removed(tmp_path):
    src = phone_photo(tmp_path / "phone.jpg")
    original = Image.open(src)
    assert original.getexif().get_ifd(0x8825), "test photo should start with GPS"
    assert run(src, "-t", "X").returncode == 0
    dest = out_of(tmp_path, "phone")
    out = Image.open(dest)
    assert not out.getexif(), "EXIF (GPS, camera make) should be gone"
    raw = dest.read_bytes()
    for marker in (b"GPSLatitude", b"PhoneMaker", b"ns.adobe.com/xap", b"Exif\x00\x00"):
        assert marker not in raw, f"{marker!r} survived"


def test_colour_profile_is_kept(tmp_path):
    src = phone_photo(tmp_path / "phone.jpg")
    assert run(src, "-t", "X").returncode == 0
    assert Image.open(out_of(tmp_path, "phone")).info.get("icc_profile") == Image.open(src).info["icc_profile"]


def test_transparent_png_becomes_white_not_black_or_hidden_colour(tmp_path):
    src = tmp_path / "clear.png"
    Image.new("RGBA", (200, 200), (0, 0, 255, 0)).save(src)
    assert run(src, "-t", "X", "-s", "corner").returncode == 0
    r, g, b = Image.open(out_of(tmp_path, "clear")).getpixel((2, 2))
    assert min(r, g, b) > 245


def test_folder_batch_processes_images_and_skips_other_files(tmp_path):
    photo(tmp_path / "a.jpg")
    photo(tmp_path / "b.JPEG")
    Image.new("RGB", (50, 50)).save(tmp_path / "c.png")
    (tmp_path / "notes.txt").write_text("not a photo")
    r = run(tmp_path, "-t", "X")
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in (tmp_path / "watermarked").iterdir()) == ["a_wm.jpg", "b_wm.jpg", "c_wm.jpg"]


def test_originals_are_never_changed(tmp_path):
    src = phone_photo(tmp_path / "phone.jpg")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    assert run(src, "-t", "X", "-W", 100).returncode == 0
    assert hashlib.sha256(src.read_bytes()).hexdigest() == digest


def test_out_and_suffix(tmp_path):
    src = photo(tmp_path / "p.jpg")
    assert run(src, "-t", "X", "--out", tmp_path / "elsewhere", "--suffix", "_mark").returncode == 0
    assert (tmp_path / "elsewhere" / "p_mark.jpg").exists()


def test_non_latin_text_and_tiny_images(tmp_path):
    src = photo(tmp_path / "tiny.jpg", size=(40, 30))
    r = run(src, "-t", "日本 · FOR AIRBNB · 中文")
    assert r.returncode == 0, r.stderr
    assert Image.open(out_of(tmp_path, "tiny")).size == (40, 30)


@pytest.mark.parametrize("args", [
    [],                         # no --text
    ["-t", "X", "-d", "0"],
    ["-t", "X", "-d", "31"],
    ["-t", "X", "-W", "0"],
    ["-t", "X", "-s", "spiral"],
])
def test_bad_options_are_refused(tmp_path, args):
    src = photo(tmp_path / "p.jpg")
    assert run(src, *args).returncode != 0
    assert not (tmp_path / "watermarked").exists()


def test_missing_file_is_reported(tmp_path):
    r = run(tmp_path / "nope.jpg", "-t", "X")
    assert r.returncode != 0 and "No JPEG or PNG" in r.stderr
