#!/usr/bin/env bash
# Build Conference Organizer as a standalone Linux executable.
# Run this on Linux, with Python 3.10+ and the dependencies installed:
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --onefile --name "Conference Organizer" \
    --icon "assets/AppIcon.png" \
    main.py

echo "Executable created at dist/Conference Organizer"
