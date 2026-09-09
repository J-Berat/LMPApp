#!/usr/bin/env bash
# Build Conference Organizer as a standalone macOS application (.app).
# Run this on a Mac, with Python 3.10+ and the dependencies installed:
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --windowed --name "Conference Organizer" \
    --icon "assets/AppIcon.icns" \
    main.py

echo "Application created at dist/Conference Organizer.app"
