#!/bin/sh
# One-time setup: a private Python environment with Pillow, beside the script.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DIR/.venv/bin/pip" install --quiet -r "$DIR/requirements.txt"
echo "Ready. Try:  $DIR/watermark --help"
