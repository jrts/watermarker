# watermarker

Adds a text watermark to JPEG (and PNG) photos. Originals are never changed.

Built for marking photos and ID scans before uploading them somewhere — a
repeated diagonal watermark is hard to crop or edit out.

- Four styles: **tiled** diagonal lines (default), **centre**, **corner**, **banner**
- Batch: pass a folder and every JPEG/PNG in it is processed
- Optional resize: width, height, or both
- Strips metadata (GPS, camera details) and fixes phone rotation
- Handles Japanese, Chinese and other non-Latin text

## Install

Needs Python 3.9+.

```sh
git clone https://github.com/jrts/watermarker.git
cd watermarker
./setup.sh
```

`setup.sh` creates a private Python environment in `.venv` with
[Pillow](https://python-pillow.org/), so nothing is installed system-wide.
The `watermark` command runs the script inside it.

Prefer your own environment? `pip install -r requirements.txt`, then run
`python3 watermark.py` instead of `./watermark`.

## Run it

```sh
./watermark photo.jpg --text "FOR AIRBNB ONLY"
./watermark ~/Pictures/airbnb/ --text "FOR AIRBNB ONLY"      # a whole folder
```

Output goes to a `watermarked/` folder beside each photo, named `<name>_wm.jpg`.
Folders are read one level deep (not subfolders). Other files are skipped.

## Options

| Option | What it does | Default |
|---|---|---|
| `-t, --text` | The watermark text. **Required.** | — |
| `-s, --style` | `tiled`, `centre`, `corner`, `banner` | `tiled` |
| `-d, --density` | Tiled only: **number of lines of text** across the photo, 1–30 | `6` |
| `-o, --opacity` | 0.05–1.0 | tiled 0.28, centre 0.35, corner 0.8, banner 0.9 |
| `--size` | Text height as a fraction of the photo's short side | 0.045–0.05 |
| `--angle` | Degrees | tiled 30, centre follows the diagonal |
| `--color` | `white`, `black`, `red` | `white` |
| `-W, --width` | Output width in px | original |
| `-H, --height` | Output height in px | original |
| `--out` | Output folder | `watermarked/` beside each photo |
| `--suffix` | Added to the filename | `_wm` |
| `--quality` | JPEG quality | 92 |

**Resizing:** give neither and the size is unchanged. Give one of `--width` or
`--height` and the other follows the photo's proportions. Give both and the
photo is stretched to exactly that size. Resizing happens before the
watermark goes on, so the text is sized for the final image.

**White on white:** the default text is white, which disappears on white
paper. Use `--color black` for scans of documents.

**Privacy:** output files carry no metadata — GPS location and camera details
are stripped. Phone photos are rotated the right way up first.

## Examples

```sh
# A passport photo, 10 lines of text, dated
./watermark ~/Desktop/passport.jpg -t "FOR AIRBNB ONLY 14 OCT 2026" -d 10

# A whole folder, corner stamp, 1600 px wide
./watermark ~/Pictures/flat/ -t "MY FLAT" -s corner -W 1600

# Exactly 1080 x 1080 (stretched)
./watermark photo.jpg -t "FOR AIRBNB ONLY" -W 1080 -H 1080
```
