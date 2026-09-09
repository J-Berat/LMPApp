#!/usr/bin/env bash
# Build GIF Maker as a standalone Linux executable.
# Run this on Linux, with Python 3.10+ and the dependencies installed:
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --onefile --name "GIF Maker" \
    --icon "assets/AppIcon.png" \
    --collect-all imageio_ffmpeg \
    --collect-all imageio \
    main.py

echo "Executable created at dist/GIF Maker"
