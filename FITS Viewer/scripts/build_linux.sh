#!/usr/bin/env bash
# Build FITS Viewer as a standalone Linux executable.
# Run this on Linux, with Python 3.10+ and the dependencies installed:
#   pip install -r requirements.txt pyinstaller
set -euo pipefail
cd "$(dirname "$0")/.."

pyinstaller --noconfirm --clean --onefile --name "FITS Viewer" \
    --icon "assets/AppIcon.png" \
    --collect-all astropy \
    --collect-all pyqtgraph \
    --collect-all h5py \
    main.py

echo "Executable created at dist/FITS Viewer"
