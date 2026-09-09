#!/usr/bin/env bash
# Build GIF Maker as a standalone macOS application (.app).
# Run this on a Mac, with Python 3.10+ and the dependencies installed:
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --windowed --name "GIF Maker" \
    --icon "assets/AppIcon.icns" \
    --collect-all imageio_ffmpeg \
    --collect-all imageio \
    main.py

echo "Application created at dist/GIF Maker.app"
